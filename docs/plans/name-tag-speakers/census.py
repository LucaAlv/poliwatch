"""Census of non-chair <name> turns inside another speaker's <rede> (read-only).

Usage: python -I census.py <store dir> <out.json>
"""
import collections, glob, json, re, sqlite3, sys
import xml.etree.ElementTree as ET

C = sys.argv[1]
db = sqlite3.connect(f"file:{C}/data/bundestag-pulse.sqlite?mode=ro&immutable=1", uri=True)
norm = lambda s: " ".join((s or "").split())
tabs = ("speeches", "contributions", "withheld_units", "withheld_turns")
blob = {t: "\n".join(norm(x) for (x,) in db.execute(f"select text from {t}")) for t in tabs}
ROLE = re.compile(r"^\s*(Alters|Vize)?[Pp]räsiden", re.I)

def txt(e):
    return norm("".join(e.itertext()))

# Redner-IDs printed for each name per WP, from every marker and TOC entry
ids = collections.defaultdict(lambda: collections.defaultdict(set))
files = sorted(glob.glob(f"{C}/data/xml/plenarprotokoll-*.xml"))
roots = {}
for f in files:
    r = ET.parse(f).getroot()
    sit = f.split("plenarprotokoll-")[1][:-4].replace("-", "/")
    roots[sit] = r
    wp = sit.split("/")[0]
    for red in r.iter("redner"):
        n = red.find("name")
        if n is None or not red.get("id"):
            continue
        key = norm(f"{n.findtext('vorname') or ''} {n.findtext('nachname') or ''}").casefold()
        ids[wp][key].add((red.get("id"), norm(n.findtext("fraktion") or ""), norm(n.findtext("rolle/rolle_lang") or "")))

stored = {}
for kind, rid, pid in db.execute("select 'speech', rede_id, protocol_id from speeches union all select kind, rede_id, protocol_id from contributions union all select 'withheld:'||reason, rede_id, protocol_id from withheld_units"):
    stored.setdefault(rid, []).append(kind)

def parse_tag(nm):
    s = nm.rstrip(": ").strip()
    frak = None
    m = re.search(r"\(([^()]*)\)\s*$", s)
    role = None
    if m and not re.search(r",", s[: m.start()]):
        frak = norm(m.group(1))
        s = s[: m.start()]
    if "," in s:
        s, role = s.split(",", 1)
        role = norm(role)
    s = re.sub(r"\([^()]*\)", "", s)
    s = re.sub(r"\b(Dr\.|Prof\.|h\. ?c\.|Dr\.-Ing\.)\s*", "", s)
    return norm(s), frak, role

out = []
for sit, r in roots.items():
    wp = sit.split("/")[0]
    verlauf = r.find("sitzungsverlauf")
    if verlauf is None:
        continue
    chairs = set()
    for n in verlauf.iter("name"):
        t = txt(n)
        m = re.match(r"^\s*(?:Alters|Vize)?[Pp]räsident(?:in)?\s+(?:Dr\.\s+)?(.+?)\s*:?\s*$", t)
        if m:
            chairs.add(norm(m.group(1)))
    for top in verlauf.iter("tagesordnungspunkt"):
        heading = " | ".join(txt(p) for p in top.findall("p") if (p.get("klasse") or "").startswith("T_"))[:300]
        for rede in top.iter("rede"):
            kids = list(rede)
            rp = rede.find("p[@klasse='redner']")
            red = rp.find("redner") if rp is not None else None
            owner = norm((red.tail or "") if red is not None else "")
            owner_id = red.get("id") if red is not None else None
            segs = []  # (label, kind, paragraphs)
            for c in kids:
                if c.tag == "name":
                    segs.append([txt(c), "name", []])
                elif c.tag == "p" and c.get("klasse") == "redner":
                    rr = c.find("redner")
                    segs.append([norm(rr.tail or "") if rr is not None else txt(c), "redner", []])
                    t = norm((rr.tail or "").partition(":")[2]) if rr is not None else ""
                    if t:
                        segs[-1][2].append(t)
                elif c.tag == "p" and segs:
                    segs[-1][2].append(txt(c))
                elif c.tag == "kommentar" and segs:
                    segs[-1][2].append("{" + txt(c) + "}")
            for i, (label, kind, ps) in enumerate(segs):
                if kind != "name":
                    continue
                chair_like = bool(ROLE.search(label)) or label.startswith("(") or any(label.rstrip(": ").strip().endswith(ch) for ch in chairs)
                if chair_like:
                    continue
                words_ps = [p for p in ps if not p.startswith("{")]
                text = " ".join(words_ps)
                w = len(text.split())
                name, frak, role = parse_tag(label)
                ws = text.split()
                phrase = " ".join(ws[len(ws) // 2: len(ws) // 2 + 8])
                where = [t for t in tabs if phrase and phrase in blob[t]] if w >= 4 else []
                prev = segs[i - 1] if i else None
                nxt = segs[i + 1] if i + 1 < len(segs) else None
                cands = sorted(ids[wp].get(name.casefold(), set()))
                out.append({
                    "sitting": sit, "rede_id": rede.get("id"), "top": top.get("top-id"), "heading": heading,
                    "owner": owner, "owner_id": owner_id, "owner_stored": stored.get(rede.get("id"), []),
                    "tag": label, "name": name, "fraktion": frak, "role": role, "words": w,
                    "index_in_rede": i, "segments_in_rede": len(segs),
                    "prev_label": prev[0] if prev else None,
                    "prev_text": " ".join(p for p in prev[2] if not p.startswith("{"))[-400:] if prev else "",
                    "next_label": nxt[0] if nxt else None,
                    "next_text": " ".join(p for p in nxt[2] if not p.startswith("{"))[:300] if nxt else "",
                    "opening": text[:300], "closing": text[-200:], "in_store": where,
                    "id_candidates": cands,
                })
json.dump(out, open(sys.argv[2], "w"), ensure_ascii=False, indent=1)
c = collections.Counter((o["words"] >= 15, bool(o["in_store"])) for o in out)
print(len(out), c)
