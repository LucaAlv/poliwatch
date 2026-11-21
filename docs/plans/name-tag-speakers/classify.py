"""Classify every non-chair <name> speaker turn (census.json: inside a <rede>;
outside2.py: outside any <rede>) into the kinds of docs/plans/name-tag-speakers.md.
Usage: python -I classify.py <store> census.json docs/plans/t4-acquire/name-tag-speakers.tsv out.tsv"""
import collections, csv, glob, json, re, sys
import xml.etree.ElementTree as ET

C, CENSUS, RECEIPT, OUT = sys.argv[1:5]
norm = lambda s: " ".join((s or "").split())
txt = lambda e: norm("".join(e.itertext()))
FLOOR = re.compile(r"[Nn]ächster? spricht|[Jj]etzt spricht|[Ee]s spricht|[Nn]ächste[rnm]? Redner|[Ll]etzte[rn]? Redner|Schlussredner|[Dd]as Wort|spricht (?:jetzt|nun)|erteile|eröffnet die Ministerin|Sie haben das Wort|hat (?:nun |jetzt )?(?:als nächste\w* )?\w* ?(?:Kolleg\w+ )?[^.!?]{0,60}das Wort")
QUESTION = re.compile(r"Zwischenfrage|Zwischenbemerkung|Frage|Anmerkung|Bemerkung", re.I)
# Hand decisions where the chair's words do not settle the kind (read in the XML)
FORCE_REDE = {("18/42", "ID1804201700")}  # Schavan: farewell words of the chair, then her Rede in the debate

census = json.load(open(CENSUS))
rows = []
units = {}
for o in census:
    key = (o["sitting"], o["rede_id"], o["name"])
    owner_name = re.sub(r"\(.*", "", re.sub(r"^\s*(Dr\.|Prof\.)\s*", "", o["owner"])).split(",")[0]
    same_as_owner = o["name"].split()[-1] in owner_name and o["name"].split()[0] in owner_name or (o["sitting"], o["rede_id"]) == ("18/36", "ID1803601400")
    if o["sitting"] == "18/4":
        kind = "oath_answer"
    elif same_as_owner:
        kind = "own_words"
    elif "Befragung" in o["heading"] and "befragung_frage" in o["owner_stored"]:
        kind = "befragung_antwort"
    elif "Befragung" in o["heading"] and "befragung_antwort" in o["owner_stored"]:
        kind = "befragung_frage"
    elif key in units:
        kind = units[key]
    else:
        prev_chair = bool(o["prev_label"]) and bool(re.match(r"\s*(Alters|Vize)?[Pp]räsident", o["prev_label"]))
        floor = prev_chair and FLOOR.search(o["prev_text"][-250:]) and not QUESTION.search(o["prev_text"][-160:])
        if o["index_in_rede"] == 0 or (o["sitting"], o["rede_id"]) in FORCE_REDE or floor:
            kind = "rede"
        else:
            kind = "zwischenfrage"
    units.setdefault(key, kind)
    rows.append(dict(population="in_rede", sitting=o["sitting"], rede_id=o["rede_id"], top=o["top"], name_tag=o["tag"].rstrip(": ").strip(),
                     person=o["name"], fraktion=o["fraktion"] or "", role=o["role"] or "", host_owner=re.sub(r"\s+", " ", o["owner"]).rstrip(": "),
                     host_stored_as=",".join(o["owner_stored"]) or "nothing", turn_index=o["index_in_rede"], words=o["words"],
                     kind=kind, redner_id_candidates=",".join(sorted({c[0] for c in o["id_candidates"]})),
                     in_receipt="",
                     opening=o["opening"][:90]))

# Receipt membership: a receipt row with the same sitting, <rede> id and word count
receipt = set()
for line in open(RECEIPT, encoding="utf-8"):
    f = line.rstrip("\n").split("\t")
    if len(f) >= 5 and f[0][:2] in ("18", "19", "20"):
        receipt.add((f[0], f[1], norm(f[3]), f[4]))
for r in rows:
    r["in_receipt"] = "yes" if any(k[0] == r["sitting"] and k[1] == r["rede_id"] and k[3] == str(r["words"]) for k in receipt) else "no"

# Outside any <rede>
ROLE = re.compile(r"^\s*(Alters|Vize)?[Pp]räsiden", re.I)
ids = collections.defaultdict(lambda: collections.defaultdict(set))
roots = {}
for f in glob.glob(f"{C}/data/xml/plenarprotokoll-*.xml"):
    r = ET.parse(f).getroot(); sit = f.split("plenarprotokoll-")[1][:-4].replace("-", "/")
    roots[sit] = r
    for red in r.iter("redner"):
        n = red.find("name")
        if n is not None and red.get("id"):
            ids[sit.split("/")[0]][norm(f"{n.findtext('vorname') or ''} {n.findtext('nachname') or ''}").casefold()].add(red.get("id"))
