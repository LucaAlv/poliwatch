# Speakers printed as `<name>` who are not the chair

Prepares the owner decision for TODOS.md "ADR 0004 follow-ups", bullet "Speakers printed as `<name>` who are not the chair (census finding 8)". The starting point is the receipt [`t4-acquire/name-tag-speakers.tsv`](t4-acquire/name-tag-speakers.tsv) (M4 of [t4-acquire.md](t4-acquire.md)). Measured on 2026-11-20 against main v0.46.35.0 (08d1e72), read-only on the reference store `.context/dip-pulse-site`. At the time of measuring, that store held 803 XML files and 803 protocols, because the running online build had already added 18/62 and 18/90. Nothing is built here.

**Recommendation in short:** store every one of these turns as what it is (option S): a Rede or a Beitrag of the named speaker, bound by a reviewed list entry. Withholding (option W) needs the same list and the same parser work, and it would then hide about 71,000 correctly printed words.

## 1. What the source shows

### The receipt still reproduces, but undercounts

- **Reproducible.** M4's own script (`~/agent-runs/t4/measure/namelost.py`) was run again on today's store. It returns the same 131 rows: same sitting, `<rede>`, tag and word count. The two rows removed on review (20/144, 20/25) come back too, as before. 18/62 and 18/90, which are new in the store, add none.
- **The phrase test missed two whole Reden.** The receipt counts a turn as lost when 8 words from its middle appear in no table. For these two turns the 8 words are a common phrase:
  - Maas, 18/17 `ID1801701900`, 797 words: "– das halte ich für ganz wesentlich –" is also in 18/100 `ID1810001600`.
  - Haase, 18/30 `ID1803006000`, 1,082 words: "zum Schutz des Klimas und der Biodiversität im" is also in 18/122, 18/138 and 21/16.
  
  Neither turn is stored: no speech text holds its opening.
- **It leaves out short turns and everything outside a `<rede>`.** The receipt scanned only turns of 15 words or more inside another speaker's `<rede>`. Twelve shorter turns are lost the same way (consents, oath answers, own words). A second set of 25 turns, 13,008 words, is printed as a `<name>` outside any `<rede>`, loose in the Tagesordnungspunkt. That is where the TODO's Biermann, Bentele and Ramelow are, and also Wanka's two Befragung opening reports. The parser does not read text outside a `<rede>` unless it is a Fragestunde turn, so none of these words is stored.

### The population: 170 turns, 80,381 words, 141 reviewed entries

The full list is [`name-tag-speakers.tsv`](name-tag-speakers.tsv): one row per turn, read from the XML. [`name-tag-speakers/census.py`](name-tag-speakers/census.py) and [`classify.py`](name-tag-speakers/classify.py) reproduce it:

```bash
python -I docs/plans/name-tag-speakers/census.py <store> census.json
```

```bash
python -I docs/plans/name-tag-speakers/classify.py <store> census.json docs/plans/t4-acquire/name-tag-speakers.tsv docs/plans/name-tag-speakers.tsv
```

Both open SQLite with `mode=ro&immutable=1`. A turn counts as the chair's when the tag starts with a presidium role, ends with the name of someone who chairs this sitting (this catches 20/144's "Wolfgang Kubicki:"), or opens with "(". Parenthesised tags are the sibling rule's: they are stage directions, as in 20/25. An *entry* is one sitting, one host `<rede>` (or Tagesordnungspunkt) and one printed person. In every case found, all turns of one person in one host have the same kind, so one reviewed entry can cover them.

