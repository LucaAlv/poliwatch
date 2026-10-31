"""DIP fields as German display text.

DIP gives an abstract as HTML and a committee as a bare name; this module turns
them into the text a page shows: plain abstract paragraphs and their teaser, and
a committee's name in the genitive. It does no I/O and escapes nothing (the
caller escapes the result).
"""

from __future__ import annotations

import html as html_module
import re
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
#: Raw abstract characters read; the longest on the reference cache has 5,111.
MAX_ABSTRACT_CHARS = 10_000
#: How far past the cut a tag, comment or character reference is followed to see
#: where it ends, and how far before the cut a tag with no end in sight still
#: counts as one the cut splits.
CUT_LOOKAHEAD = 2_000
# A numeric character reference past U+10FFFF names no character; with more than
# 4,300 digits html.unescape raises instead of reading it as U+FFFD; int() counts
# leading zeros as digits, so they go first: "&#x0000041;" is "A".
_CHARREF_ZEROS = re.compile(r"&#(?:([xX])0+(?=[0-9a-fA-F])|0+(?=[0-9]))")
_OVERLONG_CHARREF = re.compile(r"&#(?:[xX][0-9a-fA-F]{7,}|[0-9]{8,});?")
_PARTIAL_CHARREF = re.compile(r"&#?[0-9A-Za-z]*\Z")
_CHARREF_AT = re.compile(r"&#?[0-9A-Za-z]*;?")
# Markup: "<" and a letter, "!", "/" or "?".
_MARKUP_OPEN = re.compile(r"<[!/?A-Za-z]")
_TAG_NAME = re.compile(r"[A-Za-z][^\t\n\r\f />\x00]*")
_SKIPPED_CLOSE = re.compile(r"</(?:script|style)[\t\n\r\f />]", re.IGNORECASE)
#: A ``<br>`` or a block element, opened or closed, ends a paragraph.
_BREAKS = frozenset({"br", "p", "div", "li", "ul", "ol", "tr", "h1", "h2", "h3", "h4", "h5", "h6"})
#: ``<script>`` and ``<style>`` go with their text.
_SKIPPED = frozenset({"script", "style"})
_SPACE = " \t\n\r\f"


def _tag_ends(text: str) -> list[int]:
    """ends[i]: where the start tag whose name begins at ``text[i]`` ends (just past
    its ">"); -1 if it never ends. One right-to-left pass, so linear however many
    quotes or "<" the text holds. Attributes read as html.parser's current releases
    read them, so every Python agrees: a quote opens a value only as the first
    character after "=" and spaces; an unquoted value runs to a space or ">" and
    holds any "=" or quote ("<b data=x=\\">" ends at its first ">"); a quote in a
    name ("<b it's>") is a letter."""
    size = len(text)
    # Four states a character can find the tag in: name, between attributes,
    # after "=", inside an unquoted value.
    name, attr, value, bare = ([-1] * (size + 1) for _ in range(4))
    for i in range(size - 1, -1, -1):
        char = text[i]
        if char == ">":
            name[i] = attr[i] = value[i] = bare[i] = i + 1
            continue
        space = char in _SPACE
        name[i] = attr[i + 1] if space or char == "/" else name[i + 1]
        attr[i] = value[i + 1] if char == "=" else attr[i + 1]
        if space or char == "=":
            value[i] = value[i + 1]
        elif char in "\"'":
            quote_end = text.find(char, i + 1)
            value[i] = attr[quote_end + 1] if quote_end != -1 else -1
        else:
            value[i] = bare[i + 1]
        bare[i] = attr[i + 1] if space else bare[i + 1]
    return name


def _read_text(run: str) -> str:
    """One run of text between markup, character references read."""
    run = _CHARREF_ZEROS.sub(lambda match: "&#" + (match.group(1) or ""), run)
    return html_module.unescape(_OVERLONG_CHARREF.sub("�", run))


def _cut_run(text: str, start: int, cut: int) -> str:
    """The text run ``text[start:cut]`` read, less a character reference the cut
    splits ("&am" before "p;"). A trailing "&" and name characters stay when read
    whole they are no reference (``GmbH&Co.``)."""
    run = text[start:cut]
    partial = _PARTIAL_CHARREF.search(run)
    if partial:
        whole = _CHARREF_AT.match(text, start + partial.start()).group()
        if not _read_text(whole).startswith(_read_text(partial.group())):
            run = run[: partial.start()]
    return _read_text(run)


