# Bundestag research datasets, and where this project overlaps them

Research note, 2026-11-06, for the second v1 scope review ([v1-scope-review.md](../plans/v1-scope-review.md)). The owner asked for a thorough look at GermaParl. The largest overlap turned out to be another corpus, CPP-BT, so it comes first.

**Evidence kinds.** "Stated" means the source says so, read on the date above. "Measured" means counted here. Our figures come from the A3 store (`~/agent-runs/a3/full`, 2026-10-28, newest sitting 21/103), not main's tip. "Not stated" means the pages read do not say; it does not mean the feature is absent. No dataset below was downloaded or opened, except the two documentation PDFs.

## Short answer

- **Speech text from WP 18 to the present is not a gap.** CPP-BT already offers it under CC0, with the Bundestag's own speech and speaker ids, updated in September 2026.
- **GermaParl overlaps less than it first appears.** Its strengths (1949 on, linguistic annotation, hand checks) are not what this project offers, and its newest open version stops at 2023-07-07.
- **What nobody else was found to offer is the join for current Wahlperioden.** Speeches, TOPs, Drucksachen, Vorgänge and named votes linked at sitting level, through WP 21. This rests on a negative search, so it is a finding and not proof.
- **Our 85 excluded sittings are the weak point against this field.** CPP-BT lists every protocol of WP 18 to 20. We hold 613 of those 698.

## Side by side

| | **This project** | **CPP-BT** | **GermaParl** | **Njie et al.** | **PoliCorp-GermaParl2-PLUS** | **ParlLawSpeech (DE)** | **BTVote** |
|---|---|---|---|---|---|---|---|
| Coverage | WP 18–21, to 2026-10-16 | WP 1–21, to 2026-09-19 | Open: to 2023-07-07. Restricted beta: to 2025-03-18 | WP 1–21, to April 2026 | WP 1–20 in the file | 2009–2021 | WP 1–19 |
| Protocols | 716 of 801 | 4,653 | 4,461 open, 4,559 beta | 4,611 | not stated | not stated | n/a |
| Licence | Layered (ADR 0003) | CC0 | CC BY-SA per its docs, CC BY in Zenodo's field | CC BY 4.0 | CC BY on Zenodo, NC-SA on its GitHub | CC BY 4.0 | CC0 |
| Unit | Rede, plus 8 contribution kinds | Protocol, and speech from WP 18 | Speaker turn, paragraph, sentence. Speeches are reconstructed | Speech | Speech | Speech | Vote, MP |
| Source | Protocol XML, DIP, bundestag.de | XML, DIP from WP 18 | TXT, PDF, XML, varies by WP | PDF | GermaParl, then Open Data | not stated | not stated |
| Speaker id | Yes, plus person merge | `redner_id` | None exposed | `stammdaten_id`, 98.5% of speeches | `speaker_id` | Name only | Yes |
| TOP link | Keyed | Not stated | XML only, "experimental" | Not stated | `agenda_id` | Free-text string | n/a |
| Drucksachen | Keyed | Twin corpus CDRS-BT, not linked as far as read | Not stated | Not stated | Not stated | `bill_ID` | Not stated |
| Vorgänge | Keyed | Not stated | Not stated | Not stated | Not stated | `procedure_ID`, may correspond | n/a |
| Named votes | Keyed, to WP 21 | Not stated | Not stated | Not stated | Not stated | Not stated | Yes, stops at WP 19 |
| Interjections | Not parsed yet (stage 3) | `rede_kommentare` as text | Kept, typed as stage | Not stated | Marked | Not stated | n/a |
| Linguistic annotation | No | Counts only | POS, lemma, NER, DBpedia | No | NER, BERT topic | No | n/a |
| Code | Public, MIT | Public, GPL | Not published | Public | Not stated | Not stated | n/a |
| Update rhythm | Weekly planned (Q3) | Several times per WP | One or two a year, none since May 2025 | Not stated | Quarterly or monthly stated, sources disagree | None stated | Last 2022 |

"Keyed" for this project is measured on the store: 33,841 agenda-to-document links, 590 agenda-to-vote links, 644 vote-to-proceeding links, 382,441 member votes.

