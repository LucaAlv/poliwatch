# Reden the XML prints as two, and the longer Geschäftsordnung motions

Built 2026-11-23 from TODOS.md, "Turns DIP types otherwise: what the build of 2026-11-23 leaves open", items 1 and 2, on the owner's go of that day. Base: main 3ffd87b (v0.46.50.0), store clone `.context/quotes-after` (806 sittings, 61,137 Reden).

## 1. Split Reden

**What is wrong.** Where the chair interrupts a Rede, the WP 18 XML sometimes ends the `<rede>` and prints the rest as a new one of the same Redner. Each part counted as a Rede. In seven of them the first part stands inside the `<rede>` of the speaker before, from where `split_nested_reden` takes it as a part of its own.

**Census.** Two nets over all 806 sittings. Every pair of the first was read; of the second, the leads the first does not hold were judged by their TOPs and pages, and ten of them looked up:
1. Two consecutive stored units of one person in a TOP, in stored order: 17 pairs. 14 are Rede and Rede. 13 are split Reden. The other is 19/224 Weisgerber (`ID1922404500`, `ID1922404600`): the chair announces the second as the repetition of the Redebeitrag, so both stay (DIP lists one Rede on two pages). The three remaining pairs are a Rede and the same person's Erwiderung or Kurzintervention, rightly.
2. A person with more stored Reden in a sitting than DIP lists activities of a Rede, a Geschäftsordnung turn or the like: 35. 12 are among the 13 above (DIP lists no such activity for the 13th, 18/59 Schwesig), one is 19/224, and the others are Reden far apart: opening reports of a Befragung (ADR 0002 counts them), Reden DIP lists once, and 18/149 Haßelmann, two turns zur Geschäftsordnung. No case of a Rede, another unit and the same person's Rede again was a split. 18/191 `ID1819102000` (Veit, 249 characters) only withdraws a Wortmeldung and is left to the owner (TODOS.md).

**All 13** (all WP 18):

| Sitting | Redner | First part | Rest | Characters | Kept id |
|---|---|---|---|---|---|
| 18/11 | Karl Schiewerling | `ID1801103300:2` | `ID1801103400` | 4,633 + 4,562 | `ID1801103400` |
| 18/11 | Elisabeth Scharfenberg | `ID1801105300:2` | `ID1801105400` | 3,950 + 567 | `ID1801105400` |
| 18/21 | Dagmar Schmidt | `ID1802102800` | `ID1802103000` | 2,700 + 1,763 | `ID1802102800` |
| 18/26 | Markus Kurth | `ID1802600700:2` | `ID1802600800` | 1,432 + 5,811 | `ID1802600800` |
| 18/26 | Dirk Wiese | `ID1802602200:2` | `ID1802602300` | 2,108 + 7,755 | `ID1802602300` |
| 18/42 | Christine Buchholz | `ID1804201900` | `ID1804202100` | 3,878 + 324 | `ID1804201900` |
| 18/42 | Uwe Kekeritz | `ID1804205200` | `ID1804205400` | 7,097 + 158 | `ID1804205200` |
| 18/59 | Manuela Schwesig | `ID1805900100` | `ID1805900300` | 5,697 + 772 | `ID1805900100` |
| 18/63 | Andrea Lindholz | `ID1806305200:2` | `ID1806305300` | 2,561 + 5,985 | `ID1806305300` |
| 18/70 | Karin Binder | `ID1807005100:2` | `ID1807005200` | 1,290 + 5,447 | `ID1807005200` |
| 18/88 | Ulrich Lange | `ID1808801400` | `ID1808801600` | 5,645 + 425 | `ID1808801400` |
| 18/98 | Dr. Valerie Wilms | `ID1809801000:9` | `ID1809801100` | 5,018 + 502 | `ID1809801100` |
| 18/110 | Dr. André Hahn | `ID1811004100` | `ID1811004300` | 4,583 + 293 | `ID1811004100` |

18/59 is the opening report of a Befragung, a Rede.

**Build.** A list kind `own_words` (`scripts/reviewed_units.py`), applied by `validate_dip_protocol.join_own_words` after `split_nested_reden` and before any kind is decided: the two `<rede>` become one, and the rest is the resumption the walk reads, so a Zwischenfrage the chair offered at the end of the first part and the Redner granted at the start of the rest is read with both. The Rede keeps the first part's id. Where that part is one the parser made (`<id>:<n>`), it keeps the second `<rede>`'s, the one the Inhaltsverzeichnis and other datasets have. The Inhaltsverzeichnis gives that id the place of the rest, so the entry carries `page`, DIP's place of the Rede. It differs from the Inhaltsverzeichnis in five of the seven: 18/11 Schiewerling 731A (Inhaltsverzeichnis 731D), 18/11 Scharfenberg 753A (753D), 18/63 Lindholz 5869A (5869D), 18/70 Binder 6704A (6704C), 18/98 Wilms 9337A (9338B); 18/26 Kurth (2013A) and Wiese (2032C) agree. The XML's page anchors bear out the pages of six; in Kurth's Rede the anchor of 2013 stands one paragraph in, so it may begin at the foot of 2012. The TOP's page range still reaches the rest (18/88 TOP 3 ends at 8283B). The part joined away has the status `own_words`. An entry whose `<rede>` does not stand directly after one of the same owner, or whose page is missing, not needed, or not between the two places the Inhaltsverzeichnis gives, stops the run. No rule is widened: the class is WP 18 only, and nothing outside the list moves.

## 2. Geschäftsordnung turns of 400 to 799 characters

The 24 bare motions of 2026-11-23 were the turns under 400 characters two blind readers agreed on. The 32 of 400 to 799 characters, stored as Reden and typed „Zur Geschäftsordnung BT“ by DIP, were read the same way: two readers, each turn in full with the chair's words before and after, shuffled, with 8 turns already decided mixed in as hidden controls (4 motions, 4 not). Both got all 8 right. Verdicts: [D](beitraege-as-reden/reading-D.tsv) and [E](beitraege-as-reden/reading-E.tsv).

- 20 turns: both say motion, both with high confidence. Listed `procedural`, like the 24.
- 5 turns: both say motion, at least one hedges. They argue a case and move at the end (19/83 `ID198305200`, 19/171 `ID1917105500`, 20/44 `ID204406300`, 20/94 `ID209406700`, 20/114 `ID2011409200`). Not listed: they stay Reden (owner, 2026-11-24).
- 2 turns: the readers differ (18/149 `ID1814901300`, 21/105 `ID2110502300`). They stay Reden.
- 5 turns: both say Rede.