| Kind | Where | Turns | Words | Entries | In the receipt | What it is |
|---|---|---:|---:|---:|---:|---|
| `rede` | in a `<rede>` | 86 | 59,263 | 67 | 79 | A whole Rede. The chair gives the floor in Rednerliste form ("Nächste Rednerin ist …"), and the turn opens with a salutation. One entry includes the speaker's later turns in the same Rede: continuations after a chair remark, the consent to a Zwischenfrage and the answer to it. Examples: 18/30 holds 21 of these entries, in 25 turns (Pantel, Yüksel and Rainer in one host); 18/29 Krüger has 1,552 words. 18/104 `ID1810402200` is a `<rede>` that *starts* with `<name>Christian Kühn …`: it is stored today as an empty Rede bound to the placeholder person "Unbekannt", with no Fraktion or Sprechrolle. |
| `befragung_antwort` | in a `<rede>` | 33 | 6,088 | 29 | 31 | Wanka's answers in the Befragungen 18/25 and 18/35. Each sits inside the asker's `<rede>`, whose Frage is stored as `befragung_frage`. |
| `zwischenfrage` | in a `<rede>` | 17 | 1,349 | 15 | 17 | An MdB asks inside someone else's Rede, after the chair's offer and the Redner's consent. Neu asks 5 of them (in 6 turns), Müller 2. |
| `befragung_frage` | in a `<rede>` | 3 | 335 | 3 | 3 | An MdB's Frage printed inside the minister's answer `<rede>`: Kolbe in 18/19, Müller twice in 18/87. |
| `own_words` | in a `<rede>` | 3 | 308 | 3 | 1 | The host's own speaker printed as `<name>`. Hunko 18/17 loses 297 words. Ploß 19/125 loses his last 9. Pfeiffer 18/36, printed as "Jochim", loses his consent "In Ordnung.", and that is why his whole Rede is withheld today. |
| `oath_answer` | in a `<rede>` | 3 | 30 | 3 | 0 | 18/4: the oath answers of Maas, Schwesig and Wanka, 10 words each, printed inside the previous minister's listed procedural `<rede>`. |
| `rede` | outside | 14 | 12,192 | 14 | – | A whole Rede with no `<rede>` element. 18/10 Neu, 18/21 and 18/30 Schwesig, 18/23 Maas, 18/25 and 18/35 Wanka's Befragung opening reports, 18/33 Berghegger, 18/36 Wanka, 18/72 Bentele, 18/74, 18/83, 18/91 and 18/106 Müller, 19/99 Ramelow. |
| `fragestunde_frage` | outside | 6 | 377 | 4 | – | Zusatzfragen in a Fragestunde printed as `<name>` rather than as a marker: 18/3 (Verlinden, Neu ×2), 18/16 and 18/22 (Neu). |
| `ansprache` | outside | 2 | 383 | 1 | – | Wolf Biermann at the 18/64 Gedenkstunde, an invited guest. No Redner-ID. |
| `oath_answer` | outside | 2 | 48 | 1 | – | 18/223: the Bundespräsident's oath and his thanks. |
| `remark` | outside | 1 | 8 | 1 | – | 18/181: Bartsch at the lectern before the floor is given ("Außer von den Grünen; die haben nicht geklatscht."). His Rede follows in his own `<rede>`. |
| **Total** | | **170** | **80,381** | **141** | 133 rows* | |

\* The receipt's 131 rows, plus the two rows it removed on review, give 133. Its 131 rows are the 145 turns in a `<rede>`, less 12 short turns and the 2 phrase-test misses (and 131 + 2 + 12 = 145).

Everything except 19/99, 19/104 (Woidke) and 19/125 is in WP 18. Inside a `<rede>`, the WP 18 cases run from 18/4 to 18/107. Outside one, the last are 18/181 and 18/223. WP 20 and 21 print no speaker as a non-chair `<name>`.

### How the parser reads them today, and what that costs beyond the turns themselves

`speech_segments` (`scripts/validate_dip_protocol.py:1240`) makes every `<name>` child of a `<rede>` the Sitzungsleitung. The comment at `:796` says the XML uses `<name>` "for nobody else". These 170 turns are the exceptions. The cost goes beyond the lost words:

