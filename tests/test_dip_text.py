from __future__ import annotations

import time
import unittest

import _support  # noqa: F401
from dip_text import CONTEXT_TEASER, MAX_ABSTRACT_CHARS, abstract_teaser, abstract_text, committee_genitive


class AbstractTextTests(unittest.TestCase):
    """dip_text.abstract_text: DIP abstract HTML to plain paragraphs (F7)."""

    # Value: protects=DIP abstract markup (<br />\r\n runs, <strong>, nested or unclosed tags, entities, a <script>) becomes plain paragraphs the caller can escape; fails_when=the sanitizer is a regex that misses nesting or keeps script text, or <br> runs collapse into one paragraph; why_new=no abstract was stored or shown before B4; seam=none
    def test_the_table(self) -> None:
        cases = [
            (None, ""),
            ("", ""),
            ("  Ein Satz.  ", "Ein Satz."),
            ("Erster Absatz<br />\r\n<br />\r\nZweiter", "Erster Absatz\n\nZweiter"),
            ("Eins<br>Zwei<BR/>Drei", "Eins\n\nZwei\n\nDrei"),
            ("Zeile\r\nweiter  im\tText", "Zeile weiter im Text"),
            ("<strong>Beschlussempfehlung:</strong> Annahme", "Beschlussempfehlung: Annahme"),
            ("<strong>fett <a href='x'>und <em>tief</em></a></strong> verschachtelt", "fett und tief verschachtelt"),
            ("&quot;Zitat&quot; &ndash; &bdquo;so&ldquo; &#39;x&#39; &amp;lt;", "\"Zitat\" – „so“ 'x' &lt;"),
            ("Vor<script>alert(1)</script>nach<style>p{}</style>", "Vornach"),
            ("<div>Block eins</div><div>Block zwei</div>", "Block eins\n\nBlock zwei"),
            ("offen <strong>nie geschlossen", "offen nie geschlossen"),
            ("a < b und c > d", "a < b und c > d"),
            ("Ende<br />\r\n", "Ende"),
        ]
        for raw_text, expected in cases:
            with self.subTest(raw=raw_text):
                self.assertEqual(abstract_text(raw_text), expected)

    # Value: protects=markup html.parser cannot read (a bad marked section, an unclosed <script>) still yields the abstract's words as one plain paragraph; fails_when=the AssertionError escapes and stops the build, or an unclosed <script> swallows the rest of the text; why_new=the table only has markup the parser reads; seam=none; no_claim=no such abstract occurs in the reference cache (0 of 3,922)
    def test_markup_the_parser_cannot_read_keeps_its_words(self) -> None:
        cases = [
            ("Vor <![oops]> nach &amp; mehr", "Vor nach & mehr"),
            ("<p>Eins</p> <script>zwei", "Eins\n\nzwei"),
            # A closed <script> or <style> loses its text; an unclosed one is a plain tag and the text after it stays.
            ("<style>p{}</style>Eins <SCRIPT>x()</script ><![oops]> zwei", "Eins zwei"),
            # A "<" that opens no tag is text, not the start of one.
            ("a < b und c > d <![oops]>", "a < b und c > d"),
        ]
        for raw_text, expected in cases:
            with self.subTest(raw=raw_text):
                self.assertEqual(abstract_text(raw_text), expected)

    # Value: protects=on the fallback a ">" inside a quoted attribute or a comment does not end the tag, so no attribute or comment text reaches the page; fails_when=the fallback's tag pattern stops at the first ">" or comments are not stripped first; why_new=the fallback cases had no quoted ">" and no comment; seam=none; no_claim=no such abstract occurs in the reference cache (0 of 3,922 take the fallback)
    def test_the_fallback_keeps_quoted_and_commented_text_out(self) -> None:
        cases = [
            ('vor <a title=">GEHEIM">sichtbar</a> <![oops]>', "vor sichtbar"),
            ("vor <a title='>GEHEIM'>sichtbar</a> <![oops]>", "vor sichtbar"),
            ("x <!-- a > b --> y <![oops]>", "x y"),
            ("x <!-- a\n> b\n--> y <!-- c --> z <![oops]>", "x y z"),
            ("x <![oops]> y <!-- nie > geschlossen", "x y geschlossen"),  # an unclosed comment ends at its first ">"
        ]
        for raw_text, expected in cases:
            with self.subTest(raw=raw_text):
                self.assertEqual(abstract_text(raw_text), expected)

    # Value: protects=unclosed quotes in tags on the fallback cost linear time, not a hang; fails_when=the tag scan backtracks or restarts at every "<" (a regex took 61 s on 20,000 unclosed tags); why_new=quoted values are new to the fallback; seam=none
    def test_unclosed_quotes_on_the_fallback_return_quickly(self) -> None:
        for raw in ('<![oops]> <a title="' + "x" * 100_000, "<![oops]> " + '<a title="' * 20_000):
            with self.subTest(size=len(raw)):
                started = time.perf_counter()
                abstract_text(raw)
                # gstack-timing-ok: the bound is the contract; a backtracking scan takes seconds, the linear one milliseconds
                self.assertLess(time.perf_counter() - started, 0.5)


    # Value: protects=a numeric character reference too long for int() reads as U+FFFD instead of stopping persist and every render; fails_when=html.unescape or html.parser sees the raw reference (ValueError past 4,300 digits); why_new=Codex adversarial review, B4 ship run 2; seam=none
    def test_an_overlong_character_reference_reads_as_a_replacement_character(self) -> None:
        for raw in ("Vor &#" + "1" * 5000 + "; nach", "<p>Vor &#x" + "f" * 5000 + " nach</p>", "<![oops]> Vor &#" + "9" * 5000 + "; nach"):
            with self.subTest(raw=raw[:12]):
                self.assertEqual(abstract_text(raw), "Vor \ufffd nach")
        self.assertEqual(abstract_text("A &#228; &#x1F600;"), "A \u00e4 \U0001f600")

    # Value: protects=a valid numeric character reference padded with leading zeros still reads as its character; fails_when=_OVERLONG_CHARREF counts the zeros as digits (0* backtracks) and replaces "&#x0000041;" with U+FFFD; why_new=the guard tests only use references past U+10FFFF; seam=none; no_claim=none
    def test_a_zero_padded_valid_character_reference_still_reads_as_its_character(self) -> None:
        for raw, char in (("&#x0000041;", "A"), ("&#00000065;", "A"), ("&#x00000000041", "A"), ("&#x0000e4;", "\u00e4")):
            with self.subTest(raw=raw):
                self.assertEqual(abstract_text(f"Vor {raw} nach"), f"Vor {char} nach")
        self.assertEqual(abstract_text("&#x0000110000; &#000099999999;"), "\ufffd \ufffd")

    # Value: protects=a decimal reference padded with thousands of zeros reads as its character instead of raising; fails_when=leading zeros reach int() again, which counts them toward its 4,300-digit limit and stops persist and render; why_new=e3028b2 let them through (B4 ship run 3 review); seam=none; no_claim=none
    def test_thousands_of_leading_zeros_do_not_raise(self) -> None:
        self.assertEqual(abstract_text("Vor &#" + "0" * 5000 + "65; nach"), "Vor A nach")
        self.assertEqual(abstract_text("Vor &#x" + "0" * 5000 + "41; nach"), "Vor A nach")
        self.assertEqual(abstract_text("Vor &#" + "0" * 5000 + "99999999; nach"), "Vor \ufffd nach")
        self.assertEqual(abstract_text("<p title='&#" + "0" * 5000 + "1;'>Vor nach</p>"), "Vor nach")
        self.assertEqual(abstract_text("<![oops]> Vor &#" + "0" * 5000 + "65; nach"), "Vor A nach")

    # Value: protects=only the first MAX_ABSTRACT_CHARS characters are read, so markup the parser handles in quadratic time stays bounded; fails_when=the cap goes and a 64 KB unclosed "<script " run stalls persist; why_new=Claude and Codex adversarial review, B4 ship run 2; seam=none
    def test_only_the_first_max_abstract_chars_are_read(self) -> None:
        self.assertEqual(abstract_text("a" * MAX_ABSTRACT_CHARS + "b" * 50), "a" * MAX_ABSTRACT_CHARS)
        self.assertGreater(MAX_ABSTRACT_CHARS, 5111)  # the longest abstract on the reference cache

    # Value: protects=the MAX_ABSTRACT_CHARS cut never leaves a cut tag or entity ("<a hr", "&am") as visible text; fails_when=the slice is parsed as is, or the trim treats a ">" inside a quoted attribute as the tag's end; why_new=B4 review edge 15 (2026-10-23); seam=none; no_claim=no reference abstract reaches the cut (longest 5,111)
    def test_the_cut_drops_a_tag_or_entity_it_splits(self) -> None:
        def kept(tail: str, cut_after: int) -> str:
            # tail placed so that the cut falls after its first cut_after characters
            return "a" * (MAX_ABSTRACT_CHARS - cut_after) + tail

        filler = lambda cut_after: "a" * (MAX_ABSTRACT_CHARS - cut_after)  # noqa: E731
        cases = [
            (kept('<a href="x">y</a>', 6), filler(6)),  # "<a hre"
            (kept(" &ndash; x", 4), filler(4)),  # " &nd"
            (kept(" &#x41; x", 5), filler(5)),  # " &#x4"
            (kept('<a t="x>y" href="z">w</a>', 12), filler(12)),  # quoted ">" does not close it
            (kept('<a t="x" href="y&amp;z">w</a>', 20), filler(20)),  # entity inside the cut tag
            (kept(" b<", 3) + "p>c", filler(3) + " b"),  # "<" as the last character
            (kept(" &amp; c", 6), filler(6) + " &"),  # a whole reference before the cut stays
            (kept(" b<br>c", 7), filler(7) + " b\n\nc"),  # a closed tag before the cut stays
            (kept(" b & c", 4), filler(4) + " b &"),  # "&" then a space: no reference to split
        ]
        for raw_text, expected in cases:
            with self.subTest(tail=raw_text[MAX_ABSTRACT_CHARS - 20 : MAX_ABSTRACT_CHARS + 4]):
                self.assertEqual(abstract_text(raw_text), expected)

    # Value: protects=the cut drops only the tag it splits, never text before it; fails_when=a "<" that never closes, or one inside a closed tag's quoted attribute, is taken for the split tag and everything after it goes; why_new=code review 2026-10-31: "if a<b then …" past the cut came back as "if a" (4 of 10,000 characters); seam=none
    def test_the_cut_keeps_a_lone_or_quoted_angle_bracket(self) -> None:
        lone = "if a<b then " + "x " * 6000
        self.assertEqual(abstract_text(lone), " ".join(lone[:MAX_ABSTRACT_CHARS].split()))
        quoted = '<a title="x<y">text ' + "z" * MAX_ABSTRACT_CHARS
        self.assertEqual(abstract_text(quoted), "text " + "z" * (MAX_ABSTRACT_CHARS - 20))

    # Value: protects=an apostrophe in a tag name or comment before the cut never pairs with one past it; fails_when=the trim reads every quote in a tag as a value quote and drops the whole abstract from that tag; why_new=/ship red team 2026-10-31: 0 characters left where main kept 9,981; seam=none; no_claim=no reference abstract reaches the cut (longest 5,111)
    def test_an_apostrophe_in_a_tag_or_comment_keeps_the_abstract(self) -> None:
        apostrophe = "'"
        past_cut = "x " * 6000 + "don" + apostrophe + "t>"
        comment = "<!-- it" + apostrophe + "s -->"
        raw = comment + "Anfang " + past_cut
        self.assertEqual(abstract_text(raw), " ".join(raw[len(comment) : MAX_ABSTRACT_CHARS].split()))
        tag = "<b it" + apostrophe + "s>fett</b>"
        raw = tag + " " + past_cut
        self.assertEqual(abstract_text(raw), " ".join(("fett" + raw[len(tag) : MAX_ABSTRACT_CHARS]).split()))

    # Value: protects=a comment is read to its "-->" as html.parser reads it; fails_when=the trim ends a comment at an inner ">" and keeps a comment the cut splits, or drops the text after a comment that never closes; why_new=the comment rule added with the apostrophe fix (/ship 2026-10-31); seam=none; no_claim=no reference abstract reaches the cut
    def test_the_cut_reads_a_comment_to_its_end(self) -> None:
        filler = "a" * (MAX_ABSTRACT_CHARS - 10)
        self.assertEqual(abstract_text(filler + "<!-- a > b --> c"), filler)  # cut after "<!-- a > ", inside the comment
        unclosed = "vor <!-- offen " + "x " * 6000
        self.assertEqual(abstract_text(unclosed), " ".join(unclosed[:MAX_ABSTRACT_CHARS].split()))

    # Value: protects=an abstract shorter than the cut is read exactly as before; fails_when=the trim runs on every abstract and drops a trailing "<" or "&" that is text; why_new=B4 review edge 15 trim; seam=none
    def test_an_abstract_within_the_limit_is_not_trimmed(self) -> None:
        self.assertEqual(abstract_text("a < b &"), "a < b &")
        self.assertEqual(abstract_text("Ende <a hr"), "Ende <a hr")

    # Value: protects=a "<" whose tag, comment, declaration or processing instruction never closes reads as text on every Python; fails_when=html.parser's 2025 end-of-input rule (3.11.13, 3.12.11, 3.13.4) drops "<a hr" and swallows "<!-- x" while older patch releases keep both; why_new=CI on PR #120 failed on newer patch releases while local 3.13.2 passed; seam=none
    def test_markup_that_never_closes_is_text_on_every_python(self) -> None:
        for raw in ["x </a hr", "x <!x", "x <?pi", "vor <!-- offen", "a <b> c <d e"]:
            with self.subTest(raw=raw):
                self.assertEqual(abstract_text(raw), raw.replace("<b> ", ""))
        # A marked section ("<![...>") ends at its first ">" and reads as a space, the same on every Python.
        self.assertEqual(abstract_text("a<![CDATA[ x ]]>b <p>c"), "a b\n\nc")
        self.assertEqual(abstract_text("x <![CDATA[ y"), "x <![CDATA[ y")
        # A comment ends at its first "-->" on every Python; newer releases also end one at "--!>" or "<!-->".
        self.assertEqual(abstract_text("a <!-- x --!> y --> b"), "a b")
        self.assertEqual(abstract_text("a <!--> b --> c"), "a c")
        # A comment still parts the text: no entity spliced across it, a marked section inside it stays a comment.
        self.assertEqual(abstract_text("&am<!-- x -->p;"), "&amp;")
        self.assertEqual(abstract_text("a<!--[if mso]><![endif]-->b<p>c"), "ab\n\nc")

    # Value: protects=where markup ends is this module's rule, not html.parser's, so the text is the same on every Python; fails_when=a shape here reads differently on 3.11, 3.13.2 or the newest patch release (quotes in end tags, "<?...>" and "<!...>", "=" or a quote inside an unquoted value, a script body holding "<"); why_new=B4 review items 2 and 19 (2026-10-31); seam=none; no_claim=none
    def test_markup_ends_by_this_modules_rule_on_every_python(self) -> None:
        cases = [
            ('a </p class="x> b', "a\n\nb"),  # an end tag ends at its first ">", quote or not
            ('a </p class="x> b "> c', 'a\n\nb "> c'),
            ("a </ p>b", "a b"),  # "</" and a space opens no end tag, only a bogus comment
            ('a <?pi x="y> b', "a b"),
            ('a <!x y="z> b', "a b"),
            ('<b data=x=">A b">', 'A b">'),  # a quote inside an unquoted value is part of the value
            ('<b a=="x>y">z', "z"),  # a quote after "=" and spaces opens a value
            ("<b a = 'x>y' c=d>z", "z"),
            ("<b it's>z</b it's>w", "zw"),
            ("x<script>if(a<b)y()</script >z", "xz"),
            ("x<style>a>b{}</STYLE\n>z", "xz"),
            ("x GmbH&C", "x GmbH&C"),
            ("x<br/>y<br class='a'/>z", "x\n\ny\n\nz"),
            ("x<script/>y</script>z", "xyz"),  # a self-closing <script/> opens no block; the later </script> is a stray end tag
        ]
        for raw_text, expected in cases:
            with self.subTest(raw=raw_text):
                self.assertEqual(abstract_text(raw_text), expected)

    # Value: protects=a tag-like construct holding '="' before the cut with a quote after it still ends at its first ">" (end tag, processing instruction, declaration) and the abstract survives the cut; fails_when=the trim reads the quote as a value quote and drops the rest as one tag (end tag: 6 characters left, main kept 9,987); why_new=B4 review item 19 (2026-10-31); seam=none; no_claim=no reference abstract reaches the cut
    def test_the_cut_keeps_the_abstract_after_a_construct_with_a_quote(self) -> None:
        cases = [
            ("end tag", 'Anfang </p class="x>', "Anfang\n\n"),
            ("processing instruction", 'Anfang <?pi x="y>', "Anfang "),
            ("declaration", 'Anfang <!x y="z>', "Anfang "),
        ]
        for name, prefix, head in cases:
            with self.subTest(construct=name):
                raw = prefix + " " + "wort " * 3000 + 'ende "> z'
                self.assertEqual(abstract_text(raw), head + " ".join(raw[len(prefix) : MAX_ABSTRACT_CHARS].split()))

    # Value: protects=a quote after "=" inside an unquoted value opens no quoted value, so the tag ends at its first ">" and the abstract survives; fails_when=the quote pairs with one past the cut (0 characters left, main kept 9,988); why_new=B4 review item 19; seam=none; no_claim=no reference abstract reaches the cut
    def test_the_cut_keeps_the_abstract_after_a_quote_inside_an_unquoted_value(self) -> None:
        prefix = '<b data=x=">'
        raw = prefix + "Anfang " + "wort " * 2500 + '">'
        self.assertEqual(abstract_text(raw), " ".join(raw[len(prefix) : MAX_ABSTRACT_CHARS].split()))

    # Value: protects=a trailing "&" and letters that read whole are no character reference stay; one that is a reference the cut splits goes; fails_when=any "&" plus letters at the cut is dropped as partial (GmbH&Co. kept GmbH), or a real reference is shown cut; why_new=B4 review item 19; seam=none; no_claim=no reference abstract reaches the cut
    def test_the_cut_drops_only_a_real_character_reference(self) -> None:
        def filler(cut_after: int) -> str:
            return "a" * (MAX_ABSTRACT_CHARS - cut_after)

        cases = [
            (filler(6) + "GmbH&Co. x", filler(6) + "GmbH&C"),  # cut after "&C": "&Co." is no reference
            (filler(6) + "GmbH&Copf; x", filler(6) + "GmbH"),  # "&Copf;" is one
            (filler(8) + "GmbH&ampx", filler(8) + "GmbH&"),  # cut after "&amp": that reads whole as "&" and "x"
            (filler(7) + "GmbH&#65x", filler(7) + "GmbH"),  # the cut falls inside "&#65"
        ]
        for raw_text, expected in cases:
            with self.subTest(tail=raw_text[MAX_ABSTRACT_CHARS - 12 :]):
                self.assertEqual(abstract_text(raw_text), expected)

    # Value: protects=the cut scans a bounded window, not the whole raw abstract, so persist and render stay fast on a huge one; fails_when=the tag scan reads every character of a 2-million-character abstract (about 2 s and 16 MB); why_new=B4 review item 19; seam=none
    def test_a_huge_abstract_is_read_in_bounded_time(self) -> None:
        for raw in ("x " * 1_000_000, '<a title="' * 200_000, "<p>" * 700_000, "&" * 2_000_000):
            with self.subTest(raw=raw[:12]):
                started = time.perf_counter()
                text = abstract_text(raw)
                # gstack-timing-ok: the bound is the contract; reading the whole text takes seconds, the window milliseconds
                self.assertLess(time.perf_counter() - started, 0.5)
                self.assertLessEqual(len(text), MAX_ABSTRACT_CHARS)

    # Value: protects=a comment is dropped whole when the cut splits it, even where a newer Python would have ended it earlier at "--!>" or "<!-->"; fails_when=the comment rule follows the running Python, so the same text is cut at different places; why_new=B4 review item 19 (comment rule tied to 3.13.2); seam=none; no_claim=no reference abstract reaches the cut
    def test_the_cut_reads_a_comment_by_the_same_rule_on_every_python(self) -> None:
        filler = "a" * (MAX_ABSTRACT_CHARS - 7)  # the cut falls after the comment's first 7 characters
        for comment in ("<!-- a --!> b --> c", "<!--> b --> c", "<!---> b --> c"):
            with self.subTest(comment=comment):
                self.assertEqual(abstract_text(filler + comment), filler)

    # Value: protects=a tag that starts before the cut and has no end in the scanned window is dropped, so a cut tag never shows as text; fails_when=the window ends before the tag does and its start stays as visible "<a hr..."; why_new=B4 review item 19; seam=none; no_claim=no reference abstract reaches the cut
    def test_the_cut_drops_a_tag_that_ends_beyond_the_window(self) -> None:
        filler = "a" * (MAX_ABSTRACT_CHARS - 6)
        raw = filler + '<a title="' + "x" * 5000 + '">y</a>'
        self.assertEqual(abstract_text(raw), filler)
        # Far before the cut, a "<" that never ends is text, as in an abstract that fits.
        far = "<a title=" + "x " * 5000 + "y"
        self.assertEqual(abstract_text(far), " ".join(far[:MAX_ABSTRACT_CHARS].split()))


