import re, collections
from harness import *

EP_RE = re.compile(r"Einzelplan\s+(\d{1,2})\b")
GO_RE = re.compile(r"^(Geschäftsordnungsantrag|Antrag zur Geschäftsordnung)")

def ep_numbers(text):
    return {int(n) for n in EP_RE.findall(text or "")}

def numbers_of(item, skip_go_mitberaten=False):
    printed = {str(d["dokumentnummer"]) for d in derive.xml_drucksachen(item) if d.get("dokumentnummer")}
    api = item.get("api") or {}
    linked_docs = api.get("linked_drucksachen") or []
    if skip_go_mitberaten:
        positions = api.get("positions") or []
        allowed = {str(p.get("vorgang_id")) for p in positions if p.get("vorgang_id")}
        for p in positions:
            if GO_RE.search(p.get("vorgangsposition") or "") : continue
            allowed |= {str(m.get("id")) for m in p.get("mitberaten") or [] if m.get("id")}
        linked_docs = [d for d in linked_docs if str(d.get("vorgang_id")) in allowed]
    linked = {str(d["dokumentnummer"]) for d in linked_docs if d.get("dokumentnummer")}
    return printed, linked

def third_reading(heading):
    return bool(re.search(r"(^|[\s–\-)])Dritte Beratung", heading or ""))

def make_rule(einzelplan=False, dominance=False, third=False, go=False, tiebreak_title=False, ep_any=False):
    def rule(report):
        items = report.get("agenda_items") or []
        nums = [numbers_of(it, go) for it in items]
        titles = [[it.get("heading"), *vote_links._position_titles(it)] for it in items]
        out = {}
        for vote in vote_links.report_votes(report).values():
            vn = {str(n) for n in vote.get("document_numbers") or []}
            matched = {}; shared = {}
            for pos, (p, l) in enumerate(nums):
                if vn & p: matched[pos] = "drucksache_xml"
                elif vn & l: matched[pos] = "drucksache_vorgang"
                if pos in matched: shared[pos] = vn & (p | l)
            if not matched:
                titled = [pos for pos, c in enumerate(titles) if any(vote_links.title_matches(t, vote.get("title")) for t in c)]
                if len(titled) == 1: matched[titled[0]] = "title"
            text = f"{vote.get('title') or ''} {vote.get('description') or ''}"
            if einzelplan:
                eps = ep_numbers(text)
                second = "zweiten Beratung" in text or not re.search(r"dritten Beratung", text)
                if len(eps) == 1 and second and (matched or ep_any):
                    ep = next(iter(eps))
                    cands = [pos for pos, it in enumerate(items) if ep in ep_numbers(it.get("heading"))]
                    if len(cands) == 1:
                        matched = {cands[0]: "einzelplan"}
            if dominance and len(matched) > 1 and all(pos in shared for pos in matched):
                keep = {pos for pos in matched if not any(shared[pos] < shared[o] for o in matched if o != pos)}
                matched = {pos: b for pos, b in matched.items() if pos in keep}
            if third and len(matched) > 1:
                t = [pos for pos in matched if third_reading(items[pos].get("heading"))]
                if len(t) == 1: matched = {t[0]: matched[t[0]]}
            if tiebreak_title and len(matched) > 1:
                t = [pos for pos in matched if vote_links.title_matches(items[pos].get("heading"), vote.get("title"))]
                if len(t) == 1: matched = {t[0]: matched[t[0]]}
            out[derive.vote_identity(vote)] = matched
        return out
    return rule

def report_diff(name, reports, base, new, sheet, votes):
    added, dropped, changed, tag = diff(base, new, sheet)
    print(f"### {name}: {stats(new, votes)}")
    print(f"  added {len(added)} dropped {len(dropped)} basis-changed {len(changed)}")
    for k in dropped: print("   -", k, base[k], tag(k))
    for k in added: print("   +", k, new[k], tag(k))
    for k in changed: print("   ~", k, base[k], "->", new[k], tag(k))
    wrong = {k for k, r in sheet.items() if r["verdict"] == "wrong"}
    right = {k for k, r in sheet.items() if r["verdict"] == "right"}
    print(f"  sheet: wrong still present {len(wrong & set(new))}, right lost {len(right - set(new))}")

import xml.etree.ElementTree as ET
XMLD = "/Users/luca/Projects/poliwatch/.context/dip-pulse-site/data/xml/"
DRS_RE = re.compile(r"Drucksachen?\s+((?:\d{2}/\d+(?:\s*(?:,|und|sowie)\s*)?)+)")
NUM_RE = re.compile(r"\d{2}/\d+")

