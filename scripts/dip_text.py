"""DIP fields as German display text.

DIP gives an abstract as HTML and a committee as a bare name; this module turns
them into the text a page shows: plain abstract paragraphs and their teaser, and
a committee's name in the genitive. It does no I/O and escapes nothing (the
caller escapes the result).
"""

from __future__ import annotations

import html as html_module
import re
from html.parser import HTMLParser
from typing import Any


#: About this many characters of an abstract show before the rest folds away.
CONTEXT_TEASER = 300
# A full stop after these is no sentence end: "Abs. 2", "z. B.", "Nr. 3" fill DIP abstracts.
_ABBREVIATIONS = frozenset(
    "abs art nr nrn bzw ca vgl ggf usw etc inkl gem lit buchst ziff kap anl bgbl dr st bspw sog insb einschl zzgl"
    " abschn bd jh mio mrd tsd".split()
)
_SENTENCE_END = re.compile(r"[.!?](?=\s)")
# Stripped off a token before the abbreviation test: "(Abs." is "Abs.".
_OPENERS = "([„\"‚'"
# The fallback for markup html.parser cannot read: a "<" that opens no tag stays text,
# and a closed <script> or <style> goes with its text, as on the parser's path. A
# comment goes first, to its "-->" or, unclosed, to the end.
_COMMENT = re.compile(r"<!--.*?(?:-->|\Z)", re.DOTALL)
_TAG_START = frozenset("!/?abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")
_SKIPPED_BLOCK = re.compile(r"<(script|style)\b[^>]*>.*?</\1\s*>", re.IGNORECASE | re.DOTALL)
#: Raw abstract characters read; the longest on the reference cache has 5,111. Both
#: html.parser and the fallback slow down quadratically on some malformed markup.
MAX_ABSTRACT_CHARS = 10_000
# A numeric character reference past U+10FFFF names no character; with more than
# 4,300 digits html.unescape raises instead of reading it as U+FFFD; int() counts
# leading zeros as digits, so they go first: "&#x0000041;" is "A".
_CHARREF_ZEROS = re.compile(r"&#(?:([xX])0+(?=[0-9a-fA-F])|0+(?=[0-9]))")
_OVERLONG_CHARREF = re.compile(r"&#(?:[xX][0-9a-fA-F]{7,}|[0-9]{8,});?")
_PARTIAL_CHARREF = re.compile(r"&#?[0-9A-Za-z]*\Z")


def _after_equals(text: str, i: int) -> bool:
    """Whether ``text[i]`` follows "=" and nothing but whitespace."""
    j = i - 1
    while j >= 0 and text[j].isspace():
        j -= 1
    return j >= 0 and text[j] == "="


def _tag_closes(text: str) -> list[int]:
    """closes[i]: where a tag still open at i, outside quotes, ends; -1 if never.
    A quote counts only as an attribute value, after "=", as html.parser reads
    it: the apostrophe in ``<b it's>`` is part of a name and the tag ends at its ">"."""
    closes = [-1] * (len(text) + 1)
    for i in range(len(text) - 1, -1, -1):
        char = text[i]
        if char == ">":
            closes[i] = i
        elif char in "\"'" and _after_equals(text, i):
            quote_end = text.find(char, i + 1)
            closes[i] = closes[quote_end + 1] if quote_end != -1 else -1
        else:
            closes[i] = closes[i + 1]
    return closes


def _strip_tags(text: str) -> str:
    """Each tag in ``text`` replaced by a space: ``<`` and a letter, ``!``, ``/``
    or ``?``, up to the first ``>`` outside a quoted attribute value. A ``<``
    whose tag never closes stays text. Linear time: a regex retried at every
    ``<`` rescans to the end for each unclosed quote."""
    closes = _tag_closes(text)
    parts: list[str] = []
    start = i = 0
    while i < len(text) - 1:
        if text[i] == "<" and text[i + 1] in _TAG_START and closes[i + 1] != -1:
            parts.append(text[start:i])
            parts.append(" ")
            start = i = closes[i + 1] + 1
        else:
            i += 1
    parts.append(text[start:])
    return "".join(parts)


