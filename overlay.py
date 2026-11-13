# -*- coding: utf-8 -*-
"""Frameless always-on-top pill bar for stealth Anki review."""

from __future__ import annotations

from typing import Callable, Optional

from aqt.qt import (
    QApplication,
    QColor,
    QEvent,
    QFont,
    QHBoxLayout,
    QKeySequence,
    QLabel,
    QLineEdit,
    QPainter,
    QPlainTextEdit,
    QPoint,
    QSizePolicy,
    QTextEdit,
    QTimer,
    Qt,
    QVBoxLayout,
    QWidget,
    pyqtSignal,
)

from .config_dialog import merge_config
from .review_controller import ReviewController


def _truncate(text: str, max_chars: int) -> str:
    text = (text or "").replace("\n", " ").strip()
    if max_chars > 0 and len(text) > max_chars:
        return text[: max_chars - 1] + "…"
    return text


def _normalize_key_name(name: str) -> str:
    n = (name or "").strip()
    aliases = {
        " ": "Space",
        "Space": "Space",
        "Return": "Return",
        "Enter": "Return",
        "\n": "Return",
        "\r": "Return",
    }
    if n in aliases:
        return aliases[n]
    return QKeySequence(n).toString(QKeySequence.SequenceFormat.PortableText) or n


def _key_from_event(event) -> str:
    k = event.key()
    if k == Qt.Key.Key_Space:
        return "Space"
    if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
        return "Return"
    if int(Qt.Key.Key_0) <= int(k) <= int(Qt.Key.Key_9):
        return str(int(k) - int(Qt.Key.Key_0))
    if int(Qt.Key.Key_A) <= int(k) <= int(Qt.Key.Key_Z):
        return chr(ord("A") + int(k) - int(Qt.Key.Key_A))
    try:
        text = QKeySequence(event.keyCombination()).toString(
            QKeySequence.SequenceFormat.PortableText
        )
    except Exception:
        text = QKeySequence(k).toString(QKeySequence.SequenceFormat.PortableText)
    return _normalize_key_name(text)


