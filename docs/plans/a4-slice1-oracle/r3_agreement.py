"""R3: for every archive row, the dossier vote panel it links to must show the
same result badge, Drucksache links and Abweichler figure.

Usage: python3 -I r3_agreement.py <output_dir>
Pure HTML comparison; imports no repo code.
"""
import html
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import unquote

out = Path(sys.argv[1])
archive = (out / "votes" / "index.html").read_text(encoding="utf-8")

GAP = "Einzelstimmen unvollständig"
NONE = "Niemand stimmt anders als die Mehrheit"


def badge(fragment: str) -> str | None:
    """The badge span: vote-result… (with its nested note) or vote-no-result."""
    m = re.search(r'<span class="vote-result[^"]*"[^>]*>.*?</span>(?: <span class="vote-result-note">\(berechnet\)</span></span>)?', fragment, re.S)
    if m:
        return m.group(0)
    m = re.search(r'<span class="vote-no-result">.*?</span>', fragment, re.S)
    return m.group(0) if m else None


def doc_links(fragment: str) -> list[tuple[str, str | None]]:
    marker = '<span class="doc-link-list">'
    pos = fragment.find(marker)
    if pos == -1:
        return []
    pos += len(marker)
    element = re.compile(r'<(a|span) class="doc-link( muted)?"(?: href="([^"]*)")?>([^<]*)</\1>')
    result = []
    while (a := element.match(fragment, pos)):
        result.append((html.unescape(a.group(4)), html.unescape(a.group(3)) if a.group(3) else None))
        pos = a.end()
    if not fragment.startswith("</span>", pos):
        raise ValueError(f"unparsed doc-link-list at {fragment[pos:pos + 80]!r}")
    return result


rows = re.findall(r'<article class="archive-row"(.*?)</article>', archive, re.S)
print(f"archive rows: {len(rows)}")
pages: dict[str, str] = {}
problems = Counter()
examples: dict[str, list] = {}
checked = 0
abw_dist = Counter()


def note(kind: str, detail) -> None:
    problems[kind] += 1
    examples.setdefault(kind, []).append(detail)


for row in rows:
    attrs, _, body = row.partition(">")
    m = re.search(r'<h3><a href="([^"]+)">(.*?)</a>(.*?)</h3>', body, re.S)
    if not m:
        note("row without href", body[:200])
        continue
    href, title, after_title = m.groups()
    page_rel, _, anchor = html.unescape(href).partition("#")
    a_badge = badge(after_title)
    p = re.search(r"</h3><p>(.*?)</p>", body, re.S)
    a_links = doc_links(p.group(1) + "</p>") if p else []
    am = re.search(r'data-abweichler="(\d+)"', attrs)
    a_abw = int(am.group(1)) if am else None
    # The visible count line must agree with the attribute
    vis = re.search(r'<span class="archive-abweichler">(\d+) (?:stimmt|stimmen)', body)
    if (int(vis.group(1)) if vis else None) != (a_abw if a_abw else None):
        note("archive attr vs visible Abweichler", (href, a_abw, vis and vis.group(1)))

    page_path = (out / "votes" / unquote(page_rel)).resolve()
    if str(page_path) not in pages:
        if not page_path.exists():
            note("dossier page missing", href)
            continue
        pages[str(page_path)] = page_path.read_text(encoding="utf-8")
    page = pages[str(page_path)]
    ids = re.findall(rf'<section class="vote-panel" id="{re.escape(anchor)}">', page)
    if len(ids) != 1:
        note(f"anchor found {len(ids)}x", href)
        continue
    start = page.index(f'<section class="vote-panel" id="{anchor}">')
    end = page.find('<section class="vote-panel"', start + 10)
    nxt_top = page.find("</section></div>", start)  # fallback bound, generous
    section = page[start:end if end != -1 else len(page)]
    head = re.search(r'<div class="vote-head"><div><h3>Namentliche Abstimmung(.*?)</h3><p>(.*?)</p>', section, re.S)
    if not head:
        note("panel head not parsed", href)
        continue
    p_badge = badge(head.group(1))
    p_links = doc_links(head.group(2) + "</p>")
    labels = [int(x) for x in re.findall(r'<span class="vote-abweichler-label">[^<]*\((\d+)\):</span>', section)]
    if GAP in section:
        p_abw = None
    elif NONE in section:
        p_abw = 0
    elif labels:
        p_abw = sum(labels)
    else:
        p_abw = None
    checked += 1
    abw_dist["none" if a_abw is None else ("0" if a_abw == 0 else ">0")] += 1
    if a_badge != p_badge:
        note("badge", (href, a_badge, p_badge))
    if a_links != p_links:
        note("drucksache links", (href, a_links, p_links))
    if a_abw != p_abw:
        note("abweichler", (href, a_abw, p_abw, labels))

print(f"compared: {checked}; Abweichler on the archive: {dict(abw_dist)}")
print(f"disagreements: {sum(problems.values())} {dict(problems)}")
for kind, items in examples.items():
    print(f"--- {kind}")
    for item in items[:10]:
        print("   ", item)
