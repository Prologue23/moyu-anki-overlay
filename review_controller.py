# -*- coding: utf-8 -*-
"""Fetch/answer cards for the Moyu overlay using Anki's scheduler."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
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


@dataclass
class CardText:
    front: str
    back: str


class ReviewController:
    def __init__(self) -> None:
        self.card = None
        self.active = False

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
            did = mw.col.decks.get_current_id()
            mw.col.decks.select(did)
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
        front = self._front_plain(front_html)
        back = self._answer_plain(answer_html, front)
        return CardText(front=front or "（空白正面）", back=back or "（空白背面）")

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
        mw.col.decks.select(did)
        mw.col.sched.answerCard(self.card, ease)

        if mw.state == "deckBrowser" and getattr(mw, "deckBrowser", None):
            try:
                mw.deckBrowser.refresh()
            except Exception:
                pass

        return self.load_next()

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
