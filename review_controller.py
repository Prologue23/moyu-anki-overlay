# -*- coding: utf-8 -*-
"""Fetch/answer cards for the Moyu overlay using Anki's scheduler."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Optional

from aqt import mw
from aqt.utils import tooltip

_SOUND_RE = re.compile(r"\[sound:[^\]]*\]", re.IGNORECASE)
# Anki type-in-the-answer placeholders after render / in templates
_TYPE_RE = re.compile(
    r"\[\[\s*type\s*:[^\]]*\]\]|\{\{\s*type\s*:[^}]*\}\}",
    re.IGNORECASE,
)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_ANSWER_SPLIT_RE = re.compile(
    r"(?:<hr[^>]*id=[\"']?answer[\"']?[^>]*>)"
    r"|(?:\n-{3,}\n)"
    r"|(?:<div[^>]*class=[\"'][^\"']*answer[^\"']*[\"'][^>]*>)",
    re.IGNORECASE,
)
# Template chrome labels often left in plain text after stripping HTML
_FRONT_LABEL_RE = re.compile(
    r"^(?:Question|Front|问题|正面|问)\s*[:：]?\s*",
    re.IGNORECASE,
)
_BACK_LABEL_RE = re.compile(
    r"^(?:Answer|Back|答案|背面|答)\s*[:：]?\s*",
    re.IGNORECASE,
)
_SPLIT_ANSWER_LABEL_RE = re.compile(
    r"(?:^|\s)(?:Answer|Back|答案|背面)\s*[:：]?\s+",
    re.IGNORECASE,
)


def _strip_html(raw: str) -> str:
    """Local HTML stripper — avoids Anki backend strip_html when unavailable."""
    if not raw:
        return ""
    raw = re.sub(r"<(script|style)\b[^>]*>.*?</\1\s*>", "", raw, flags=re.IGNORECASE | re.DOTALL)
    raw = re.sub(r"<!--.*?-->", "", raw, flags=re.DOTALL)
    try:
        from anki.utils import strip_html as anki_strip

        text = anki_strip(raw)
        if text is not None:
            return text
    except Exception:
        pass
    text = raw.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    text = re.sub(r"</p\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</div\s*>", "\n", text, flags=re.IGNORECASE)
    text = _TAG_RE.sub("", text)
    return text


def _clean_plain(raw: str) -> str:
    if not raw:
        return ""
    text = _TYPE_RE.sub("", raw)
    text = _SOUND_RE.sub("", text)
    text = _strip_html(text)
    text = html.unescape(text)
    text = _WS_RE.sub(" ", text).strip()
    return text


class _WithoutNote(HTMLParser):
    """Remove explicitly marked note containers without touching other text."""
    _void = {"area", "base", "br", "col", "embed", "hr", "img", "input",
             "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.parts = []
        self.depth = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        markers = {attrs.get("id", "").casefold(),
                   *attrs.get("class", "").casefold().split()}
        if self.depth:
            if tag not in self._void:
                self.depth += 1
        elif markers & {"note", "notes", "备注", "注释", "笔记"}:
            if tag not in self._void:
                self.depth = 1
        else:
            self.parts.append(self.get_starttag_text())

    def handle_startendtag(self, tag, attrs):
        if not self.depth:
            self.handle_starttag(tag, attrs)
            self.depth = 0

    def handle_endtag(self, tag):
        if self.depth:
            self.depth -= 1
        else:
            self.parts.append("</" + tag + ">")

    def handle_data(self, data):
        if not self.depth:
            self.parts.append(data)

    def handle_entityref(self, name):
        self.handle_data("&" + name + ";")

    def handle_charref(self, name):
        self.handle_data("&#" + name + ";")


def _without_note(raw: str) -> str:
    parser = _WithoutNote()
    parser.feed(raw)
    parser.close()
    return "".join(parser.parts)


def _separate_note(text: str, note: str) -> str:
    # Common templates append an unmarked {{Note}} after the answer. Remove
    # only a distinct suffix, not matching words inside the question/answer.
    if note and text != note and text.endswith(note):
        prefix = text[:-len(note)]
        if prefix and (prefix[-1].isspace() or prefix[-1] in "|:：—–-"):
            prefix = re.sub(r"(?:^|\s)(?:Notes?|备注|注释)\s*[:：]?\s*$", "", prefix,
                            flags=re.IGNORECASE)
            return prefix.rstrip(" |:：—–-")
    return text


@dataclass
class CardText:
    front: str
    back: str
    note: str = ""


class ReviewController:
    def __init__(self) -> None:
        self.card = None
        self.active = False
        self._last_answer = None

    def can_start(self) -> bool:
        if not mw or not mw.col:
            return False
        if mw.state == "review":
            tooltip("请先退出主界面复习，再使用摸鱼复习条。")
            return False
        return True

    def start(self) -> bool:
        if not self.can_start():
            return False
        self.active = True
        return self.load_next()

    def stop(self) -> None:
        self.active = False
        self.card = None

    def load_next(self) -> bool:
        if not self.active or not mw or not mw.col:
            self.card = None
            return False

        try:
            # The scheduler already follows the selected deck. Re-selecting
            # it creates an undo step on current Anki and masks our review.
            self.card = mw.col.sched.getCard()
        except Exception:
            self.card = None
            return False

        if not self.card:
            return False

        if hasattr(self.card, "start_timer"):
            self.card.start_timer()
        elif hasattr(self.card, "startTimer"):
            self.card.startTimer()
        return True

    def current_text(self) -> Optional[CardText]:
        if not self.card:
            return None
        front_html = self.card.question()
        answer_html = self.card.answer()
        note = ""
        for name, value in self.card.note().items():
            if name.strip().casefold() in {"note", "notes", "备注", "注释", "笔记"}:
                note = _clean_plain(value)
                if note:
                    break
        # Keep card rendering (including reversed/cloze cards); only separate
        # note content so it is not exposed before the answer or shown twice.
        if note:
            front_html = _without_note(front_html)
            answer_html = _without_note(answer_html)
        front = _separate_note(self._front_plain(front_html), note)
        back = _separate_note(self._answer_plain(answer_html, front), note)
        return CardText(front=front or "（空白正面）", back=back or "（空白背面）", note=note)

    def current_html(self) -> Optional[tuple[str, str, str]]:
        """Keep the actual card direction, CSS and note markup for the web view."""
        if not self.card:
            return None
        note = ""
        for name, value in self.card.note().items():
            if name.strip().casefold() in {"note", "notes", "备注", "注释", "笔记"}:
                if _clean_plain(value):
                    note = value
                    break
        return self.card.question(), self.card.answer(), note

    def answer(self, ease: int) -> bool:
        if not self.active or not self.card or not mw or not mw.col:
            return False
        if ease not in (1, 2, 3, 4):
            return False
        if mw.state == "review":
            tooltip("主界面正在复习，已暂停摸鱼取卡。")
            self.stop()
            return False

        did = mw.col.decks.get_current_id()
        col = mw.col
        card_id = self.card.id
        before = self._undo_step(col)
        self._last_answer = None
        col.sched.answerCard(self.card, ease)
        after = self._undo_step(col)
        if after is not None and after != before:
            self._last_answer = (col, after, card_id, did)

        if mw.state == "deckBrowser" and getattr(mw, "deckBrowser", None):
            try:
                mw.deckBrowser.refresh()
            except Exception:
                pass

        return self.load_next()

    def delete_current_card(self) -> bool:
        """Remove only the current card; sibling cards (and the note) stay if any remain."""
        if not self.active or not self.card or not mw or not mw.col:
            return False
        if mw.state == "review":
            tooltip("主界面正在复习，已暂停摸鱼取卡。")
            self.stop()
            return False

        col = mw.col
        card_id = self.card.id
        note_id = self.card.nid
        try:
            sibling_count = len(col.card_ids_of_note(note_id))
        except Exception:
            sibling_count = 1

        self._last_answer = None
        try:
            col.remove_cards_and_orphaned_notes([card_id])
        except Exception:
            tooltip("删除卡片失败。")
            return False

        if sibling_count > 1:
            tooltip("已删除当前卡片（同笔记其他卡片保留）")
        else:
            tooltip("已删除当前卡片（该笔记无其他卡片，笔记已一并删除）")

        if mw.state == "deckBrowser" and getattr(mw, "deckBrowser", None):
            try:
                mw.deckBrowser.refresh()
            except Exception:
                pass
        update = getattr(mw, "update_undo_actions", None)
        if callable(update):
            update()

        return self.load_next()

    @staticmethod
    def _undo_step(col):
        try:
            status = col.undo_status()
            return status.last_step if status.undo else None
        except Exception:
            return None

    def undo_last_answer(self) -> bool:
        """Undo only our own most recent review, using Anki's native history."""
        entry = self._last_answer
        if not self.active or not entry or not mw or not mw.col:
            tooltip("没有可撤销的摸鱼条评分。")
            return False
        col, step, card_id, deck_id = entry
        if (mw.col is not col or mw.state == "review" or
                self._undo_step(col) != step or
                col.decks.get_current_id() != deck_id):
            self._last_answer = None
            tooltip("Anki 已有其他操作，未撤销，以免影响其他修改。")
            return False
        try:
            col.undo()
        except Exception:
            tooltip("暂时无法撤销这次评分。")
            return False
        # Never retry the same history entry, even if reloading the card fails.
        self._last_answer = None
        try:
            self.card = col.get_card(card_id)
            if hasattr(self.card, "start_timer"):
                self.card.start_timer()
            elif hasattr(self.card, "startTimer"):
                self.card.startTimer()
        except Exception:
            self.load_next()
            tooltip("评分已撤销，但原卡片未能重新加载。")
            return False
        if mw.state == "deckBrowser" and getattr(mw, "deckBrowser", None):
            try:
                mw.deckBrowser.refresh()
            except Exception:
                pass
        update = getattr(mw, "update_undo_actions", None)
        if callable(update):
            update()
        return True

    def next_intervals(self) -> dict[int, str]:
        result = {1: "", 2: "", 3: "", 4: ""}
        if not self.card or not mw or not mw.col:
            return result
        for ease in (1, 2, 3, 4):
            try:
                result[ease] = mw.col.sched.nextIvlStr(self.card, ease)
            except Exception:
                result[ease] = ""
        return result

    def deck_name(self) -> str:
        if not mw or not mw.col:
            return ""
        try:
            return mw.col.decks.name(mw.col.decks.get_current_id())
        except Exception:
            return ""

    @classmethod
    def _front_plain(cls, raw: str) -> str:
        if not raw:
            return ""
        text = _ANSWER_SPLIT_RE.split(raw, maxsplit=1)[0]
        text = _clean_plain(text)
        text = _FRONT_LABEL_RE.sub("", text).strip()
        # If type placeholder left a hanging label-only string, already removed by _TYPE_RE
        return text

    @classmethod
    def _answer_plain(cls, answer_html: str, front_plain: str) -> str:
        if not answer_html:
            return ""

        parts = _ANSWER_SPLIT_RE.split(answer_html, maxsplit=1)
        if len(parts) > 1:
            body = parts[1]
        else:
            body = answer_html

        back = _clean_plain(body)
        back = _BACK_LABEL_RE.sub("", back).strip()

        # Some templates put both sides in one block with an "Answer" label.
        if front_plain and front_plain in back:
            after = back.split(front_plain, 1)[-1]
            after = _BACK_LABEL_RE.sub("", after).strip(" |:-—–")
            if after:
                back = after

        split = _SPLIT_ANSWER_LABEL_RE.split(back, maxsplit=1)
        if len(split) > 1 and split[1].strip():
            back = split[1].strip()

        back = _FRONT_LABEL_RE.sub("", back).strip()
        back = _BACK_LABEL_RE.sub("", back).strip()

        if front_plain and back.startswith(front_plain):
            back = back[len(front_plain) :].lstrip(" |:-—–")
            back = _BACK_LABEL_RE.sub("", back).strip()

        return back.strip()
