# How bundestag.de builds a namentliche Abstimmung page, and what B4 can learn

Research note, 2026-10-19. Prompted by the B4 question "how should B4 handle the votes without a DIP abstract?" and the vote page <https://www.bundestag.de/parlament/plenum/abstimmung/abstimmung?id=1036> (Bundeswehreinsatz Unmiss, 15 Oct 2026), whose "Debatte" tab carries a written account of the vote and the debate.

**Method.** All 217 vote pages of the reference store (`~/agent-runs/b3-review-replay/site/data`, votes 2022-01-27 to 2026-06-12) were fetched on 2026-10-19 and parsed; one Textarchiv article and one Antrag PDF were read by hand. The pages are editorial and change after a vote (see "Lifecycle"), so every figure below describes the pages as of 2026-10-19, not as of the vote. Scripts and raw pages are not committed; the measures are reproducible from a fresh fetch.

## 1. Constraint first: the Debatte text cannot be republished

The Debatte prose is written by the Bundestag's editorial team (Parlamentsredaktion / Internetredaktion), signed with editor initials and a date, e.g. `(ahe/hau/15.10.2026)`. It is not an amtliches Werk. The [Impressum](https://www.bundestag.de/services/impressum) (read 2026-10-19) says the site's content is protected and "dürfen … nur für den privaten Gebrauch heruntergeladen oder ausgedruckt werden. Jede darüber hinausgehende Verwendung ist nicht gestattet", with exceptions needing written consent. Only Drucksachen and Plenarprotokolle are exempt (§ 5 UrhG, subject to §§ 62/63).

So "show their text for the votes without an abstract" is not available to us. What we can use:

- **Facts** (dates, numbers, which document was voted on, the outcome). Facts carry no protected expression.
- **The link.** A deep link to the vote page's Debatte tab, or to the Textarchiv article, as a "Bericht des Bundestages" source.
- **The method**, i.e. how they write it (section 4).

The consent question already open in [ADR 0003](../adr/0003-licences-and-impressum.md), question 5, could ask about the Debatte texts in the same email.

## 2. Page anatomy

The CMS is CoreMedia (`/blueprint/servlet/…`, `data-cm-id`, `/resource/blob/…`). A vote page is a composition of three content objects.

**a) The vote object** (id `1036`, the `/apps/na/` app):

- Header: date, an editorial plain-language `<h1>` ("Ablehnung eines Antrags zur BAföG-Reform"), and under it the formal Tagesordnung wording with Drucksache links. We already store the `<h1>` as `title` and the formal wording as `description`, both from the list endpoint.
- Tab "Abstimmungsergebnis":
  - Overall bar chart: `<canvas data-chart-values="496,73,4,57">`.
  - One doughnut per Fraktion (`data-value="CDU/CSU"`, same CSV order: ja, nein, enthalten, nicht abgegeben).
  - A member list loaded from `/apps/na/namensliste.form?id=1036&ajax=true` and rendered client-side by a mustache template (`#na-listview-template`), with filters for A–Z, Fraktion, Bundesland, PLZ/Wahlkreis (autocomplete `/ajax/filterlist/de/--440456/plz-only-autocomplete`), Geschlecht and Alter, and a list/picture toggle.
  - We already parse all of this (`fetch_roll_call_vote_detail`, `parse_fraction_votes`, `parse_member_votes`).

**b) The Textarchiv article, transcluded as the "Debatte" tab.** The tab id is `tab_debatte_<videoId>`. Inside it, `showItContainer_<articleId>_<videoId>` names both:

- the Mediathek video of the whole agenda item (`7666172`);
- the Textarchiv article (`1223592`). This is the same id as the article URL suffix: `/dokumente/textarchiv/2026/kw42-de-bundeswehr-unmiss-1223592`.

That gives a deterministic vote → article join with no fuzzy matching. The tab holds:

- The video player.
- The article body: a lead paragraph, then `<h2>` sections.
- An embedded result widget: `<roll-call-votes-component>` fed by an inline JSON block (`<script type="application/json" data-for-id="na_…">`) with `votes`, `href`, `teaserTitle`, `date`, `leadingTitle` (the Ressort label, e.g. "Auswärtiges") and `majorityType` (`SIMPLE` / `TWO_THIRDS` / `ABSOLUTE`).
- A sidebar with:
  - **Reden zu diesem Tagesordnungspunkt**: one Mediathek video per speech (`/mediathek/video?videoid=…`), speaker name and role.
  - **Dokumente**: each Drucksache with its type, full title, PDF size and "Status" date.
  - **Fundstelle im Plenarprotokoll**: a PDF link with a page anchor, `…/btp/20/20xxx.pdf#P.11016`.
  - **Beschluss** (see c).
  - **Tagesordnung**: `/tagesordnung?week=42&year=2026`.

