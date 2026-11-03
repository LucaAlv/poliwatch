"""T1.1 measurements (plan a4-site-from-release.md, Slice 1) on one output dir.

Usage: python3 -I t11_measure.py <repo_scripts_dir> <output_dir>
Reads the store and the cached reports with the repo code at <repo_scripts_dir>.
"""
import json
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

scripts_dir, out = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(scripts_dir))

import build_dip_pulse_site as b  # noqa: E402
import derive  # noqa: E402
import politikfelder  # noqa: E402
import render_dip_pulse_html as pulse_html  # noqa: E402
from features import votes as vf  # noqa: E402

db = out / "data" / "bundestag-pulse.sqlite"
conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row

reports = []
for path in sorted((out / "data").glob("plenarprotokoll-*.json")):
    reports.append(json.loads(path.read_text(encoding="utf-8")))
cache = politikfelder.load_cache(out)

stored = vf.stored_votes(conn)
by_id = {s.vote["id"]: s for s in stored}
print(f"store: {len(stored)} votes, {conn.execute('SELECT COUNT(*) FROM vote_members').fetchone()[0]} vote_members, "
      f"{conn.execute('SELECT COUNT(*) FROM protocols').fetchone()[0]} protocols")
print(f"reports: {len(reports)}")

# --- report-side votes (the old JSON path) ---------------------------------
report_votes = {}  # vote id -> (report, first item, vote)
report_vote_count = 0
for report in reports:
    for item, vote in derive.iter_report_votes(report):
        report_vote_count += 1
        key = pulse_html.vote_key(vote)
        prev = report_votes.get(key)
        if prev is None or str(report.get("protocol", {}).get("datum") or "") >= str(prev[0].get("protocol", {}).get("datum") or ""):
            report_votes[key] = (report, item, vote)
print(f"report votes (per sitting): {report_vote_count}; distinct ids: {len(report_votes)}")

# M0: votes.id == pulse_html.vote_key for every vote
ids_store = set(by_id)
ids_report = set(report_votes)
print(f"M3b votes.id == vote_key: store-only {sorted(ids_store - ids_report)}, report-only {sorted(ids_report - ids_store)}")

# M1: Politikfelder, report_politikfelder vs stored vote_politikfelder (both through politikfelder.shown)
pf_diff = []
for report in reports:
    _items, vote_tags = politikfelder.report_politikfelder(report, cache)
    for key, tagging in vote_tags.items():
        s = by_id.get(key)
        if s is None:
            continue
        old = politikfelder.shown(tagging)
        new = politikfelder.shown(s.tagging)
        if old != new:
            pf_diff.append((key, old, new, tagging, s.tagging))
print(f"M1 Politikfelder differ (report_politikfelder vs stored): {len(pf_diff)}")
for d in pf_diff[:10]:
    print("   ", d)
src = Counter(s.tagging[1] for s in stored)
print(f"   stored vote_politikfelder sources: {dict(src)}")

# M2: documents.url vs per-item winner of document_source_links, over every vote link
doc_url = {r[0]: r[1] for r in conn.execute("SELECT document_number, url FROM documents")}
links_total = links_eq = links_diff = links_nolink = 0
diff_examples = []
for s in stored:
    winners = vf.document_source_links(s.item) if s.item else {}
    for number in s.vote["document_numbers"]:
        links_total += 1
        w = winners.get(number)
        if w is None:
            links_nolink += 1
            continue
        if doc_url.get(number) == w[0]:
            links_eq += 1
        else:
            links_diff += 1
            diff_examples.append((s.vote["id"], number, doc_url.get(number), w))
print(f"M2 vote links: {links_total}; documents.url == per-item winner: {links_eq}; differs: {links_diff}; "
      f"no per-item link: {links_nolink}")
for d in diff_examples[:8]:
    print("   ", d)

# M3a: lowest item_index vs iter_report_votes first TOP
mismatch = []
lowest = {}
for vote_id, item_index in conn.execute(
    "SELECT aiv.vote_id, MIN(ai.item_index) FROM agenda_item_votes aiv JOIN agenda_items ai ON ai.id = aiv.agenda_item_id "
    "JOIN votes v ON v.id = aiv.vote_id AND v.protocol_id = ai.protocol_id GROUP BY aiv.vote_id"
):
    lowest[vote_id] = item_index
import stable_ids as persist  # noqa: E402
under_two = 0
for report in reports:
    seen_items = Counter()
    for item in report.get("agenda_items") or []:
        for vote in derive.item_votes(item):
            seen_items[pulse_html.vote_key(vote)] += 1
    under_two += sum(1 for c in seen_items.values() if c > 1)
    for item, vote in derive.iter_report_votes(report):
        key = pulse_html.vote_key(vote)
        first = persist.source_index(item.get("index")) if item is not None else None
        if lowest.get(key) != first:
            mismatch.append((key, first, lowest.get(key)))
print(f"M3a first TOP (iter_report_votes) == lowest item_index: mismatches {len(mismatch)} {mismatch[:5]}; "
      f"votes under 2+ TOPs of one sitting: {under_two}; sitting-level votes: {sum(1 for s in stored if s.item is None)}")

# M4: votes with no vote_documents; does the JSON path show links for them?
no_docs = [s for s in stored if not s.vote["document_numbers"]]
print(f"M4 votes with no vote_documents: {len(no_docs)}")
for s in no_docs:
    report, item, vote = report_votes[s.vote["id"]]
    links = vf.document_source_links(item) if item else {}
    shown = [n for n in (vote.get("document_numbers") or [])]
    print(f"    {s.vote['id']} {s.vote['date']} report document_numbers={shown} linked={[n for n in shown if n in links]}")

# M5: short groups (member groups do not cover their fraction counts) on the store
short_votes = Counter()
short_groups = 0
for s in stored:
    groups = derive.vote_abweichler(s.vote)
    states = Counter(g["state"] for g in groups.values())
    bad = states["partial"] + states["no_members"]
    short_groups += bad
    if bad:
        short_votes["short"] += 1
    if derive.vote_abweichler_count(s.vote) is None:
        short_votes["count_none"] += 1
    if not derive.vote_groups_cover_total(s.vote):
        short_votes["not_cover_total"] += 1
null_totals = conn.execute(
    "SELECT COUNT(*) FROM votes WHERE yes_count IS NULL OR no_count IS NULL OR abstain_count IS NULL OR absent_count IS NULL"
).fetchone()[0]
print(f"M5 short groups: {short_groups} in {short_votes['short']} votes; Abweichler count None: {short_votes['count_none']}; "
      f"groups do not cover total: {short_votes['not_cover_total']}; votes with a NULL count: {null_totals}")

# Render time of votes_archive_rows
if hasattr(b, "votes_archive_rows"):
    t = time.perf_counter()
    rows = b.votes_archive_rows(db)
    t1 = time.perf_counter()
    b.render_votes_archive_index(rows)
    t2 = time.perf_counter()
    print(f"votes_archive_rows: {t1 - t:.3f} s for {len(rows)} rows; render {t2 - t1:.3f} s")