## GermaParl

**What it is.** A linguistically annotated corpus of Bundestag debates from 1949, by Andreas Blätte and Christoph Leonhardt (PolMine, University of Duisburg-Essen), funded through NFDI (KonsortSWD, Text+). It ships as Corpus Workbench (CWB) for the R package polmineR, and as TEI-style XML. PolMine is a CLARIN centre, and the corpus had hand checks by the SOLDISK team at Hildesheim.

**Status.**
- Newest open version: v2.1.0, 2024-07-22, 4,461 protocols, 281 million words, ending 2023-07-07.
- Newest version: v2.3.0-rc1, 2025-05-23, 4,559 protocols, 291 million tokens, ending 2025-03-18. It is a closed beta: academic users on request, no sharing.
- No release was found since May 2025. A search hit list was partly truncated, so this is not fully confirmed.
- It does not reach most of WP 21. The planned next step is ParlaMint-DE, a conversion covering 1949 to 2025, with no date given (ParlaCLARIN V, May 2026).

**Overlap with this project.**
- **Same ground:** Reden text for WP 18 to mid-WP 20 openly, and to early WP 21 in the beta. Speaker, Fraktion and party per speaker. Presidium turns split out of other speakers' speeches, for WP 19.
- **Only GermaParl:** 1949 to 2013. POS, lemma, NER and DBpedia entity layers. Interjections kept in the text. CQP querying. A user base in political science.
- **Only this project:** WP 21 in the open. A defined speech unit with recorded decisions on what counts as a Rede (ADR 0001, 0002, 0004). Speaker ids; GermaParl has none, and its docs give no id attribute. Keyed links to Drucksachen, Vorgänge and named votes. Party membership by date: GermaParl has it for WP 20 only, we have C1's seat intervals. A weekly rhythm.

**How to read that.** GermaParl is a neighbour, not a rival. Someone doing discourse or linguistic work stays with GermaParl. Someone asking how a debate relates to the bill and the vote has no GermaParl route.

**What is worth taking from it.**
- Its documentation is honest about limits: no speech attribute, and why. Ours should be as direct.
- It keeps the original speaker label as `who_original`. We should check that our release can show a reader the printed label for every speaker.
- **Licence caution:** v2.0.0 and v2.1.0 say CC BY in Zenodo's field and CC BY-SA in the text. Taking its data in would bring that question with it. Q12 (no new third-party data) already avoids this.

## CPP-BT, the real overlap