**c) The Beschluss box.** It belongs to the agenda item, not to the vote: it lists every decision taken under the item (Überweisungen, show-of-hands outcomes, each roll call). For a roll call it reads like this:

```
namentliche Abstimmung zu Beschlussempfehlung 21/8613 (Antrag 21/8293 annehmen)
18:13:52: Beginn der Abstimmung
18:36:51: Ende der Abstimmung
endgültiges Ergebnis
Gesamt: 573 Ja: 496 Nein: 73 Enthaltungen 4
Beschlussempfehlung 21/8613 angenommen
```

The first line names the voted object and, in parentheses, what the committee recommended. The box can also record a Wahlwiederholung and Sitzungsunterbrechungen (vote 936), Buchstabe and Artikel splits ("hier Artikel 7", "zweite Beratung"), and corrected tallies ("endgültiges Ergebnis"). We already read this box for the outcome word (`_official_vote_text`, matched by this vote's Ja/Nein tally), and we discard everything else in it.

## 3. Lifecycle of the editorial text

The Textarchiv article exists before the debate. Week 45 (upcoming) already had articles on 2026-10-19. One article covers one proceeding and carries a tab per reading ("1. Lesung", "2./3. Lesung"). The Unmiss article shows the pattern:

- **1. Lesung tab** (signed 08.10.2026): "Ihren Antrag hat der Bundestag am Mittwoch, 7. Oktober 2026, erstmals debattiert … an die Ausschüsse überwiesen."
- **2./3. Lesung tab** (signed 15.10.2026, the day of the vote): a new lead with the result and numbers, plus the same "Antrag der Bundesregierung" section copied from the first tab and moved into the past tense ("…, lautete die Forderung im Regierungsantrag").

In the 217 pages, 210 signatures are dated on or after the vote and 5 before it. Those 5 are texts that were never rewritten after the vote. A cached copy can therefore be a preview, and a fetch shortly after a vote can catch the preview too.

## 4. How they write it (the transferable part)

The structure is constant:

1. **Lead paragraph, built only from structured facts.** Who decided what, on which day, the outcome, the numbers, the committee's Beschlussempfehlung, and any §96 report. Example: "Der Bundestag hat am Donnerstag, 15. Oktober 2026, … angenommen. In namentlicher Abstimmung votierten 496 Abgeordnete für die Mandatsverlängerung, 73 stimmten dagegen. Es gab vier Enthaltungen. … hatte der Auswärtige Ausschuss eine Beschlussempfehlung (21/8613) abgegeben."
2. **One section per Vorlage**, headed by its type ("Antrag der Bundesregierung", "Abgelehnter Antrag zu Bildungskosten"). It paraphrases the Drucksache and attributes every claim to its author, in indirect speech: "Wie die Bundesregierung schreibt …", "Laut der antragstellenden Fraktion …", "forderten die Grünen …". Comparing 21/2234 (Grüne, BAföG) with its section shows the source: the editors summarise section II of the Antrag, "Der Deutsche Bundestag fordert die Bundesregierung auf …", and leave out the partisan section I, "stellt fest".
3. **Optional per-Fraktion debate sections**, "CDU/CSU: Müssen als Regierung Prioritäten setzen" (96 of 218 articles).

Only (2) and (3) need prose judgement. Everything in (1) is available to us as data, so a deterministic lead sentence covers every vote, with or without an abstract.

## 5. Measurements (217 stored votes, pages of 2026-10-19)

**Debatte text exists for 215 of 217.** The two without are 784 (Sondervermögen Bundeswehr, 2022) and 994 (GEAS-Anpassungsgesetz, 2026).

**Votes without a DIP abstract: 50, 67 or 77, depending on the counting method:**

| Method | With abstract | Without |
|---|---|---|
| Any Vorgang reached by any of the vote's BT numbers | 167 | 50 |
| Only numbers that resolve to exactly one Vorgang | 150 | 67 |
| Only a Vorgang that every one of the vote's numbers reaches | 140 | 77 |

The other agent's 64 lies inside this range. Number fan-out makes the first method an upper bound, so a B4 spec should name its method. Under the first method, 45 of the 50 are `Antrag` Vorgänge, 3 Entschließungsanträge, 1 Vertrauensantrag and 1 Gesetzgebung. DIP's documentation service writes no abstracts for opposition Anträge.

**All 50 have Debatte text, but it is not one text per vote:**

- 180 distinct articles serve the 215 votes. 58 votes share an article with another vote, and one article covers 9 votes.
- For the 50 without an abstract, the vote's own Drucksache number appears inside an `<h2>` section for 15. For the other 35 it appears only in the lead or intro.
- Section headings are unreliable for matching. In vote 1005, the section headed "Abgelehnter Antrag zum BAföG" covers 21/5780, and 21/2234 (the BAföG Antrag actually voted on) sits under "Abgelehnter Antrag zu Bildungskosten". Match a vote to its section by Drucksache number inside the section, never by heading.

**Embedded JSON** (`majorityType`, `leadingTitle`) appears on 76 pages, all from 2024 onwards: none in 2022–2023, 25 of 47 in 2024, 36 of 42 in 2025, 15 of 20 in 2026. A shared article embeds one widget per vote, each with its own `href` (`abstimmung?id=N`), so read only the widget whose id is the page's own. On that basis 63 pages carry their own widget and 13 carry only other votes' widgets.

- `majorityType` from the page's own widget: SIMPLE 58, TWO_THIRDS 3 (939, 951 Grundgesetz changes; 926), ABSOLUTE 2 (938 Vertrauensfrage; 973). Two of the five non-simple values look wrong. Vote 926 (repeal of the Lieferkettengesetz, a simple law) is TWO_THIRDS, and vote 973 (Schwarzarbeitsbekämpfung, a 2./3. Beratung) is ABSOLUTE. So the field can cross-check `special_majority_procedure`, but it is editorial data, not ground truth.
- `leadingTitle` equals our stored `topic` (the list Dachzeile) on 69 of 73.

**The Beschluss box prints the provisional tally; our store holds the final one.** For 43 of 217 votes the box tally differs from ours by 1–3 votes. Our tally matches the page chart, the member list and the Plenarprotokoll's "Endgültiges Ergebnis". Example, vote 996 in Plenarprotokoll 21/67:
- Read out in the sitting ("verlesen"): 573 votes cast, Ja 438, Nein 135. That is what the box shows, labelled "endgültiges Ergebnis".
- Endgültiges Ergebnis: 574 votes cast, Ja 439, Nein 135. That is what we store.

Our store is right. But `_official_vote_text` looks for this vote's sentence in the box by our final Ja/Nein tally, so for these 43 votes it cannot find the outcome sentence, and the result falls back to a derived one. This is my reading of the code; I didn't trace an actual build. Matching with a ±3 tolerance or against the provisional tally would fix it.

**Beschluss box vs. our inversion reading.** I matched the "namentliche Abstimmung …" line to each vote by its Ja/Nein tally, as `_official_vote_text` does; taking the box's first line is wrong for bundled items. I then ran our `recommendation_inversion` on the stored title and description, the page `<h1>`, and the stored DIP document titles. The stores I found have `inverted` and `result_raw` empty for all 217 votes, so I re-derived both.

- A tally-matched line was found for 146 votes. For the rest, the tally didn't match exactly once (46; 43 of these are the provisional-tally offset above), there was no roll-call line before the tally (23), or there was no box (2).
- **"zu Beschlussempfehlung X (Antrag Y ablehnen)": 28 votes.** Ja means rejecting the Antrag. Our reading flags 14 and **misses 14**: 773, 790, 793, 798, 803, 811, 819, 841, 850, 855, 873, 882, 892, 906.
  - Nine of the 14 are confirmed by the tallies: the sponsoring Fraktion voted Nein on its own Antrag's rejection (e.g. 906 Taurus, CDU/CSU Nein; 892, AfD Nein). For the other five no sponsor could be parsed from the subtitle, but the Nein bloc is the size of one opposition Fraktion.
  - Per `features/votes.py`, a vote that is not flagged gets no "Ja = Antrag ablehnen" note and no "Antrag:" badge prefix.
  - All 14 are WP 20 votes. None of their titles uses the "Ablehnung eines/des/der Antrag…" wording the regex needs. Most end in "(Beschlussempfehlung)". 906 reads "Ablehnung von Lieferung …", which the regex doesn't match either.
- **"zu Beschlussempfehlung X (… annehmen)": 23 votes.** Not inverted; we agree on all 23.
- **Object is the Vorlage itself** ("zu Gesetzentwurf X (Beschlussempfehlung Y: Gesetzentwurf ablehnen)", "zu Antrag X", "zu Änderungsantrag X"): Ja means for the Vorlage, so not inverted, even when the parenthetical says "ablehnen".
- **The box's object label can be shorthand.** In 996, the box reads "namentliche Abstimmung zu Antrag 21/4466 … Ja: 438 … Antrag 21/4466 abgelehnt". The sponsor (AfD) voted Nein, and the Plenarprotokoll says "Ergebnis der namentlichen Abstimmung über die Beschlussempfehlung … Damit ist die Beschlussempfehlung angenommen." So the question was really the rejecting recommendation. Our `inverted` is right there and the literal box reading would be wrong. The box is strong evidence, not proof. The protocol's announcement sentence is an amtliches Werk, already sits in our cached XML, and names the voted object outright, so it may be the better source of the three.
- **Separate open issue: in the replay build, the flag never reaches the page.** In every local store (`b3-review-replay`, `.context/dip-pulse-site`, `/private/tmp/pfx`), `inverted` and `result_raw` are empty for all 217 votes. The cached report JSON has no `inverted` key either. The rendered replay site shows no inversion note on any of its 108 vote panels, and 1005, which our function does flag, renders "Kein Ergebnis verfügbar". So in that build, all 28 recommendation-to-reject votes are shown un-inverted, not only the 14. Whether an online build persists the fields was not checked. This looks like a persistence or replay gap, not a regex one, and it should be checked before B4 relies on the flag.

**Our build already fetches but drops:**

- The Beschluss line and its voted object.
- The vote start and end times (168 pages).
- `majorityType` and `leadingTitle`.
- The speech videos per agenda item.
- The Fundstelle page anchor.
- The Dokumente list with dates.
- The Textarchiv article id.

## 6. Implications for B4

1. **Lead sentence: deterministic, no AI.** It follows the editors' pattern (date, decision, voted object, recommendation, numbers, committee).
   - Every vote has the h1, the formal description (which names the Vorlage, the committee and the Drucksachen) and the tallies.
   - The voted object and the recommendation's direction come from the tally-matched Beschluss line on 146 votes today, about 189 with a ±3 tally match. Otherwise they come from the Plenarprotokoll announcement sentence.
   - The "Ja means …" clause is only as good as the inversion reading (see the 14 misses and the persistence gap in §5).
   - This fills B4's "what was decided" for the 50–77 votes without an abstract, factually, and it doesn't wait on the validators.
2. **"What was proposed" for Anträge without an abstract: an extractive fallback, not an AI one.** Use section II of the Antrag Drucksache ("fordert die Bundesregierung auf: 1. …"). It is an amtliches Werk, so it can be quoted verbatim with a source line (§§ 62/63 UrhG). It is also the passage the editors paraphrase. It needs a PDF or DIP-text extraction step and a length rule (cut after the first n demands), but no validators. For a rejected Beschlussempfehlung it must sit under the inversion framing ("Abgelehnt wurde ein Antrag der AfD, der forderte: …"). Whether this replaces or precedes the labelled AI sentence is a B4 decision.
3. **Link to the Debatte tab** as "Bericht und Debatte beim Bundestag" (`…abstimmung?id=N#debatte` or the Textarchiv URL via the article id). Link only, until consent arrives.
4. **Inversion: first find out why `inverted` is empty in the stores, then add evidence.** Add the protocol's "Abstimmung über die Beschlussempfehlung … zu dem Antrag" sentence or the tally-matched Beschluss line to `recommendation_inversion`. Either would recover the 14 misses. Because of 996, weigh the box against the title and the sponsor's vote; don't let it override them. Inversion is a P1 dependency of B4, so this belongs in front of it. It is a separate fix; nothing was changed in `scripts/`.
5. **Official outcome: allow for the provisional tally** when `_official_vote_text` searches the box (43 votes, §5).
6. **Small extras worth storing:** `majorityType` as a cross-check for `special_majority_procedure`, the Fundstelle page anchor (a better source link than the protocol root), and the vote times.

## Not covered

- Votes 1010–1036 (after the store's last vote): only a few fetched, not analysed.
- How the Beschluss box is produced upstream (probably the Parlamentsdokumentation's Beschlussübersicht). Not traced.
- DIP's `drucksache-text` endpoint as the source for item 6.2: not tried; no API key in this session. Fetching the PDF and running `pdftotext` worked.
