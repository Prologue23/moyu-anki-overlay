# -*- coding: utf-8 -*-
"""摸鱼复习条 — stealth single-line Anki review overlay for macOS."""

from __future__ import annotations

import traceback
from pathlib import Path
from typing import Optional

from aqt import gui_hooks, mw
from aqt.qt import QAction, QKeySequence, QTimer, qconnect
from aqt.utils import tooltip

from .config_dialog import MoyuConfigDialog, merge_config

ADDON_NAME = "摸鱼复习条"
_LOG = Path(__file__).with_name("moyu_debug.log")
_controller = None
_overlay = None
_menu_action: Optional[QAction] = None


def _log(msg: str) -> None:
    try:
        with _LOG.open("a", encoding="utf-8") as f:
            f.write(msg.rstrip() + "\n")
    except Exception:
        pass


def _load_config() -> dict:
    conf = mw.addonManager.getConfig(__name__)
    return merge_config(conf if isinstance(conf, dict) else {})


def _save_config(conf: dict) -> None:
    conf = merge_config(conf)
    mw.addonManager.writeConfig(__name__, conf)
    if _overlay is not None:
        _overlay.apply_config(conf)
    if _menu_action is not None:
        shortcut = conf.get("toggle_shortcut") or "Ctrl+Shift+M"
        try:
            _menu_action.setShortcut(QKeySequence(shortcut))
        except Exception:
            pass


def _open_config() -> bool:
    try:
        dlg = MoyuConfigDialog(_load_config(), on_save=_save_config, parent=mw)
        dlg.exec()
    except Exception:
        _log("config dialog failed:\n" + traceback.format_exc())
        tooltip("打开设置失败，详见 moyu_debug.log")
    return True


def _ensure_overlay():
    global _controller, _overlay
    from .overlay import MoyuOverlay
    from .review_controller import ReviewController

    if _controller is None:
        _controller = ReviewController()
    if _overlay is None:
        _overlay = MoyuOverlay(
            controller=_controller,
            config=_load_config(),
            on_config_save=_save_config,
            parent=None,
        )
        _overlay.closed.connect(lambda: tooltip("摸鱼复习条已关闭"))
    else:
        _overlay.apply_config(_load_config())
    return _overlay


def toggle_overlay() -> None:
    try:
        if not mw or not mw.col:
            tooltip("请先打开一个配置文件。")
            return
        overlay = _ensure_overlay()
        if overlay.isVisible():
            overlay.hide_overlay()
            tooltip("已隐藏摸鱼复习条")
            return
        if mw.state == "review":
            tooltip("请先退出主界面复习，再打开摸鱼复习条。")
            return
        overlay.apply_config(_load_config())
        overlay.show_overlay()
        if _controller and _controller.card is None and _controller.active:
            tooltip("当前牌组暂无到期卡片")
    except Exception:
        _log("toggle_overlay failed:\n" + traceback.format_exc())
        tooltip("摸鱼复习条出错，详见插件目录 moyu_debug.log")


def show_overlay_if_configured() -> None:
    try:
        conf = _load_config()
        if not conf.get("auto_show", True):
            return
        if not mw or not mw.col:
            return
        if mw.state == "review":
            return
        overlay = _ensure_overlay()
        overlay.apply_config(conf)
        overlay.show_overlay()
        _log("auto_show overlay visible=" + str(overlay.isVisible()))
    except Exception:
        _log("show_overlay_if_configured failed:\n" + traceback.format_exc())


def _setup_menu() -> None:
    global _menu_action
    if _menu_action is not None:
        return
    menu = getattr(getattr(mw, "form", None), "menuTools", None)
    if menu is None:
        raise RuntimeError("mw.form.menuTools not available")

    action = QAction(f"显示/隐藏{ADDON_NAME}", mw)
    conf = _load_config()
    shortcut = conf.get("toggle_shortcut") or "Ctrl+Shift+M"
    try:
        action.setShortcut(QKeySequence(shortcut))
    except Exception:
        _log(f"bad shortcut {shortcut!r}, ignored")
    qconnect(action.triggered, toggle_overlay)
    menu.addAction(action)
    _menu_action = action

    settings = QAction(f"{ADDON_NAME}设置…", mw)
    qconnect(settings.triggered, _open_config)
    menu.addAction(settings)
    _log("menu action added")


def _on_profile_loaded() -> None:
    _log("profile_did_open")
    try:
        _setup_menu()
    except Exception:
        _log("setup_menu on profile failed:\n" + traceback.format_exc())
    try:
        mw.addonManager.setConfigAction(__name__, _open_config)
    except Exception:
        _log("setConfigAction failed:\n" + traceback.format_exc())
    QTimer.singleShot(500, show_overlay_if_configured)


def _on_state_change(new_state: str, old_state: str) -> None:
    try:
        if new_state == "review" and _overlay and _overlay.isVisible():
            _overlay.hide_overlay()
            tooltip("已进入主界面复习，摸鱼复习条已暂停。")
    except Exception:
        _log("state_change failed:\n" + traceback.format_exc())


_log("--- addon import start ---")
try:
    gui_hooks.profile_did_open.append(_on_profile_loaded)
    gui_hooks.state_did_change.append(_on_state_change)
    _log("hooks registered")
except Exception:
    _log("hook registration failed:\n" + traceback.format_exc())

try:
    _setup_menu()
except Exception:
    _log("early setup_menu failed:\n" + traceback.format_exc())

try:
    mw.addonManager.setConfigAction(__name__, _open_config)
except Exception:
    _log("early setConfigAction failed:\n" + traceback.format_exc())

_log("--- addon import done ---")