- **Two Reden are withheld because of a `<name>`.** 18/6 `ID1800602300` Winkelmeier-Becker (1,251 words): Neu's Zwischenfrage was printed as `<name>`, so Beck's later one is "unresolved". 18/36 `ID1803601400` Pfeiffer (1,803 words): his own consent was lost, so Dehm's Zwischenfrage is "unresolved".
- **Wrong attribution.** In 18/29 `ID1802903200`, Henning Otte's Zwischenfrage in Neu's Rede (41 words) is counted as Otte's own words. Neu's Rede is the `<name>` turn, so the host's owner seems to speak again.
- **An empty Rede with no speaker.** 18/104 `ID1810402200` is stored with `char_count` 0, bound to the placeholder person "Unbekannt" and with no Fraktion or Sprechrolle, and it counts in the Reden total.
- **Debuts are late** (section 3).

Found on the way, not part of this rule: the store keeps Wanka as **two persons**. Her Redner-ID 999990003 appears in 10 files (18/43–18/108) and 999990030 in 22 (18/121–18/244). Nothing joins them, so she has two Personenseiten and her debut is counted twice. Maas and Schwesig are split the same way: their WP 18 minister ids 999990001 and 999990002 are not joined to their later ids 11004809 and 999990099. That gets its own TODOS.md item.

## 2. The options, kind by kind

The TODO names two options. Leaving the turns as they are is not a third one: they would stay counted nowhere and in no withheld share.

- **S, store:** each turn becomes the named speaker's Rede or Beitrag, as if the source had printed a speaker marker.
- **W, withhold under ADR 0005:** each turn becomes a withheld unit of its own. The host Rede stays stored.

A variant of W that withholds the whole host `<rede>` would withhold 77 stored Reden with 74,362 correctly read words, plus 32 stored Beiträge. ADR 0005's rule against withholding "the whole source `<rede>` with every split part" (D4) already rejects it.

| Kind | S stores | W stores |
|---|---|---|
| `rede` in a `<rede>` | A Rede of the named speaker. The parser splits it from the host at the new marker, as 6c does: `<host id>:<marker>`. Several Reden in one host nest as `:2:2` and `:2:2:2`. That is how 18/30's `ID1803002900` gives Pantel, Yüksel and Rainer three Reden. Sprechrolle and Fraktion come from the tag, as from any marker. | A withheld unit with the same split-part id and reason `name_tag_speaker`. Its Redner-ID is required, because the store gate refuses a withheld Rede without one. |
| `rede` outside | A Rede in a `<rede>` wrapped around the `<name>` and its paragraphs. The id is new: `N<ordinal>`, the 1-based position of that `<name>` among the Sitzungsverlauf's `<name>` elements. It is stable for one XML file, which R3's digest pins. The existing synthetic id `<protocol>:<item>:<sequence>` is not used, because it moves when a neighbour does. | A withheld unit with that id. |
| `befragung_antwort`, `befragung_frage`, `zwischenfrage` | A Beitrag of that kind, `nested:<host>:<marker>`, as for any nested marker. In the prototype, today's 6a and Befragung rules give the right kind for all 59 of these turns once the marker exists. The list states the kind anyway. | No unit. ADR 0005 withholds Reden only, so W needs a new withheld-Beitrag kind or leaves these 8,149 words where they are now. |
| `fragestunde_frage` | A flat marker. The Fragestunde reader stores it as `fragestunde_frage`, like the turns around it. | As for Zwischenfragen. |
| `own_words` | The turn joins the host owner's text. Hunko gains 297 words and Ploß 9. Pfeiffer's withheld Rede is released and stored, with his three Zwischenfragen. | The same: these words are the host's own, so there is nothing to withhold. |
| `oath_answer` | Not stored. It goes into `xml_turn_diagnostics` as `procedural`, like every other oath answer in 18/4 (ADR 0004: an oath answer is no Rede). It must **not** become a marker: another speaker's turn inside a listed procedural `<rede>` is withheld with that `<rede>`. The prototype showed this withholding 3 of 18/4's listed oath units. | The same. |
| `ansprache` | Biermann's words as a Beitrag of kind `ansprache`, with no Redner-ID (owner question 4). | The same, or not shown. |
| `remark` | Not stored, listed so that the completeness check passes. | The same. |

### How each option meets the existing rules