*Corpus der Plenarprotokolle des Deutschen Bundestages*, by Seán Fobbe. [Zenodo 22844952](https://zenodo.org/records/22844952), concept DOI 10.5281/zenodo.4542661, version 2026-09-19, CC0.

- **Size:** 4,653 protocols, about 372 million tokens. WP 18 to 21: 245, 239, 214 and 94 protocols. 83,759 speech rows from WP 18 on.
- **Formats:** CSV, TXT, XML and Parquet, 4.4 GB, with SHA hashes and a GPG signature. An open R pipeline, a codebook in German, and a quality report published with the code.
- **Speech table:** `rede_id`, `redner_id`, names, `redner_fraktion`, role, text, `rede_zitate`, `rede_kommentare`. No TOP, Drucksache, Vorgang or vote column in the variable list.
- **Its own stated limit:** it does not check deeply, because the build is automatic. It sends readers who need thorough checks to GermaParl.
- **Twin:** the Drucksachen corpus CDRS-BT. Its record could not be read (HTTP 404 on the API), so its status is unknown.

**Comparison with our counts (measured on ours, stated on theirs):**

| WP | Our sittings | CPP-BT sittings | Our base `rede_id`s | CPP-BT Reden | Ours per sitting | CPP-BT per sitting |
|---|---:|---:|---:|---:|---:|---:|
| 18 | 194 | 245 | 13,962 | 18,524 | 72.0 | 75.6 |
| 19 | 206 | 239 | 22,697 | 26,960 | 110.2 | 112.8 |
| 20 | 213 | 214 | 26,061 | 26,537 | 122.4 | 124.0 |
| 21 | 103 | 94 | 13,002 | 11,738 | 126.2 | 124.9 |

Base ids are `speeches` and `contributions` rows with the `:N` suffix removed, because our sub-ids split one `<rede>`. WP 21 has different cut-offs. The rates sit close together, but 20/11 alone cannot explain WP 20's difference of 476, since one sitting holds about 124. Either CPP-BT keeps rows we do not, or we lose a few. A join on `rede_id` would settle it, and the two id formats match (`ID19200100`).

## Others

- **Njie, Torkayesh and Venghaus 2026** ([Zenodo 21258818](https://zenodo.org/records/21258818)): WP 1 to 21, to April 2026, 1,033,723 speeches, from PDF, `stammdaten_id` on about 98.5% of speeches, party null on about 60%, CC BY.
- **PoliCorp-GermaParl2-PLUS** (GESIS, [Zenodo 21295610](https://zenodo.org/records/21295610)): GermaParl to 2021, then Open Data, as JSON per WP, with a web portal and a BERT topic per speech. Licence statements conflict.
- **ParlLawSpeech** ([site](https://parllawspeech.org/about/)): the closest idea to ours, speech to bill to law, with a `procedure_ID`. Germany is 2009 to 2021, as RDS, with no votes stated and no update plan stated. It suggests researchers want this link. No source offering it for the current Wahlperiode was found.
- **BTVote** (Sieberer et al.): the reference for roll-calls, stops at WP 19. **WP 20 and 21 votes are not in it.**
- **Open Discourse:** coverage ends 2020-11-06 on its Dataverse record, and its repository says not under active development. A gold-standard poster (Ramisch) reports structural deficiencies.
- **ParlaMint 5.0:** 29 parliaments, Germany not among them yet. **ParlSpeech V2:** a single version from 2020, superseded by ParlLawSpeech.
- **abgeordnetenwatch API:** CC0, votes per MP; WP range not stated.

## What this means

1. **Positioning.** Our headline cannot be "tidy, citable Bundestag transcripts"; that exists under CC0. It is "the joined, current record". `docs/designs/fakt-der-woche.md:36-41` already said so on 2026-09-19, but that design is the feature now cut, and `PRODUCT.md:42-46` names no research dataset.
2. **Coverage.** A researcher comparing the two sees 613 of 698 sittings against all of them. CPP-BT keeps a sitting even when its contents are imperfect. Our exclusion also drops the sitting's TOPs, Drucksache links and votes, which are what no other source was found to offer. The store holds 0 of its 556 votes on the 85 excluded dates.
3. **Free checks.** Three independent pipelines over the same XML can check each other. CPP-BT's codebook already led to one real defect here, the shared speaker ids in the store (`TODOS.md`, "Speaker ids the Bundestag gives to more than one person").
4. **The right first readers.** Fobbe and the PolMine authors know this material better than anyone, and could be the researcher check that Q16 left open. Contacting them is the owner's call.
5. **Do not chase.** Linguistic annotation, WP 1 to 17 and ParlaMint encoding are other people's strengths. Parquet would break the standard-library rule (`PRODUCT.md:58`).

## Sources

GermaParl: [update post](https://polmine.github.io/posts/2025/05/23/GermaParl2-Update.html), [v2.3.0-rc1](https://zenodo.org/records/15495748), [v2.1.0](https://zenodo.org/records/12794676), [docs (v2.0.1)](https://polmine.github.io/GermaParl2/), [data report](https://polmine.github.io/GermaParl2/data-report.html), [ParlaMint-DE paper](https://aclanthology.org/2026.parlaclarin-1.5/). Bundestag: [open data](https://www.bundestag.de/services/opendata). BTVote: [Dataverse](https://dataverse.harvard.edu/dataverse/btvote). Open Discourse: [Dataverse](https://doi.org/10.7910/DVN/FIKIBO), [repository](https://github.com/open-discourse/open-discourse). ParlaMint: [5.0](https://www.clarin.si/repository/xmlui/handle/11356/2004).

**Not read:** the CDRS-BT record, the ParlLawSpeech codebook (GESIS answered 403), the actual files of any dataset. Parts of the Zenodo search and version lists came through a truncated fetch.