class MoyuOverlay(QWidget):
    closed = pyqtSignal()
    position_changed = pyqtSignal(int, int)

    def __init__(
        self,
        controller: ReviewController,
        config: dict,
        on_config_save: Callable[[dict], None],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.config = merge_config(config)
        self._on_config_save = on_config_save
        self._hovered = False
        self._pinned_reveal = False
        # After grading: stay collapsed until mouse leaves, then hover works again.
        self._await_mouse_leave = False
        self._dragging = False
        self._drag_offset = QPoint()
        self._opacity = float(self.config.get("opacity", 0.88))
        self._filter_installed = False
        self._keyboard_grabbed = False

        self.setObjectName("MoyuOverlay")
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow, True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._build_ui()
        self._apply_geometry_defaults()
        self._apply_typography()

        self._hover_timer = QTimer(self)
        self._hover_timer.setInterval(40)
        self._hover_timer.timeout.connect(self._poll_hover)
        self.refresh()

    def apply_config(self, config: dict) -> None:
        self.config = merge_config(config)
        self._opacity = float(self.config.get("opacity", 0.88))
        self._apply_typography()
        self.refresh()

    def _chip_style(self) -> str:
        family = str(self.config.get("font_family") or "PingFang SC")
        size = int(self.config.get("font_size") or 13)
        return f"""
        QLabel#contentChip {{
            color: #1c1c1e;
            background: rgba(255, 255, 255, 235);
            border-radius: 11px;
            padding: 5px 12px;
            font-family: "{family}";
            font-size: {size}px;
        }}
        """

    def _apply_typography(self) -> None:
        family = str(self.config.get("font_family") or "PingFang SC")
        size = int(self.config.get("font_size") or 13)
        style = self._chip_style()
        self.front_chip.setStyleSheet(style)
        self.back_chip.setStyleSheet(style)
        font = QFont(family, size)
        font.setBold(False)
        self.front_chip.setFont(font)
        self.back_chip.setFont(font)

    def _make_chip(self) -> QLabel:
        label = QLabel("")
        label.setObjectName("contentChip")
        label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        return label

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(2, 2, 2, 2)
        root.setSpacing(4)
        root.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self.front_chip = self._make_chip()
        self.back_chip = self._make_chip()
        self.back_chip.hide()

        root.addWidget(
            self.front_chip, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        root.addWidget(
            self.back_chip, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )

        self.setMinimumHeight(24)
        self.setMaximumHeight(120)

    def _apply_geometry_defaults(self) -> None:
        self.resize(180, 30)
        screen = self.screen()
        geo = screen.availableGeometry() if screen else None
        x = self.config.get("pos_x")
        y = self.config.get("pos_y")
        if x is None or y is None:
            if geo:
                x = geo.x() + geo.width() // 2 - 90
                y = geo.y() + 12
            else:
                x, y = 200, 40
        self.move(int(x), int(y))

    def _install_app_filter(self) -> None:
        app = QApplication.instance()
        if app and not self._filter_installed:
            app.installEventFilter(self)
            self._filter_installed = True

    def _remove_app_filter(self) -> None:
        app = QApplication.instance()
        if app and self._filter_installed:
            app.removeEventFilter(self)
            self._filter_installed = False

    def _grab_keys(self) -> None:
        if self._keyboard_grabbed:
            return
        try:
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
            self.raise_()
            self.activateWindow()
            self.setFocus(Qt.FocusReason.OtherFocusReason)
            self.grabKeyboard()
            self._keyboard_grabbed = True
        except Exception:
            self._keyboard_grabbed = False

    def _release_keys(self) -> None:
        if not self._keyboard_grabbed:
            return
        try:
            self.releaseKeyboard()
        except Exception:
            pass
        self._keyboard_grabbed = False
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

    def show_overlay(self) -> None:
        if not self.controller.can_start():
            return
        if not self.controller.active:
            self.controller.start()
        else:
            self.controller.load_next()
        self._await_mouse_leave = False
        self._hovered = False
        self._pinned_reveal = False
        self._release_keys()
        self.refresh()
        self.show()
        self.raise_()
        self._install_app_filter()
        self._hover_timer.start()

    def hide_overlay(self) -> None:
        self._hover_timer.stop()
        self._release_keys()
        self._remove_app_filter()
        self._pinned_reveal = False
        self.controller.stop()
        self.hide()

    def toggle(self) -> None:
        if self.isVisible():
            self.hide_overlay()
        else:
            self.show_overlay()

    def refresh(self) -> None:
        max_chars = int(self.config.get("max_chars", 48))
        text = self.controller.current_text()
        if not text:
            self.front_chip.setText("暂无到期")
            self.back_chip.setText(
                self.controller.deck_name() or "当前牌组没有可复习的卡片"
            )
            self._relayout()
            return

        self.front_chip.setText(_truncate(text.front, max_chars))
        self.back_chip.setText(_truncate(text.back, max_chars * 2))
        self._relayout()

    def _expanded(self) -> bool:
        if self._await_mouse_leave or self.controller.card is None:
            return False
        return self._hovered or self._pinned_reveal

    def _measure_width(self) -> int:
        max_w = int(self.config.get("collapsed_width", 520))
        auto = bool(self.config.get("auto_width", True))
        chrome = 4
        self.front_chip.adjustSize()
        front_w = self.front_chip.sizeHint().width()
        if self._expanded():
            self.back_chip.adjustSize()
            back_w = self.back_chip.sizeHint().width()
            needed = max(front_w, back_w) + chrome
            return max(80, min(needed, max(max_w, 720)))
        needed = front_w + chrome
        if auto:
            return max(80, min(needed, max_w))
        return max_w

    def _relayout(self) -> None:
        expanded = self._expanded()
        anchor = self.pos()
        self.back_chip.setVisible(expanded)
        if expanded:
            self.setFixedHeight(self.front_chip.sizeHint().height() + self.back_chip.sizeHint().height() + 10)
            self.setWindowOpacity(min(1.0, self._opacity + 0.05))
            self._grab_keys()
        else:
            self.setFixedHeight(max(28, self.front_chip.sizeHint().height() + 4))
            self.setWindowOpacity(self._opacity)
            if not self._hovered and not self._pinned_reveal:
                self._release_keys()
        self.setFixedWidth(self._measure_width())
        self.move(anchor)
        self.updateGeometry()
        self.update()

    def _reveal_keys(self) -> set[str]:
        sc = self.config.get("shortcuts") or {}
        out = set()
        for key in (sc.get("reveal_1"), sc.get("reveal_2")):
            n = _normalize_key_name(str(key or ""))
            if n:
                out.add(n)
        return out

    def _reveal_grade_ease(self) -> int:
        """Grade applied when reveal keys are pressed while answer is visible."""
        sc = self.config.get("shortcuts") or {}
        name = str(sc.get("reveal_grade") or "good").lower()
        return {"again": 1, "hard": 2, "good": 3, "easy": 4}.get(name, 3)

    def _grade_map(self) -> dict[str, int]:
        sc = self.config.get("shortcuts") or {}
        mapping: dict[str, int] = {}
        for name, ease in (("again", 1), ("hard", 2), ("good", 3), ("easy", 4)):
            key = _normalize_key_name(str(sc.get(name) or ""))
            if key:
                mapping[key] = ease
        return mapping

    def _cursor_over_self(self) -> bool:
        if not self.isVisible():
            return False
        # Slightly inflate hit area so leaving/entering is reliable after resize.
        geo = self.frameGeometry().adjusted(-2, -2, 2, 2)
        return geo.contains(self.cursor().pos())

    def _poll_hover(self) -> None:
        if not self.isVisible() or self._dragging:
            return
        over = self._cursor_over_self()

        # Must leave after grading before hover/keys can reveal the next card.
        if self._await_mouse_leave:
            if not over:
                self._await_mouse_leave = False
            else:
                return

        if over and not self._hovered:
            self._hovered = True
            self._grab_keys()
            self._relayout()
        elif not over and self._hovered:
            self._hovered = False
            if not self._pinned_reveal:
                self._release_keys()
            self._relayout()
        elif over and self._hovered and not self._keyboard_grabbed:
            self._grab_keys()

    def _typing_in_field(self) -> bool:
        w = QApplication.focusWidget()
        if w is self or (w is not None and self.isAncestorOf(w)):
            return False
        return isinstance(w, (QLineEdit, QTextEdit, QPlainTextEdit))

    def _anki_active(self) -> bool:
        app = QApplication.instance()
        if not app:
            return False
        return app.applicationState() == Qt.ApplicationState.ApplicationActive

    def _handle_hotkey(self, key: str) -> bool:
        if not self.isVisible() or not self.controller.active:
            return False
        if self.controller.card is None:
            return False
        if self._typing_in_field():
            return False
        if self._await_mouse_leave:
            return False

        over_or_pinned = (
            self._hovered or self._pinned_reveal or self._cursor_over_self()
        )
        if not over_or_pinned and not self._anki_active():
            return False

        if key in self._reveal_keys():
            if self._expanded():
                self._on_grade(self._reveal_grade_ease())
            else:
                self._pinned_reveal = True
                self._grab_keys()
                self._relayout()
            return True

        # Grade keys (1-4 etc.): reveal when answer hidden; grade when shown.
        ease = self._grade_map().get(key)
        if ease:
            if self._expanded():
                self._on_grade(ease)
            else:
                self._pinned_reveal = True
                self._grab_keys()
                self._relayout()
            return True
        return False

    def _on_grade(self, ease: int) -> None:
        ok = self.controller.answer(ease)
        if not self.controller.active:
            self.hide_overlay()
            self.closed.emit()
            return
        # Collapse next card; require mouse leave then re-hover / shortcut.
        self._await_mouse_leave = True
        self._hovered = False
        self._pinned_reveal = False
        self._release_keys()
        self.refresh()
        if not ok and self.controller.card is None:
            self.refresh()

    def eventFilter(self, obj, event):  # noqa: N802
        et = event.type()
        if et == QEvent.Type.KeyPress and self.isVisible():
            if self._handle_hotkey(_key_from_event(event)):
                return True
        if et == QEvent.Type.ShortcutOverride and self.isVisible():
            key = _key_from_event(event)
            over_or_pinned = (
                self._hovered or self._pinned_reveal or self._cursor_over_self()
            )
            if self._await_mouse_leave:
                return False
            if over_or_pinned or self._anki_active():
                if key in self._reveal_keys() or key in self._grade_map():
                    event.accept()
                    return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if self._handle_hotkey(_key_from_event(event)):
            event.accept()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            if (
                not self._expanded()
                and self.controller.card
                and not self._await_mouse_leave
            ):
                self._pinned_reveal = True
                self._grab_keys()
                self._relayout()
            self._dragging = True
            self._drag_offset = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._dragging and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            pos = self.pos()
            self.config["pos_x"] = pos.x()
            self.config["pos_y"] = pos.y()
            self._on_config_save(self.config)
            self.position_changed.emit(pos.x(), pos.y())
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        # Fully transparent chrome — only the white capsules are visible.
        painter = QPainter(self)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 0))
        painter.end()