- **Reconciliation that accounts for every `<rede>`** (`reconcile_reden`, `:1752`). For in-rede Reden, the split parts go into `created`, as 6c's do, so each needs a status. A host keeps its own status. The outside Reden are new `<rede>` elements that the raw inventory (`:1714`) never saw. The rule records each one as emitted under its `N<ordinal>` id, and a listed entry that the sitting does not match stops the run. S and W are the same here.
- **Split parts and marker ordinals.** A `<name>` that becomes a marker is counted as a marker, so the ordinals of later markers in the same host go up by one. That renames 7 existing units, which the prototype found: 6 nested Beiträge (18/6 Jurk, 18/10 Weiler, 18/24 Krellmann, 18/25 Mutlu, 18/30 Pothmer, 18/101 Hahn) and one withheld unit. Inserting the 6 Fragestunde turns shifts the `sequence` of 228 later turns in three Tagesordnungspunkte (18/3 TOP 6, 18/16 TOP 1, 18/22 TOP 2). Those turns have no `rede_id`, so their ids move too. Pre-release, ids are changed in place. The alternative would be leaving converted markers out of the count and giving them an id form of their own, which costs more than it saves. Again the same for S and W.
- **`withheld_units`.** Under S, 2 withheld Reden are released (18/6, 18/36: 3,054 words) and no Rede is added. W adds 81 withheld units. Of these, 79 are in WP 18, and they would make up most of what WP 18 withholds (section 3).
- **The reviewed-units list.** One entry per (sitting, host or `N<ordinal>`, printed person) with its kind and Redner-ID: 141 entries, generated from the TSV. One existing entry moves: 18/29's `withhold` of Annette Groth's § 31 part, `ID1802902700:2`, becomes `ID1802902700:2:2:2`, because Frei's and Bartz's Reden are now split off before it. The digest changes for the 51 sittings the entries touch, so R3 re-reads exactly those.
- **`erste-reden` (v3).** Under S, a person's first Rede is now the earlier one, so debuts move earlier (section 3). Under W, the earlier Rede is withheld. By v3, a withheld first Rede gives the person **no debut row at all**. W therefore removes these debuts instead of correcting them.
- **ADR 0004 presidium kinds.** A non-chair `<name>` inside a listed `procedural` `<rede>` (18/4) is an oath answer and stays procedural. No other listed `<rede>` holds one.
- **The sibling rule for stage directions** (20/25). A `<name>` in parentheses continues the current speaker. The detector here leaves those tags alone. Both rules must use one chair test, so that a tag is read in this order: chair, stage direction, listed speaker. An unlisted tag is refused (section 5).

## 3. Figures each option moves

A scratch prototype measured option S. It copied the 51 XML files that hold such turns and replaced each listed `<name>` with a speaker marker of its kind and proposed Redner-ID: a split for `rede`, a wrapped `<rede>` outside, a flat marker in the Fragestunde. Oath answers, the remark and Biermann were left alone. It then parsed both versions with today's parser (main v0.46.35.0) and compared every Rede, Beitrag and withheld unit. 18/29 ran with the Groth entry renamed. Biermann's Ansprache is added by hand. Fact values, per-year coverage and Redeanteil per week come from the build's replay, not from here. The base figures are today's store.

**Reden, WP 18** (by side, as `speeches.fraktion` or Sprechrolle):

