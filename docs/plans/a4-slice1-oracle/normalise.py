"""Copy an output dir's text files into DEST with the slice 0 volatile tokens
normalised (plan "Slice 0 result", Recipe): the generation name g-…, ISO
timestamps, the "Stand … MEZ" line, the build revision. .gz files are
gunzipped (name without .gz). SQLite and lock files are skipped.

Usage: python3 -I normalise.py SRC DEST
"""
import gzip
import re
import shutil
import sys
from pathlib import Path

src, dest = Path(sys.argv[1]), Path(sys.argv[2])
if dest.exists():
    shutil.rmtree(dest)

RULES = [
    (re.compile(r"g-[0-9a-f]{12}"), "g-GEN"),
    (re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?"), "ISO-TS"),
    (re.compile(r"Stand \d{1,2}\.\d{1,2}\.\d{4},? \d{1,2}:\d{2}(?: Uhr)?(?: MEZ| MESZ)?"), "Stand STAMP"),
    (re.compile(r"\b(?=[0-9]*[a-f])[0-9a-f]{12}(?:-dirty-[0-9a-f]+|-unverified(?:-[0-9a-f]+)?)?\b"), "REV"),
]
SKIP = (".sqlite", ".lock", ".sqlite-journal", ".sqlite-wal", ".sqlite-shm")
TEXT = (".html", ".json", ".md", ".csv", ".txt", ".xml", ".js", ".css", ".cff", ".ndjson", ".jsonl", ".svg")

for path in sorted(src.rglob("*")):
    rel = path.relative_to(src)
    if not path.is_file() or path.name.endswith(SKIP) or any(part.endswith(".private") for part in rel.parts):
        continue
    if rel.parts[0] in ("src-base", "src-tip"):
        continue
    data = path.read_bytes()
    name = rel
    if path.suffix == ".gz":
        try:
            data = gzip.decompress(data)
        except OSError:
            pass
        else:
            name = rel.with_suffix("")
    target = dest / name
    target.parent.mkdir(parents=True, exist_ok=True)
    if name.suffix in TEXT:
        text = data.decode("utf-8", errors="surrogateescape")
        for pattern, repl in RULES:
            text = pattern.sub(repl, text)
        target.write_text(text, encoding="utf-8", errors="surrogateescape")
    else:
        target.write_bytes(data)