def page(x):
    try: return int(str(x).strip().split()[0])
    except Exception: return None

def overlap_pages(item, position):
    pr = item.get("page_range") or {}
    ts, te = page((pr.get("start") or {}).get("page")), page((pr.get("end") or {}).get("page"))
    src = position.get("source") or {}
    ps = page(src.get("anfangsseite") or src.get("seite")); pe = page(src.get("endseite") or src.get("seite")) or ps
    if None in (ts, te, ps, pe): return None
    return min(pe, te) - max(ps, ts) + 1

def weak_vorgaenge(items):
    """per item: Vorgang ids whose every position reaches this item only on one boundary page while the same position overlaps another item by more pages"""
    out = []
    for i, it in enumerate(items):
        strong, seen = set(), set()
        for p in (it.get("api") or {}).get("positions") or []:
            vid = str(p.get("vorgang_id")); seen.add(vid)
            ov = overlap_pages(it, p)
            others = [overlap_pages(o, p) for j, o in enumerate(items) if j != i]
            if ov is not None and ov <= 1 and any(x is not None and x > ov for x in others):
                continue
            strong.add(vid)
            strong |= {str(m.get("id")) for m in p.get("mitberaten") or []}
        out.append(seen - strong)
    return out

def headingless_chair_numbers(report, num):
    """(top_id, occ) -> numbers the chair names in a headingless section, from the XML."""
    path = XMLD + "plenarprotokoll-" + num.replace("/", "-") + ".xml"
    try: root = ET.parse(path).getroot()
    except Exception: return {}
    seen = collections.Counter(); res = {}
    for top in root.findall("./sitzungsverlauf/tagesordnungspunkt"):
        tid = derive.clean_text(top.get("top-id")); seen[tid] += 1
        nums = set()
        for p in top.findall("./p"):
            if (p.get("klasse") or "").startswith("T"): continue
            text = "".join(p.itertext())
            for m in DRS_RE.finditer(text): nums |= set(NUM_RE.findall(m.group(1)))
        res[(tid, seen[tid])] = nums
    return res

_CHAIR = {}
def chair_sections(report, num):
    if num not in _CHAIR:
        items = report.get("agenda_items") or []
        keys = occ_keys(items)
        chair = headingless_chair_numbers(report, num)
        _CHAIR[num] = {pos: chair.get(k, set()) for pos, (k, it) in enumerate(zip(keys, items))
                       if not derive.clean_text(it.get("heading")) and not it.get("xml_speech_count")}
    return _CHAIR[num]

def make_rule2(base_kw, c=False, d=False, third_strict=False):
    inner = make_rule(**{k: v for k, v in base_kw.items() if k != "third"})
    TR = re.compile(r"^\W*(?:[IVX]+\s+|[a-z]\)\s*)?[–-]?\s*Dritte Beratung")
    def rule(report):
        num = derive.clean_text(report["protocol"]["dokumentnummer"])
        items = report.get("agenda_items") or []
        res = inner(report)
        weak = weak_vorgaenge(items) if c else None
        sections = chair_sections(report, num) if d else {}
        allv = vote_links.report_votes(report)
        for vid, matched in res.items():
            vote = allv[vid]; vn = {str(n) for n in vote.get("document_numbers") or []}
            if d:
                hits = [pos for pos, ns in sections.items() if ns & vn]
                if len(hits) == 1:
                    matched = {hits[0]: "drucksache_xml"}
            if c and len(matched) > 1:
                def strong(pos):
                    it = items[pos]
                    if vn & {str(x["dokumentnummer"]) for x in derive.xml_drucksachen(it) if x.get("dokumentnummer")}: return True
                    docs = [x for x in (it.get("api") or {}).get("linked_drucksachen") or [] if str(x.get("dokumentnummer")) in vn]
                    return any(str(x.get("vorgang_id")) not in weak[pos] for x in docs) or matched[pos] not in ("drucksache_vorgang",)
                keep = {pos: b for pos, b in matched.items() if strong(pos)}
                if keep: matched = keep
            if base_kw.get("third") and len(matched) > 1:
                pat = TR if third_strict else re.compile(r"(^|[\s–\-)])Dritte Beratung")
                t = [pos for pos in matched if pat.search(items[pos].get("heading") or "")]
                if len(t) == 1: matched = {t[0]: matched[t[0]]}
            res[vid] = matched
        return res
    return rule
