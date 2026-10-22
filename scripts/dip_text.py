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
_TAG = re.compile(r"<[^>]*>")


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
    markup gone. The caller escapes the result; the raw text stays in the cache."""
    if not raw:
        return ""
    parser = _AbstractParser()
    try:
        parser.feed(str(raw))
        parser.close()
        malformed = parser.skipping > 0  # an unclosed <script> or <style> would swallow the rest
    except AssertionError:  # html.parser's answer to markup it cannot read, e.g. "<![oops]>"
        malformed = True
    if malformed:
        # Keep the words rather than lose them: tags out, entities read, one paragraph.
        return " ".join(html_module.unescape(_TAG.sub(" ", str(raw))).split())
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
        token = first[: match.start()].rsplit(None, 1)[-1] if first[: match.start()].strip() else ""
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