def _drop_cut_markup(kept: str, rest: str) -> str:
    """``kept`` without the character reference or tag the cut before ``rest``
    splits, which the parser would hand back as text ("&am", "<a hr"). Tags
    are read over the whole raw text as ``_strip_tags`` reads them: a tag that
    closes before the cut is passed over whole, a "<" inside its quoted
    attribute included; a "<" whose tag never closes stays text, as it does
    in an abstract that fits; the one tag that closes after the cut goes.
    A comment runs to its first "-->", as ``_parser_input`` reads it; the
    "<!--" of one that never closes is text."""
    text = kept + rest
    closes = _tag_closes(text)
    i = 0
    while i < len(kept):
        if text.startswith("<!--", i):
            end = text.find("-->", i + 4)
            if end == -1:
                i += 1
                continue
            if end + 3 > len(kept):
                kept = kept[:i]
                break
            i = end + 3
        elif text[i] == "<" and text[i + 1 : i + 2] in _TAG_START and closes[i + 1] != -1:
            if closes[i + 1] >= len(kept):
                kept = kept[:i]
                break
            i = closes[i + 1] + 1
        else:
            i += 1
    partial = _PARTIAL_CHARREF.search(kept)
    follower = text[len(kept) : len(kept) + 1]
    if partial and follower and (follower.isalnum() or follower in "#;"):
        kept = kept[: partial.start()]
    return kept


def _parser_input(text: str) -> str:
    """``text`` as every html.parser release reads it alike: each comment, ended
    at its first "-->", emptied to "<!---->" (it still parts the text around it,
    so "&am<!-- -->p;" stays two runs), and each "<" that opens a tag or comment that never
    closes written as "&lt;", so it reads as text. The 2025 security releases
    (3.11.13, 3.12.11, 3.13.4) changed both: older releases hand an unclosed
    "<a hr" or "<!-- x" back as text, newer ones drop the tag and read the
    comment to the end, and end a comment at "--!>" or "<!-->" too. Tags close
    as ``_strip_tags`` reads them and are passed over whole."""
    closes = _tag_closes(text)
    parts: list[str] = []
    start = i = 0
    while i < len(text) - 1:
        if text.startswith("<!--", i):
            end = text.find("-->", i + 4)
            if end != -1:
                parts.append(text[start:i])
                parts.append("<!---->")
                start = i = end + 3
                continue
        elif text[i] == "<" and text[i + 1] in _TAG_START and closes[i + 1] != -1:
            i = closes[i + 1] + 1
            continue
        elif text[i] != "<" or text[i + 1] not in _TAG_START:
            i += 1
            continue
        parts.append(text[start:i])
        parts.append("&lt;")
        start = i = i + 1
    parts.append(text[start:])
    return "".join(parts)