OUTSIDE_KIND = {"Wolf Biermann": "ansprache", "Frank-Walter Steinmeier": "oath_answer", "Dietmar Bartsch": "remark"}
for sit, r in sorted(roots.items(), key=lambda kv: tuple(map(int, kv[0].split("/")))):
    v = r.find("sitzungsverlauf")
    if v is None:
        continue
    chairs = set()
    for n in v.iter("name"):
        m = re.match(r"^\s*(?:Alters|Vize)?[Pp]räsident(?:in)?\s+(?:Dr\.\s+)?(.+?)\s*:?\s*$", txt(n))
        if m:
            chairs.add(norm(m.group(1)))
    inrede = {id(x) for rd in v.iter("rede") for x in rd.iter()}
    for par in [e for e in v.iter() if id(e) not in inrede and e.tag not in ("rede", "redner", "p", "name")]:
        heading = " | ".join(txt(p) for p in par.findall("p") if (p.get("klasse") or "").startswith("T_"))
        kids = list(par)
        seen = collections.Counter()
        for i, c in enumerate(kids):
            if c.tag != "name":
                continue
            lab = txt(c)
            if ROLE.search(lab) or lab.startswith("(") or any(lab.rstrip(": ").endswith(ch) for ch in chairs):
                continue
            ps = []
            for d in kids[i + 1:]:
                if d.tag in ("name", "rede", "tagesordnungspunkt") or (d.tag == "p" and d.get("klasse") == "redner"):
                    break
                if d.tag == "p":
                    ps.append(txt(d))
            t = " ".join(ps)
            s = lab.rstrip(": ").strip()
            role = ""
            frak = ""
            m = re.search(r"\(([^()]*)\)\s*$", s)
            if m and "," not in s[: m.start()]:
                frak = norm(m.group(1)); s = s[: m.start()]
            if "," in s:
                s, role = s.split(",", 1); role = norm(role)
            person = norm(re.sub(r"\b(Dr\.|Prof\.)\s*", "", re.sub(r"\([^()]*\)", "", re.sub(r"^Bundespräsident\s+", "", s))))
            kind = OUTSIDE_KIND.get(person) or ("fragestunde_frage" if "Fragestunde" in heading else "rede")
            seen[person] += 1
            rows.append(dict(population="outside_rede", sitting=sit, rede_id="", top=par.get("top-id") or par.tag, name_tag=lab.rstrip(": ").strip(),
                             person=person, fraktion=frak, role=role, host_owner="", host_stored_as="no <rede>", turn_index=i, words=len(t.split()),
                             kind=kind, redner_id_candidates=",".join(sorted(ids[sit.split("/")[0]].get(person.casefold(), set()))),
                             in_receipt="no", opening=t[:90]))

# Unit numbering: one unit per (sitting, host, person, kind) inside a <rede>; outside, Steinmeier's two turns are one
# One reviewed entry per (sitting, host <rede> or TOP, printed person): all turns
# of one person in one host share a kind in every case found.
rows.sort(key=lambda r: (r["population"] != "in_rede", tuple(map(int, r["sitting"].split("/"))), r["rede_id"] or r["top"], int(r["turn_index"])))
unit_no = {}
for r in rows:
    r["entry"] = unit_no.setdefault((r["sitting"], r["rede_id"] or r["top"], r["person"]), len(unit_no) + 1)
# Proposed binding: the one Redner-ID this WP's XML prints for the name; reviewed exceptions
BIND = {"Johanna Wanka": "999990003 (of 999990003, 999990030: the id of her 2014 sittings)",
        "Annette Schavan": "11003836 (her MdB-Stammdaten id, mdb_zugehoerigkeiten; no WP 18 XML prints one)",
        "Jutta Blankau-Rosenfeldt": "none: bind by DIP person 1828",
        "Wolf Biermann": "none (guest; Ansprache)"}
for r in rows:
    if r["kind"] == "own_words":
        r["proposed_redner_id"] = "host owner's"
    elif r["kind"] in ("remark", "oath_answer"):
        r["proposed_redner_id"] = "- (not stored)"
    else:
        r["proposed_redner_id"] = BIND.get(r["person"]) or r["redner_id_candidates"]
cols = ["population", "sitting", "rede_id", "top", "turn_index", "name_tag", "person", "fraktion", "role", "host_owner", "host_stored_as",
        "words", "kind", "entry", "proposed_redner_id", "in_receipt", "opening"]
with open(OUT, "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, cols, delimiter="\t", extrasaction="ignore", lineterminator="\n")
    fh.write("# Every speaker turn printed under a <name> that is not the chair, in the 803 XML files of the reference store (2026-11-20), "
             "inside another speaker's <rede> (in_rede) or outside any <rede> (outside_rede). Kinds and columns: docs/plans/name-tag-speakers.md. "
             "Made by docs/plans/name-tag-speakers/census.py and classify.py.\n")
    w.writeheader()
    for r in rows:
        w.writerow(r)
c = collections.Counter()
for r in rows:
    c[(r["population"], r["kind"])] += 1
for k, n in sorted(c.items()):
    print(k, n, sum(r["words"] for r in rows if (r["population"], r["kind"]) == k), len({r["entry"] for r in rows if (r["population"], r["kind"]) == k}))
print("receipt rows matched", sum(r["in_receipt"] == "yes" for r in rows))