class AbstractTeaserTests(unittest.TestCase):
    def test_a_short_first_paragraph_is_the_teaser(self) -> None:
        self.assertEqual(abstract_teaser("Kurz.\n\nZweiter Absatz."), ("Kurz.", True))
        self.assertEqual(abstract_teaser("Kurz."), ("Kurz.", False))

    def test_a_long_paragraph_is_cut_at_a_sentence_not_at_an_abbreviation(self) -> None:
        first = "Änderung des § 5 Abs. 2 Nr. 3 und Art. 1 z. B. bei Renten. " + "Weiterer Satz mit Inhalt. " * 20
        teaser, more = abstract_teaser(first.strip())
        self.assertTrue(more)
        # The last whole sentence within the limit: nine more after the first.
        self.assertEqual(teaser, "Änderung des § 5 Abs. 2 Nr. 3 und Art. 1 z. B. bei Renten. " + "Weiterer Satz mit Inhalt. " * 8 + "Weiterer Satz mit Inhalt.")
        self.assertLessEqual(len(teaser), CONTEXT_TEASER)
        # "Abs.", "Nr. 3", "Art. 1" and "z. B." end no sentence.
        self.assertEqual(abstract_teaser("Nach § 5 Abs. 2 Nr. 3 z. B. gilt " + "x" * 300)[0], "Nach § 5 Abs. 2 Nr. 3 z. B. gilt …")

    def test_without_a_sentence_end_it_is_cut_at_a_word_with_an_ellipsis(self) -> None:
        teaser, more = abstract_teaser("wort " * 100)
        self.assertTrue(more)
        self.assertTrue(teaser.endswith("wort …"))
        self.assertLessEqual(len(teaser), CONTEXT_TEASER + 2)

    # Value: protects=a first paragraph with no space inside the limit (one long token, e.g. a URL) is cut at the limit with an ellipsis, not emptied; fails_when=the word-boundary cut takes rfind's -1 as an index, leaving a teaser of one character; why_new=the table only has paragraphs with spaces; seam=none
    def test_a_single_long_token_is_cut_at_the_limit(self) -> None:
        teaser, more = abstract_teaser("x" * (CONTEXT_TEASER + 50))
        self.assertTrue(more)
        self.assertEqual(teaser, "x" * CONTEXT_TEASER + " …")

    # Value: protects=an abbreviation behind an opening bracket or quote ("(Abs.", "„Art.", "[Nr.") ends no sentence, so the teaser is not cut there; fails_when=the token keeps its "(" and misses _ABBREVIATIONS; why_new=B4 review edge 4 (2026-10-22); seam=none
    def test_an_abbreviation_after_a_bracket_or_quote_ends_no_sentence(self) -> None:
        for opener in ("(Abs.", "„Art.", "[Nr.", "(vgl."):
            with self.subTest(opener=opener):
                teaser, more = abstract_teaser(f"Die Regel gilt nach § 5 {opener} 2) " + "wort " * 80)
                self.assertTrue(more)
                self.assertTrue(teaser.endswith("wort …"), teaser)
        # A real sentence end before the bracket is still where it cuts.
        teaser, _ = abstract_teaser("Erster Satz. Nach § 5 (Abs. 2) " + "wort " * 80)
        self.assertEqual(teaser, "Erster Satz.")


