"""Scratch harness: load cached reports read-only, compute links under a rule, diff against baseline and the review sheet."""
import json, sys, glob, re, csv, collections
sys.path.insert(0, "/Users/luca/Projects/poliwatch/.claude/worktrees/vote-pr-c-24221e/scripts")
import vote_links, derive
D = "/Users/luca/Projects/poliwatch/.context/dip-pulse-site/data/"
SHEET = "/Users/luca/Projects/poliwatch/.claude/worktrees/vote-pr-c-24221e/docs/plans/vote-links-review.tsv"

def load_reports():
    out = {}
    for path in sorted(glob.glob(D + "plenarprotokoll-[0-9]*.json")):
        r = json.load(open(path))
        num = derive.clean_text((r.get("protocol") or {}).get("dokumentnummer"))
        out[num] = r
    return out

def occ_keys(items):
    seen = collections.Counter(); keys = []
    for it in items:
        tid = derive.clean_text(it.get("top_id")); seen[tid] += 1
        keys.append((tid, seen[tid]))
    return keys

def links_by_key(reports, rule):
    """{(vote_id, protocol, top_id, occ): basis}"""
    out = {}
    for num, r in reports.items():
        items = r.get("agenda_items") or []
        keys = occ_keys(items)
        for vid, tops in rule(r).items():
            for pos, basis in tops.items():
                out[(vid, num, keys[pos][0], keys[pos][1])] = basis
    return out

def all_votes(reports):
    return {(vid, num): v for num, r in reports.items() for vid, v in vote_links.report_votes(r).items()}

def load_sheet():
    rows = {}
    with open(SHEET) as f:
        lines = [l for l in f if not l.startswith("#")]
    for row in csv.DictReader(lines, delimiter="\t"):
        rows[(row["vote_id"], row["protocol"], row["top_id"], int(row["top_occurrence"]))] = row
    return rows

def stats(links, votes):
    basis = collections.Counter(links.values())
    per_vote = collections.Counter((k[0], k[1]) for k in links)
    multi = [v for v, n in per_vote.items() if n > 1]
    unlinked = [v for v in votes if v not in per_vote]
    per_top = collections.Counter((k[1], k[2], k[3]) for k in links)
    return dict(links=len(links), basis=dict(basis), votes=len(votes), unlinked=len(unlinked),
                multi_votes=len(multi), multi_links=sum(per_vote[v] for v in multi),
                tops_multi=sum(1 for n in per_top.values() if n > 1))

def diff(old, new, sheet, reports=None):
    added = sorted(set(new) - set(old)); dropped = sorted(set(old) - set(new))
    changed = sorted(k for k in set(old) & set(new) if old[k] != new[k])
    def tag(k):
        row = sheet.get(k)
        return f"{row['verdict']}/{row['pattern']}" if row else "UNREVIEWED"
    return added, dropped, changed, tag

if __name__ == "__main__":
    reports = load_reports()
    votes = all_votes(reports)
    base = links_by_key(reports, vote_links.links)
    print(len(reports), stats(base, votes))
    sheet = load_sheet()
    print("sheet rows", len(sheet), "in base", sum(1 for k in sheet if k in base))