def _markup_end(text: str, i: int, ends: list[int]) -> tuple[int, str | None, str]:
    """(end, name, kind) of the markup opening at ``text[i]``, end just past it, or
    end -1 if it never ends and so stays text. kind is "tag", "end" (end tag),
    "comment" or "other"; name is a tag's lowercased name. A comment ends at its
    first "-->" on every Python (newer releases also end one at "--!>" or "<!-->");
    an end tag, "<?...>" and "<!...>" at their first ">"; a start tag as
    ``_tag_ends`` reads it."""
    if text.startswith("<!--", i):
        end = text.find("-->", i + 4)
        if end != -1:
            return end + 3, None, "comment"
    if text[i + 1] in "!/?":
        end = text.find(">", i)
        if end == -1:
            return -1, None, "other"
        match = _TAG_NAME.match(text, i + 2) if text[i + 1] == "/" else None
        return end + 1, match.group().lower() if match else None, "end" if match else "other"
    end = ends[i + 1]
    match = _TAG_NAME.match(text, i + 1)
    return end, match.group().lower(), "tag"


def _paragraphs(text: str, cut: int, truncated: bool) -> list[list[str]]:
    """The paragraphs of ``text[:cut]`` as runs of read text. ``text`` is the
    abstract, or when ``truncated`` its first ``cut`` + ``CUT_LOOKAHEAD``
    characters: a tag, comment or ``<script>`` block that starts before the cut and
    ends after it is dropped; so is one with no end in the text that starts
    within ``CUT_LOOKAHEAD`` before the cut, which may end beyond it."""
    paragraphs: list[list[str]] = [[]]
    ends = _tag_ends(text)
    pos = 0
    for match in _MARKUP_OPEN.finditer(text):
        i = match.start()
        if i < pos:
            continue
        if i >= cut:
            break
        end, name, kind = _markup_end(text, i, ends)
        if kind == "tag" and name in _SKIPPED and end != -1 and text[end - 2] != "/":
            close = _SKIPPED_CLOSE.search(text, end)
            close_end = text.find(">", close.end() - 1) if close else -1
            # An unclosed <script> is a plain tag: the rest stays text.
            kind, end = ("block", close_end + 1) if close_end != -1 else (kind, end)
        if end == -1:
            if not truncated or i < cut - CUT_LOOKAHEAD:
                continue  # "<" that opens nothing: text
            end = len(text) + 1  # may end past the window, so past the cut
        paragraphs[-1].append(_read_text(text[pos:i]))
        if end > cut:
            return paragraphs
        if (kind in ("tag", "end") and name in _BREAKS):
            paragraphs.append([])
        elif text.startswith("<![", i):
            paragraphs[-1].append(" ")
        pos = end
    paragraphs[-1].append(_cut_run(text, pos, cut) if truncated else _read_text(text[pos:cut]))
    return paragraphs


def abstract_text(raw: Any) -> str:
    """A DIP abstract as plain text: paragraphs separated by a blank line (``\n\n``),
    whitespace inside a paragraph collapsed to single spaces, entities unescaped,
    markup gone. The caller escapes the result; the raw text stays in the cache.
    Read by this module's own scanner, not html.parser, whose treatment of
    malformed markup changed in 2025 (3.11.13, 3.12.11, 3.13.4): the same text
    reads alike on every Python. A "<" whose markup never ends stays text; a
    ``<script>`` or ``<style>`` that never closes is dropped as a tag only.
    Only the first ``MAX_ABSTRACT_CHARS`` characters are read, less a tag,
    comment or character reference the cut splits."""
    if not raw:
        return ""
    raw = str(raw)
    truncated = len(raw) > MAX_ABSTRACT_CHARS
    text = raw[: MAX_ABSTRACT_CHARS + CUT_LOOKAHEAD] if truncated else raw
    cut = MAX_ABSTRACT_CHARS if truncated else len(text)
    paragraphs = (" ".join("".join(parts).split()) for parts in _paragraphs(text, cut, truncated))
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