class _AbstractParser(HTMLParser):
    """Collects the text of a DIP abstract: a ``<br>`` or a block element ends a
    paragraph, every other tag is dropped with its text kept, ``<script>`` and
    ``<style>`` are dropped with their text."""

    BREAKS = frozenset({"br", "p", "div", "li", "ul", "ol", "tr", "h1", "h2", "h3", "h4", "h5", "h6"})
    SKIPPED = frozenset({"script", "style"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.paragraphs: list[list[str]] = [[]]
        self.skipping = 0

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag in self.SKIPPED:
            self.skipping += 1
        elif tag in self.BREAKS:
            self.paragraphs.append([])

    def handle_startendtag(self, tag: str, attrs: Any) -> None:
        if tag in self.BREAKS:
            self.paragraphs.append([])

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIPPED:
            self.skipping = max(0, self.skipping - 1)
        elif tag in self.BREAKS:
            self.paragraphs.append([])

    def handle_data(self, data: str) -> None:
        if not self.skipping:
            self.paragraphs[-1].append(data)


def abstract_text(raw: Any) -> str:
    """A DIP abstract as plain text: paragraphs separated by a blank line (``\n\n``),
    whitespace inside a paragraph collapsed to single spaces, entities unescaped,
    markup gone. The caller escapes the result; the raw text stays in the cache.
    Only the first ``MAX_ABSTRACT_CHARS`` characters are kept, less a tag or
    character reference the cut splits; finding that tag scans the rest."""
    if not raw:
        return ""
    raw = str(raw)
    if len(raw) > MAX_ABSTRACT_CHARS:
        raw = _drop_cut_markup(raw[:MAX_ABSTRACT_CHARS], raw[MAX_ABSTRACT_CHARS:])
    raw = _CHARREF_ZEROS.sub(lambda match: "&#" + (match.group(1) or ""), raw)
    raw = _OVERLONG_CHARREF.sub("\ufffd", raw)
    parser = _AbstractParser()
    # A marked section ("<![CDATA[", "<![oops]>") outside a comment goes to the fallback
    # unread: html.parser before the 2025 security releases raises on most of them,
    # later ones read a comment. Word's "<!--[if mso]>…<![endif]-->" is a comment.
    parser_input = _parser_input(raw)
    malformed = "<![" in parser_input
    if not malformed:
        try:
            parser.feed(parser_input)
            parser.close()
            malformed = parser.skipping > 0  # an unclosed <script> or <style> would swallow the rest
        except AssertionError:  # html.parser's answer to other markup it cannot read
            malformed = True
    if malformed:
        # Keep the words rather than lose them: tags out, entities read, one paragraph.
        text = _strip_tags(_SKIPPED_BLOCK.sub(" ", _COMMENT.sub(" ", raw)))
        return " ".join(html_module.unescape(text).split())
    paragraphs = (" ".join("".join(parts).split()) for parts in parser.paragraphs)
    return "\n\n".join(p for p in paragraphs if p)


def abstract_teaser(text: str) -> tuple[str, bool]:
    """The part of a sanitised abstract shown inline, and whether more follows.

    The first paragraph when it is short; else the text up to the last sentence
    end within ``CONTEXT_TEASER`` characters (a full stop after a number, a
    single letter or a known abbreviation ends none); else up to the last word
    boundary, marked with an ellipsis."""
    paragraphs = text.split("\n\n")
    first = paragraphs[0]
    if len(first) <= CONTEXT_TEASER:
        return first, len(paragraphs) > 1
    cut = None
    for match in _SENTENCE_END.finditer(first, 0, CONTEXT_TEASER + 1):
        before = first[: match.start()]
        token = before.rsplit(None, 1)[-1].lstrip(_OPENERS) if before.strip() else ""
        if token.isdigit() or len(token) <= 1 or "." in token or token.casefold() in _ABBREVIATIONS:
            continue
        cut = match.end()
    if cut is not None:
        return first[:cut], True
    space = first.rfind(" ", 0, CONTEXT_TEASER)
    return first[: space if space > 0 else CONTEXT_TEASER].rstrip() + " …", True


def committee_genitive(name: str) -> str | None:
    """``des`` + the genitive of a committee's name, as DIP spells it:
    "Haushaltsausschuss" is "des Haushaltsausschusses", "Auswärtiger
    Ausschuss" "des Auswärtigen Ausschusses", "Ältestenrat" "des
    Ältestenrates". The head noun is the first word ending in -ausschuss,
    -rat or -ium; before it only an ordinal or an -er adjective may stand.
    Any other shape (a feminine noun, a Fraktion) is None, never a guess."""
    words = str(name or "").split()
    for index, word in enumerate(words):
        lower = word.casefold()
        if lower.endswith(("ausschuss", "rat")):
            head = word + "es"
        elif lower.endswith("ium"):
            head = word + "s"
        else:
            continue
        before = []
        for prefix in words[:index]:
            if prefix.rstrip(".").isdigit() and prefix.endswith("."):
                before.append(prefix)
            elif prefix.endswith("er"):
                before.append(prefix[:-2] + "en")
            else:
                return None
        return " ".join(["des", *before, head, *words[index + 1:]])
    return None


def join_with_und(parts: list[str]) -> str:
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " und " + parts[-1]
