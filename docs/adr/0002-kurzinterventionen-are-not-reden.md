---
status: accepted
---

# Kurzinterventionen, Erwiderungen and the Fragen and Antworten of question formats are not counted as Reden

The Plenarprotokoll XML records a Kurzintervention (§ 27a Abs. 2 GO-BT, at most two minutes, right after another Rede) and the Redner's Erwiderung to it as `<rede>` elements of their own, exactly like a Rede. We do not count them as Reden: every figure defined over Reden (Redeanteil, Rangfolge nach Reden, Reden per Person, the Fakt der Woche metrics that count Reden) excludes them, and where they are shown they are counted on their own. The Bundestag's own count of Redebeiträge does the same: its list of the most frequent Redner leaves out "Zwischenbemerkungen in der Aussprache" along with Zwischenfragen.

Counting them would barely move shares per Zusammenschluss, because the coalition's Erwiderungen offset much of the opposition's Kurzinterventionen: on the WP 21 DIP Aktivitäten no Zusammenschluss moves by more than about half a point. It would distort counts per Person, however: one MdB with 17 Reden also had 15 Kurzinterventionen or Erwiderungen, and for 62 Persons these add at least a quarter on top of their Reden.

## Amendment 2026-09-26: Fragestunde and Befragung der Bundesregierung

The same rule applies to the question formats. The XML records every Frage, Zusatzfrage and Antwort in the Fragestunde and the Befragung der Bundesregierung as a `<rede>` of its own. None of them is a Rede; only the opening report that starts a Befragung is. The reason is the definition of Rede itself: neither format has an Aussprache, so a Frage or an Antwort is not a contribution to a debate, while the opening report is a statement given the floor on its own. The Datenhandbuch supports this in part. Its count leaves out "Zusatzfragen in der Fragestunde und entsprechend alle Antworten von Regierungsmitgliedern oder Parlamentarischen Staatssekretären während der Fragestunde und der Regierungsbefragung". It does not mention MdBs' Fragen in the Befragung or the opening report.

This one matters far more than Kurzinterventionen. In the store on 2026-09-26, 7,611 of 34,771 recorded `<rede>` elements (22 %) sit in 76 Befragungen, about 100 each. One minister was credited with 40 Reden in a single Befragung. Because most Antworten come from the Bundesregierung, today's shares per Zusammenschluss overstate the government side.

- **Leave the whole Befragung out, including the opening report (rejected).** It is easier to detect, by the TOP heading alone, but it drops a real statement of several minutes that is given the floor like any Rede.
- **Keep counting every Frage and Antwort (rejected).** This contradicts the Datenhandbuch and the definition of Rede, and makes ministers the most frequent Redner.

## Considered Options

- **Count them as Reden (rejected).** Matches the XML markup and needs no detection, but a two-minute Kurzintervention would weigh as much as a full Rede in every count.
- **Count them as Reden but label them (rejected).** Keeps published numbers stable, but "Rede" would mean two things and readers could not subtract the labelled ones from a total.

## Consequences

- The XML does not type a `<rede>`, so Kurzinterventionen and Erwiderungen must be detected, from the Sitzungsleitung's wording or from DIP's Aktivität type. A detection error now changes counts, not just a label.
- Published counts change, including Fakt der Woche history and Vergleichsbasis baselines built from past weeks.
- The code does not follow this rule yet (GitHub issue #68). For the question formats it does not either: `QUESTION_FORMAT_PREFIXES` in `scripts/render_dip_pulse_html.py` keeps every Frage and Antwort in the week's Reden.

## Sources

- § 27a GO-BT: https://www.gesetze-im-internet.de/btgo_2025/__27a.html
- Datenhandbuch Kap. 7.6, "Reden im Plenum" (what the count of Redebeiträge leaves out): https://www.bundestag.de/resource/blob/196278/Kapitel_07_06_Redner_im_Plenum.pdf