REFERENCE_URHEBER = (
    # Every Beschlussempfehlung urheber on the reference store (2026-10-20).
    "Petitionsausschuss", "Haushaltsausschuss", "Finanzausschuss", "Auswärtiger Ausschuss",
    "Ausschuss für Inneres und Heimat", "Ausschuss für Klimaschutz und Energie", "Rechtsausschuss",
    "Ausschuss für Arbeit und Soziales", "Wirtschaftsausschuss", "Ausschuss für Gesundheit", "Verkehrsausschuss",
    "Ausschuss für Ernährung und Landwirtschaft", "Ausschuss für Wohnen, Stadtentwicklung, Bauwesen und Kommunen",
    "Ausschuss für Wirtschaft und Energie", "Ausschuss für Umwelt, Naturschutz, nukleare Sicherheit und Verbraucherschutz",
    "Innenausschuss", "Ausschuss für Bildung, Forschung und Technikfolgenabschätzung",
    "Ausschuss für Umwelt, Klimaschutz, Naturschutz und nukleare Sicherheit", "Ausschuss für Recht und Verbraucherschutz",
    "Verteidigungsausschuss", "Ausschuss für wirtschaftliche Zusammenarbeit und Entwicklung",
    "Ausschuss für Familie, Senioren, Frauen und Jugend", "Ausschuss für Wahlprüfung, Immunität und Geschäftsordnung",
    "Ausschuss für Landwirtschaft, Ernährung und Heimat", "Ausschuss für Kultur und Medien", "Sportausschuss",
    "Ausschuss für Digitales", "Vermittlungsausschuss", "Ältestenrat", "Ausschuss für Menschenrechte und humanitäre Hilfe",
    "Ausschuss für Digitales und Staatsmodernisierung", "Wahlprüfungsausschuss",
    "Ausschuss für die Angelegenheiten der Europäischen Union", "Ausschuss für Bildung, Familie, Senioren, Frauen und Jugend",
    "Ausschuss für Tourismus", "Ausschuss für Sport und Ehrenamt",
    "Bundesministerium für Umwelt, Naturschutz, nukleare Sicherheit und Verbraucherschutz",
    "Ausschuss für Forschung, Technologie, Raumfahrt und Technikfolgenabschätzung",
    "2. Untersuchungsausschuss", "1. Untersuchungsausschuss",
)


