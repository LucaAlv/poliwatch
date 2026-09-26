---
status: accepted
---

# Kurzinterventionen and Erwiderungen are not counted as Reden

The Plenarprotokoll XML records a Kurzintervention (§ 27a Abs. 2 GO-BT, at most two minutes, right after another Rede) and the Redner's Erwiderung to it as `<rede>` elements of their own, exactly like a Rede. We do not count them as Reden: every figure defined over Reden (Redeanteil, Rangfolge nach Reden, Reden per Person, the Fakt der Woche metrics that count Reden) excludes them, and where they are shown they are counted on their own. The Bundestag's own count of Redebeiträge does the same: its list of the most frequent Redner leaves out "Zwischenbemerkungen in der Aussprache" along with Zwischenfragen.

Counting them would barely move shares per Zusammenschluss, because the coalition's Erwiderungen offset much of the opposition's Kurzinterventionen: on the WP 21 DIP Aktivitäten no Zusammenschluss moves by more than about half a point. It would distort counts per Person, however: one MdB with 17 Reden also had 15 Kurzinterventionen or Erwiderungen, and for 62 Persons these add at least a quarter on top of their Reden.

## Considered Options

- **Count them as Reden (rejected).** Matches the XML markup and needs no detection, but a two-minute Kurzintervention would weigh as much as a full Rede in every count.
- **Count them as Reden but label them (rejected).** Keeps published numbers stable, but "Rede" would mean two things and readers could not subtract the labelled ones from a total.

## Consequences

- The XML does not type a `<rede>`, so Kurzinterventionen and Erwiderungen must be detected, from the Sitzungsleitung's wording or from DIP's Aktivität type. A detection error now changes counts, not just a label.
- Published counts change, including Fakt der Woche history and Vergleichsbasis baselines built from past weeks.
- The code does not follow this rule yet (GitHub issue #68).

## Sources

- § 27a GO-BT: https://www.gesetze-im-internet.de/btgo_2025/__27a.html
- Datenhandbuch Kap. 7.6, "Reden im Plenum" (what the count of Redebeiträge leaves out): https://www.bundestag.de/resource/blob/196278/Kapitel_07_06_Redner_im_Plenum.pdf