| Side | Reden old → S | Words added under S |
|---|---|---:|
| CDU/CSU | 4,560 → 4,584 | +22,402 (incl. the 2 released Reden, and Otte −41) |
| SPD | 3,463 → 3,483 | +15,509 |
| Die Linke | 2,108 → 2,124 | +13,541 (incl. Hunko +297) |
| BÜNDNIS 90/DIE GRÜNEN | 2,185 → 2,190 | +4,071 (incl. Kühn's empty Rede, now 933 words) |
| Bundesregierung | 601 → 615 | +16,528 |
| Bundesrat | 21 → 23 | +1,214 (Morlok, Blankau-Rosenfeldt) |
| No speaker | 1 → 0 | (Kühn's Rede gets its speaker) |
| **WP 18** | **12,950 → 13,030 (+80)** | **11,319,529 → 11,392,794 words (+73,265)** |
| WP 19 | 19,982 → 19,984 (+2: Woidke, Ramelow) | +1,511 (incl. Ploß +9) |

The share of WP 18 Reden by Fraktion moves by at most 0.08 points (Bundesregierung 4.64% → 4.72%). Under W, the Reden stay at 12,950 + 2 released − 1 (Kühn's Rede becomes withheld) = 12,951.

**Beiträge, WP 18, under S:** `befragung_antwort` 1,166 → 1,199; `befragung_frage` 1,195 → 1,198; `fragestunde_frage` 3,601 → 3,607; `zwischenfrage` 1,110 → 1,130 (15 here, 4 in the released Reden, and Otte's); `ansprache` 10 → 11. That adds 8,707 words, plus Biermann's 383. Under W, none of these moves.

**Withheld:**

| | Old | S | W |
|---|---|---|---|
| WP 18 withheld Reden | 67 | 65 | 144 |
| WP 18 withheld words | 56,704 | 53,650 | 123,603 |
| WP 18 withheld share (own words) | 0.498% | 0.469% | 1.080% |
| All WPs withheld share | 0.192% | 0.184% | 0.356% |

On today's store of 806 sittings (21/107 to 21/109 added), the scripts reproduce the TSV unchanged and every WP 18 and 19 figure here stands. Only the all-WP shares move: 0.191% old, 0.184% under S, 0.354% under W.

The S figures are more correct for two reasons. Two Reden that were withheld only because of a misprinted `<name>` are read. And the words that were missing from both sides of the ratio are now counted.

**Debuts (`erste-reden`) under S.** A person's first Rede moves earlier for 20 people. The new week is "complete" when no sitting in it has a withheld Rede after this change. Only in complete weeks does the published fact move.

| Person | First Rede today | First Rede under S |
|---|---|---|
| Sven Morlok | 18/42, 2014-W26 (incomplete) | 18/6, 2013-W51 (complete) |
| Elisabeth Winkelmeier-Becker | withheld 18/6, so no debut row | 18/6, 2013-W51 (complete) |
| Johanna Wanka (999990003) | 18/43, 2014-W26 | 18/8, 2014-W03 (incomplete) |
| Karl-Heinz Brunner | 18/36, 2014-W21 (complete) | 18/8, 2014-W03 (incomplete) |
| Alexander S. Neu | 18/32, 2014-W19 (complete) | 18/10, 2014-W05 (incomplete) |
| Heiko Maas | 18/43, 2014-W26 | 18/11, 2014-W05 (incomplete) |
| Manuela Schwesig | 18/38, 2014-W23 (complete) | 18/11, 2014-W05 (incomplete) |
| Christian Petry | 18/33, 2014-W19 (complete) | 18/23, 2014-W12 (complete) |
| André Berghegger | 18/41, 2014-W26 | 18/26, 2014-W14 (incomplete) |
| Hans-Ulrich Krüger | 18/31, 2014-W15 | 18/29, same week |
| Thomas Jurk, Jan Metzler, Sylvia Pantel, Gülistan Yüksel, Burkhard Blienert | 18/43, 18/50, 18/41, 18/64, 18/39 | 18/30, 2014-W15 (incomplete) |
| Waldemar Westermayer | 18/121, 2015-W37 (complete) | 18/57, 2014-W41 (complete) |
| Norbert Müller (Potsdam) | 18/112, 2015-W25 | 18/66, 2014-W46 (incomplete) |
| Verena Bentele | 18/161, 2016-W11 | 18/72, 2014-W49 (complete) |
| Angelika Glöckner | 18/83, 2015-W05 | 18/75, 2014-W51 (complete) |
| Dietmar Woidke | 20/19, 2022-W08 (complete) | 19/104, 2019-W23 (complete) |

Three more people have no stored Rede today: Schavan (18/42), Blankau-Rosenfeldt (18/63) and Ramelow as Ministerpräsident (19/99, Redner-ID 999990081). Ramelow also has an MdB Redner-ID (11003824) with three Reden from 20/182 on. If the registry does not join the two ids, he will appear as two persons, like Wanka. The chair confirms eight of these debuts in the source: "Dies war die erste Rede der Kollegin Pantel"; "erste Rede" for Yüksel, Berghegger, Blienert, Westermayer, Müller and Glöckner; and "erste Rede als Mitglied" for Jurk. In complete weeks, 7 debuts arrive in 6 weeks (2013-W51 ×2, 2014-W12, W41, W49, W51, 2019-W23), and 7 leave 5 weeks (2014-W19 ×2, W21, W23 ×2, 2015-W37, 2022-W08). Ramelow's week is 2019-W19. The replay's fact diff gives the values. **Under W**, these 19 people have no debut row at all, and only Winkelmeier-Becker gains one.

## 4. Recommendation and owner questions

**Store them (S).** Every turn here was given the floor, or is a Beitrag of a kind the dataset already counts. Nothing about it is uncertain once the kind and the speaker are reviewed. W needs the same reviewed list and the same parser machinery: split parts, wrapped `<rede>`s, a Redner-ID per unit. It would then withhold about 71,000 correctly printed words and drop 19 debuts. It also has no answer for the 59 Beiträge.

Questions, my pick first:

1. **Store the 141 entries as the named speaker's Rede or Beitrag (S), rather than withhold them under ADR 0005 (W)?** A: S.
2. **Is the TSV's `kind` and `proposed_redner_id` per entry your review, so that the build writes `scripts/reviewed_units.json` from it?** Yes. (No means you read the 141 entries in the build PR first.) A printed name is no proof of identity (CONTEXT.md, Namensabgleich), so the list is the review. 132 entries need a Redner-ID of their own. For 95 of them, the same Wahlperiode's XML prints exactly one Redner-ID for that name. The other 37 are question 3's. The 3 `own_words` entries use the host owner's id; oath answers, the remark and Biermann need none.
3. **Bind the three names no printed id settles this way?** Yes:
   - Wanka (35 entries) → 999990003, the id of her 2014 Reden. The other is 999990030, and joining the two is the separate TODO.
   - Schavan → 11003836, her MdB-Stammdaten id in the store's `mdb_zugehoerigkeiten`. No WP 18 file prints an id for her.
   - Blankau-Rosenfeldt → DIP person 1828. The Bundestag never gave her a Redner-ID, so the entry carries `dip:1828`, which is a Personenkennung by CONTEXT.md.
4. **Biermann at the 18/64 Gedenkstunde: store his 383 words as an Ansprache with no Redner-ID (A), or leave them out (B)?** A. CONTEXT.md defines an invited guest's address at a ceremonial sitting as an Ansprache, and an Ansprache counts in no figure. B would treat his words like a WP 20/21 address printed as chair text.

Settled by this plan and not asked:
- Ids renumber in place (section 2).
- Oath answers stay procedural.
- Bartsch's remark stays out.
- An unlisted non-chair `<name>` is refused as in section 5.

## 5. Build outline (option S)

**Parser** (`scripts/validate_dip_protocol.py`):

- `mark_name_speakers(root, entries)` runs right after `mark_reviewed_units`, before `mark_roleless_chairs` and `split_nested_reden`. It finds every `<name>` in the Sitzungsverlauf that is not the chair. It uses the chair test above, shared with the sibling stage-direction rule (one function, used by both rules and by the census). For each one:
  - **Listed:**
    - `rede`, `zwischenfrage`, `befragung_*`, `own_words`: the `<name>` is replaced in place by `<p klasse="redner"><redner id="…">`. The `<name>` structure inside it is built from the tag: titles, first and last name, Fraktion, and `<rolle>` for a role. The tag is kept as the tail. An `own_words` entry uses the host owner's id. A `rede` marker carries `listed_kind="rede"`.
    - `rede` outside a `<rede>`: the `<name>` and its paragraphs, up to the next `<name>`, marker or `<rede>`, are wrapped into `<rede id="N<ordinal>">` with that marker.
    - `fragestunde_frage`: a flat marker in place.
    - `oath_answer`: a `procedural` diagnostic. No marker.
    - `ansprache`: a Beitrag of kind `ansprache` with the printed name.
    - `remark`: nothing.
  - **Unlisted, inside a `<rede>`:** a `LocatedRefusal` with reason `unreviewed_name_speaker`. The host unit is withheld and the sitting stays, as for `unreviewed_presidium`.
  - **Unlisted, outside any `<rede>`:** there is no unit to withhold, so it is a `ValueError` and the sitting is refused.
  - **Stale entry:** an entry that no `<name>` matches stops the run (`ReviewedUnitsError`).
- `split_nested_reden` splits at a `listed_kind="rede"` marker unconditionally. It skips the Rednerliste and salutation tests. Without the forced split, the prototype left 16 of the 67 Reden unsplit ("Danke schön. – Frau Präsidentin!", "Liebe Frau Präsidentin!", a floor given as "erhält nun … das Wort"). Eight were read as Zwischenfragen, and the other eight withheld their host Rede.
- `reconcile_reden` records the `N<ordinal>` Reden as emitted.
- The comment at `:796` is corrected.

**List** (`scripts/reviewed_units.py`, `scripts/reviewed_units.json`):

- New kinds `name_rede`, `name_zwischenfrage`, `name_befragung_frage`, `name_befragung_antwort`, `name_fragestunde_frage`, `name_own_words`, `name_procedural`, `name_ansprache`, `name_remark`.
- One extra key, `name`: the printed tag, which must match. `rede_id` names the host `<rede>` or `N<ordinal>`.
- `redner_id` takes digits, `dip:<n>` (one entry), or is empty for `name_procedural`, `name_remark` and `name_ansprache`.
- 141 entries, generated once from the TSV by a script in the PR.
- The Groth entry is renamed to `ID1802902700:2:2:2`.

**Rules and versions:**

- `speech_kinds.VERSION` 9 → 10, because the parse output changes. That forces a full re-read.
- `WITHHELD_REASONS` gains `unreviewed_name_speaker`, which bumps the export format 20 → 21, as `unreviewed_presidium` bumped it last time.
- No store schema change. `dip:` binding uses the registry's DIP Personenkennung. If `persist_dip_pulse_store` cannot take a DIP id from a speaker dict today, that is the one persist change.
- `erste-reden` keeps version 3: its definition does not change.

**Tests:**

- A new `tests/test_name_speakers.py` with synthetic XML for each kind:
  - a split, including nested `:2:2`;
  - outside wrapping;
  - Fragestunde;
  - the oath stays procedural inside a listed procedural `<rede>`;
  - own words;
  - an unlisted turn in and outside a `<rede>`;
  - a stale entry;
  - the chair forms that are not caught: a role prefix, a chair name without a title, and a parenthesised tag.
- `reviewed_units` tests for the new kinds and keys.
- `scripts/check_withhold_one.py` and the full suite stay green.

**Docs:**

- ADR 0004: an amendment, because `<name>` is the chair's except for these reviewed turns.
- CONTEXT.md "Sitzungsleitung": one clause.
- `docs/source-errors.md`: a new entry.
- DATA.md: method sentence and coverage figures.
- `docs/data-changelog.md`: old → new figures.
- CHANGELOG.
- TODOS.md: close this bullet.

**Replay:**

- One full `--offline --repersist` of a copy of the reference store. The speech rule bump re-reads all 803 reports.
- `scripts/compare_store_values.py` against a `cp -cR` baseline, following the README recipe "Validate a data correction".
- Expected: changes in exactly 48 sittings, matching section 3: 47 measured, plus 18/64 for Biermann. 18/4, 18/181 and 18/223 only change their diagnostics. The review checklist's "Figures" check covers this.

**Size:** about 200 lines of parser, 60 of list code, 141 generated entries and 300 lines of tests, plus docs. One PR, one replay. Build it after the stage-direction rule lands, so the two share the chair test.