class CommitteeGenitiveTests(unittest.TestCase):
    def test_known_shapes(self) -> None:
        self.assertEqual(committee_genitive("Haushaltsausschuss"), "des Haushaltsausschusses")
        self.assertEqual(committee_genitive("Auswärtiger Ausschuss"), "des Auswärtigen Ausschusses")
        self.assertEqual(committee_genitive("Ausschuss für Inneres und Heimat"), "des Ausschusses für Inneres und Heimat")
        self.assertEqual(committee_genitive("Ältestenrat"), "des Ältestenrates")
        self.assertEqual(committee_genitive("1. Untersuchungsausschuss"), "des 1. Untersuchungsausschusses")
        self.assertEqual(
            committee_genitive("Bundesministerium für Umwelt, Naturschutz, nukleare Sicherheit und Verbraucherschutz"),
            "des Bundesministeriums für Umwelt, Naturschutz, nukleare Sicherheit und Verbraucherschutz",
        )

    def test_every_reference_urheber_inflects(self) -> None:
        for name in REFERENCE_URHEBER:
            with self.subTest(name=name):
                genitive = committee_genitive(name)
                self.assertIsNotNone(genitive)
                self.assertTrue(genitive.startswith("des "))
                self.assertRegex(genitive, r"(ausschusses|Ausschusses|rates|iums)\b")

    def test_an_unknown_shape_is_not_guessed(self) -> None:
        for name in ("Bundesregierung", "Fraktion der SPD", ""):
            with self.subTest(name=name):
                self.assertIsNone(committee_genitive(name))


if __name__ == "__main__":
    unittest.main()
