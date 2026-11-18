#!/usr/bin/env python3
"""Compare a release's speeches with CPP-BT's speech metadata, sitting by sitting.

CPP-BT is the Corpus der Plenarprotokolle des Deutschen Bundestages (Zenodo concept
DOI 10.5281/zenodo.4542661, CC0). This script is the release review's step 4
(``docs/release-review.md``). It is standard library only and imports no module of
this project, so a bug in the project cannot hide in its own check. Nothing in the
build, the release script or CI calls it.

It reads three things and writes one TSV:

* ``--export``: the release's SQLite (``bundestag-pulse.sqlite`` or ``.sqlite.gz``),
  opened read-only;
* ``--xml-dir``: the source ``plenarprotokoll-<WP>-<NR>.xml`` files, used only to say
  what an id only CPP-BT has is (by its parent element);
* ``--cpp-bt``: the speech metadata CSV, or the zip that holds exactly one.

The exit code is 0 when the comparison ran, whatever it found; 2 when an input could
not be read (a clear message, never a traceback). The script reports; the review
judges. Agreement is no proof that both sides are right, and disagreement is a lead.

Keys, each defined once:

* ``sitting_key``: ``18/100``. CPP-BT appends `` (neu)`` to a reprinted protocol.
* ``source_rede_id``: the Bundestag's ``<rede id>``. Ours may carry ``:N`` when the
  parser splits another member's speech out of one element; ids that start with
  ``nested:`` and empty ids (Fragestunde) are not Bundestag ids and are skipped by
  name, and counted, never by a failed match.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import os
import re
import shutil
import sqlite3
import statistics
import sys
import tempfile
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
import zlib
from collections import Counter, defaultdict
from pathlib import Path

SITTING_RE = re.compile(r"^(\d{1,3})/(\d{1,4})(?: \(neu\))?$")
REDE_ID_RE = re.compile(r"^ID\d{6,14}$")
CSV_FIELD_LIMIT = 16 * 1024 * 1024
CPP_COLUMNS = (
    "protokoll_nr", "rede_id", "redner_nachname", "redner_fraktion", "redner_rolle_kurz", "tokens",
)
#: First values, to be calibrated on the first run and written into the checklist.
RATIO_TOLERANCE = 0.15
RATIO_MIN_TOKENS = 50

#: The annex rules of ``validate_dip_protocol.ANNEX_EXCLUSIONS``, copied so the script
#: imports no project module (a test pins both lists to the same rule names).
ANNEX_RULES = (
    ("paragraph_31", re.compile(r"erkl(?:ä|ae)rung(?:en)? nach § ?31\b.*")),
    ("paragraph_31_continuation", re.compile(r"zu der abstimmung über .+")),
    ("reprint", re.compile(r"neudruck eines redebeitrages\b.*")),
)
#: What an id only CPP-BT has can be, in the order it is looked for.
CLASSES = (
    "withheld", "paragraph_31", "paragraph_31_continuation", "reprint", "in_top_presidium",
    "in_top_other", "annex_zu_protokoll", "annex_other", "outside_top", "unclassified",
)
#: Classes the review reads by hand; the rest are named and explained by a rule.
READ_BY_HAND = {"in_top_presidium", "in_top_other", "annex_zu_protokoll", "annex_other", "outside_top", "unclassified"}
PRESIDIUM_ROLES = ("praesident", "präsident", "vizepraesident", "vizepräsident", "alterspraesident",
                   "alterspräsident", "sitzungsleitung")


class InputError(Exception):
    """An input the script cannot read; the message is the whole report."""


# ---------------------------------------------------------------- keys

def sitting_key(value: object) -> str | None:
    """``"18/100"`` for ``"18/100"`` and ``"18/100 (neu)"``; None for anything else."""
    if not isinstance(value, str):
        return None
    match = SITTING_RE.fullmatch(value.strip())
    return f"{int(match.group(1))}/{int(match.group(2))}" if match else None


def source_rede_id(value: object) -> str | None:
    """The Bundestag id behind one of ours, or None for ids that are not one."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or text.startswith("nested:"):
        return None
    text = text.split(":", 1)[0]
    return text if REDE_ID_RE.fullmatch(text) else None


def fold_name(value: object) -> str:
    """Case-folded NFC text without brackets; diacritics are kept so a spelling
    difference shows (the known-differences file lists it)."""
    if not isinstance(value, str):
        return ""
    text = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", unicodedata.normalize("NFC", value))
    return re.sub(r"\s+", " ", text).strip().casefold()


def our_surname_text(display_name: object) -> str:
    """The name part of a ``display_name`` such as ``Dr. Jan Foo, MdB, AfD``."""
    if not isinstance(display_name, str):
        return ""
    return fold_name(display_name.split(",", 1)[0])


def surnames_agree(ours: str, theirs: object) -> bool | None:
    """True when every word of CPP-BT's surname is a word of our name (a hyphen
    separates words, so ``Alabali-Radovan`` and ``Alabali Radovan`` agree and
    ``Bluhm`` agrees with ``Bluhm-Förster``); None when either side has none."""
    their = fold_name(theirs)
    if not ours or not their or their == "na":
        return None
    words = set(re.split(r"[\s-]+", ours))
    return all(word in words for word in re.split(r"[\s-]+", their) if word)


FRAKTION_ALIASES = {"fraktionslos": "fraktionslos", "parteilos": "fraktionslos"}


def fraktion_key(value: object) -> str | None:
    """A Fraktion label folded for comparison; None for missing or "NA"."""
    if not isinstance(value, str):
        return None
    text = unicodedata.normalize("NFC", value).strip().casefold()
    if text in ("", "na"):
        return None
    text = re.sub(r"^gruppe\s+", "", text)
    text = re.sub(r"[^\w/]+", " ", text).strip()
    return FRAKTION_ALIASES.get(text, text)


# ---------------------------------------------------------------- inputs

def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def open_export(path: Path, workdir: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise InputError(f"--export {path}: not a file")
    source = path
    if path.suffix == ".gz":
        source = workdir / "export.sqlite"
        try:
            with gzip.open(path, "rb") as src, source.open("wb") as dst:
                shutil.copyfileobj(src, dst)
        except (OSError, EOFError, zlib.error) as error:
            raise InputError(f"--export {path}: cannot decompress ({error})") from error
    connection = None
    try:
        connection = sqlite3.connect(f"{source.resolve().as_uri()}?mode=ro", uri=True)
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    except sqlite3.DatabaseError as error:
        if connection is not None:
            connection.close()
        raise InputError(f"--export {path}: not a SQLite database ({error})") from error
    missing = {"protocols", "speeches", "contributions", "withheld_units", "mps"} - tables
    if missing:
        connection.close()
        raise InputError(f"--export {path}: missing tables {sorted(missing)}")
    return connection


def read_cpp_bt(path: Path):
    """Yield one dict per CPP-BT row with the columns this script needs."""
    if not path.is_file():
        raise InputError(f"--cpp-bt {path}: not a file")
    csv.field_size_limit(CSV_FIELD_LIMIT)
    archive = None
    try:
        if path.suffix == ".zip":
            archive = zipfile.ZipFile(path)
            members = [info for info in archive.infolist() if info.filename.lower().endswith(".csv")]
            if len(members) != 1:
                raise InputError(f"--cpp-bt {path}: the zip must hold exactly one .csv, it holds {len(members)}")
            raw = archive.open(members[0])
        else:
            raw = path.open("rb")
        text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="", errors="replace")
        reader = csv.DictReader(text, strict=True)
        missing = [name for name in CPP_COLUMNS if name not in (reader.fieldnames or [])]
        if missing:
            raise InputError(f"--cpp-bt {path}: missing columns {missing}")
        for row in reader:
            yield {name: row.get(name) or "" for name in CPP_COLUMNS}
    except zipfile.BadZipFile as error:
        raise InputError(f"--cpp-bt {path}: not a zip ({error})") from error
    except csv.Error as error:
        raise InputError(
            f"--cpp-bt {path}: unreadable CSV near row {reader.line_num if 'reader' in locals() else 0} "
            f"({error}); an unbalanced quote or a field over {CSV_FIELD_LIMIT} bytes") from error
    finally:
        if archive is not None:
            archive.close()


# ---------------------------------------------------------------- our side

def load_ours(connection: sqlite3.Connection) -> dict:
    """Per sitting: source rede ids by table, one name and Fraktion per id, our word count."""
    sittings: dict[str, dict] = {}
    sitting_of_protocol: dict[object, str] = {}
    skipped = Counter()
    for protocol_id, number in connection.execute("SELECT id, document_number FROM protocols"):
        key = sitting_key(number)
        if key is None:
            skipped["protocol_number_unparsed"] += 1
            continue
        sitting_of_protocol[protocol_id] = key
        sittings.setdefault(key, {"speech": set(), "contribution": set(), "withheld": set(), "name": {},
                                  "fraktion": {}, "words": Counter()})

    def add(table: str, protocol_id, rede_id, name, fraktion, text) -> None:
        key = sitting_of_protocol.get(protocol_id)
        if key is None:
            return
        source = source_rede_id(rede_id)
        if source is None:
            skipped["no_bundestag_id" if not rede_id else "nested_id"] += 1
            return
        sitting = sittings[key]
        sitting[table].add(source)
        if ":" not in str(rede_id):  # the part that carries the element's own speaker
            if name:
                sitting["name"].setdefault(source, our_surname_text(name))
            if fraktion:
                sitting["fraktion"].setdefault(source, fraktion)
        if table == "speech":
            sitting["words"][source] += len((text or "").split())  # a speech with no text counts 0, not "unknown"

    for row in connection.execute(
            "SELECT s.protocol_id, s.rede_id, m.display_name, s.fraktion, s.text FROM speeches s "
            "LEFT JOIN mps m ON m.id = s.mp_id"):
        add("speech", *row[:4], row[4])
    for row in connection.execute(
            "SELECT c.protocol_id, c.rede_id, COALESCE(m.display_name, c.speaker_name), c.fraktion "
            "FROM contributions c LEFT JOIN mps m ON m.id = c.mp_id"):
        add("contribution", *row, None)
    for row in connection.execute(
            "SELECT protocol_id, rede_id, speaker_name, fraktion FROM withheld_units"):
        add("withheld", *row, None)
    return {"sittings": sittings, "skipped": skipped}


# ---------------------------------------------------------------- their side and classification

def classify_only_theirs(xml_dir: Path, key: str, ids: dict[str, dict], withheld: set[str]) -> dict[str, str]:
    """Class of each id (a key of ``ids``) that only CPP-BT has in a sitting we hold."""
    result: dict[str, str] = {}
    pending = {rede_id for rede_id in ids if rede_id not in withheld}
    for rede_id in ids:
        if rede_id in withheld:
            result[rede_id] = "withheld"
    if not pending:
        return result
    wp, number = key.split("/")
    xml_path = xml_dir / f"plenarprotokoll-{wp}-{number}.xml"
    try:
        root = ET.parse(xml_path).getroot()
    except (OSError, ET.ParseError):
        return {**result, **{rede_id: "unclassified" for rede_id in pending}}
    parents = {child: parent for parent in root.iter() for child in parent}
    found: dict[str, ET.Element] = {}
    for element in root.iter("rede"):
        rede_id = element.get("id")
        if rede_id in pending:
            found[rede_id] = element
    for rede_id in pending:
        element = found.get(rede_id)
        if element is None:
            result[rede_id] = "unclassified"
            continue
        result[rede_id] = _classify_element(element, parents, ids[rede_id]["role"])
    return result


def _classify_element(element: ET.Element, parents: dict, role: str) -> str:
    node = parents.get(element)
    while node is not None:
        if node.tag == "anlagen-text":
            title = re.sub(r"\s+", " ", (node.get("anlagen-typ") or "")).strip().casefold()
            for rule, pattern in ANNEX_RULES:
                if pattern.fullmatch(title):
                    return rule
            return "annex_zu_protokoll" if "zu protokoll" in title else "annex_other"
        if node.tag == "tagesordnungspunkt":
            lowered = role.casefold()
            return "in_top_presidium" if any(word in lowered for word in PRESIDIUM_ROLES) else "in_top_other"
        if node.tag == "sitzungsverlauf":
            return "outside_top"
        node = parents.get(node)
    return "unclassified"


def compare(connection: sqlite3.Connection, cpp_rows, xml_dir: Path, wp_min: int) -> dict:
    ours = load_ours(connection)
    theirs: dict[str, dict] = defaultdict(lambda: {"ids": {}})
    theirs_skipped = Counter()
    duplicates = 0
    for row in cpp_rows:
        key = sitting_key(row["protokoll_nr"])
        rede_id = row["rede_id"].strip()
        if key is None or not REDE_ID_RE.fullmatch(rede_id):
            theirs_skipped["row_unparsed"] += 1
            continue
        if int(key.split("/")[0]) < wp_min:
            continue
        if rede_id in theirs[key]["ids"]:
            duplicates += 1
            continue
        try:
            tokens = int(row["tokens"])
        except ValueError:
            tokens = None
        theirs[key]["ids"][rede_id] = {
            "surname": row["redner_nachname"], "fraktion": row["redner_fraktion"],
            "role": row["redner_rolle_kurz"], "tokens": tokens}

    def order(key: str) -> tuple[int, int]:
        wp, number = key.split("/")
        return int(wp), int(number)

    all_keys = sorted({key for key in ours["sittings"] if int(key.split("/")[0]) >= wp_min} | set(theirs),
                      key=order)
    rows, differences = [], []
    totals = Counter()
    by_class_total = Counter()
    for key in all_keys:
        mine = ours["sittings"].get(key)
        their = theirs.get(key)
        row = {"sitting": key, "ours": None, "theirs": None, "both": None, "only_ours": None,
               "only_theirs": None, "classes": Counter(), "surname_diffs": None, "fraktion_diffs": None,
               "ratio_outliers": None, "ratio_median": None}
        if mine is not None:
            row["ours"] = len(mine["speech"] | mine["contribution"])
        if their is not None:
            row["theirs"] = len(their["ids"])
        if mine is None and their is not None:
            totals["theirs_ids_in_sittings_we_lack"] += len(their["ids"])
            totals["sittings_only_theirs"] += 1
        elif their is None and mine is not None:
            totals["sittings_only_ours"] += 1
        elif mine is not None and their is not None:
            totals["sittings_both"] += 1
            held = mine["speech"] | mine["contribution"]
            both = held & set(their["ids"])
            only_ours = held - set(their["ids"])
            only_theirs = set(their["ids"]) - held
            row.update(both=len(both), only_ours=len(only_ours), only_theirs=len(only_theirs))
            totals["ids_both"] += len(both)
            totals["ids_only_ours"] += len(only_ours)
            totals["ids_only_theirs"] += len(only_theirs)
            for rede_id in sorted(only_ours):
                differences.append((key, "only_ours", rede_id, "", "", ""))
            classes = classify_only_theirs(
                xml_dir, key, {rede_id: their["ids"][rede_id] for rede_id in only_theirs}, mine["withheld"])
            for rede_id in sorted(only_theirs):
                klass = classes[rede_id]
                row["classes"][klass] += 1
                by_class_total[klass] += 1
                differences.append((key, "only_theirs:" + klass, rede_id, "", their["ids"][rede_id]["surname"], ""))
            surname_diffs = fraktion_diffs = 0
            for rede_id in sorted(both):
                info = their["ids"][rede_id]
                agree = surnames_agree(mine["name"].get(rede_id, ""), info["surname"])
                if agree is None:
                    totals["surname_not_compared"] += 1
                else:
                    totals["surname_compared"] += 1
                if agree is False:
                    surname_diffs += 1
                    differences.append((key, "surname", rede_id, mine["name"].get(rede_id, ""), info["surname"], ""))
                a, b = fraktion_key(mine["fraktion"].get(rede_id)), fraktion_key(info["fraktion"])
                if a is None or b is None:
                    totals["fraktion_not_compared"] += 1
                elif a != b:
                    fraktion_diffs += 1
                    differences.append((key, "fraktion", rede_id, mine["fraktion"].get(rede_id, ""), info["fraktion"], ""))
            row.update(surname_diffs=surname_diffs, fraktion_diffs=fraktion_diffs)
            totals["surname_diffs"] += surname_diffs
            totals["fraktion_diffs"] += fraktion_diffs
            ratios = {}
            for rede_id in sorted(both):
                tokens = their["ids"][rede_id]["tokens"]
                words = mine["words"].get(rede_id)
                if tokens and tokens > RATIO_MIN_TOKENS and words is not None:
                    ratios[rede_id] = words / tokens
            totals["ratio_compared"] += len(ratios)
            if ratios:
                median = statistics.median(ratios.values())
                row["ratio_median"] = round(median, 3)
                # a median of 0 (most Reden of the sitting have no stored text) leaves no scale: list every Rede, deviation 1
                deviations = {rede_id: (abs(value / median - 1) if median > 0 else 1.0) for rede_id, value in ratios.items()}
                outliers = sorted(((deviations[rede_id], rede_id, value) for rede_id, value in ratios.items()
                                   if deviations[rede_id] > RATIO_TOLERANCE), key=lambda item: (-item[0], item[1]))
                row["ratio_outliers"] = len(outliers)
                totals["ratio_outliers"] += len(outliers)
                for deviation, rede_id, value in outliers:
                    differences.append((key, "ratio", rede_id, f"{mine['words'][rede_id]}", f"{their['ids'][rede_id]['tokens']}",
                                        f"ratio {value:.3f}, sitting median {median:.3f}, deviation {deviation:.3f}"))
            else:
                row["ratio_outliers"] = None
        rows.append(row)
    return {"rows": rows, "differences": differences, "totals": totals, "by_class": by_class_total,
            "ours_skipped": ours["skipped"], "theirs_skipped": theirs_skipped, "duplicates": duplicates}


# ---------------------------------------------------------------- output

def refuse_empty_comparison(result: dict) -> None:
    """Stop a run whose join found nothing to compare: a changed format must not read as a pass."""
    totals = result["totals"]
    if totals["sittings_both"] == 0:
        raise InputError("no sitting is held by both sides: the protocol numbers of one input did not parse")
    unparsed = result["theirs_skipped"]["row_unparsed"]
    read = sum(totals[name] for name in ("ids_both", "ids_only_theirs", "theirs_ids_in_sittings_we_lack"))
    if unparsed * 100 > unparsed + read:
        raise InputError(f"{unparsed} CPP-BT rows have no readable protocol number or rede id (over 1%): the format changed")
    if totals["ids_both"] and totals["ratio_compared"] == 0:
        raise InputError("no Rede could be compared by token count: the tokens column did not parse")


def tsv_line(values) -> str:
    cleaned = []
    for value in values:
        text = "" if value is None else str(value)
        cleaned.append(re.sub(r"[\t\r\n]+", " ", text))
    return "\t".join(cleaned) + "\n"


def known_differences(path: Path | None) -> set[tuple[str, str, str, str]]:
    """The known-differences file: ``(field, rede_id, ours, theirs)`` with a reason.

    A row with an empty ``rede_id`` covers every Rede with that pair of values (a name
    change or a spelling); a row with an id covers that Rede only. Both values are
    folded as the report folds them. A row without a reason is ignored. An ``only_theirs``
    row must name its Rede: with an empty id it would mark every id only CPP-BT holds as known."""
    if path is None or not path.is_file():
        return set()
    known = set()
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
    except UnicodeDecodeError as error:
        raise InputError(f"--known-differences {path}: not UTF-8 ({error})") from error
    for row in rows:
        if True:
            if row.get("field") and (row.get("reason") or "").strip():
                if row["field"] == "only_theirs" and not (row.get("rede_id") or "").strip():
                    raise InputError(f"--known-differences {path}: an only_theirs row has no rede_id "
                                     "and would mark every Rede only CPP-BT holds as known")
                known.add((row["field"], (row.get("rede_id") or "").strip(),
                           fold_difference(row["field"], row.get("ours") or ""),
                           fold_difference(row["field"], row.get("theirs") or "")))
    return known


def fold_difference(field: str, value: str) -> str:
    return (fold_name(value) if field == "surname" else (fraktion_key(value) or ""))


def is_known(known, field: str, rede_id: str, ours: str, theirs: str) -> bool:
    pair = (fold_difference(field, ours), fold_difference(field, theirs))
    return (field, "", *pair) in known or (field, rede_id, *pair) in known


def write_report(result: dict, out: Path, inputs: list[tuple[str, str, str]], known: set[tuple[str, str]],
                 by_wp_extra: dict) -> None:
    classes = list(CLASSES)
    with out.open("w", encoding="utf-8", newline="") as handle:
        handle.write("# sittings: one row per sitting; an empty cell means the side does not hold the sitting\n")
        handle.write(tsv_line(["sitting", "ours", "theirs", "both", "only_ours", "only_theirs"] + classes
                              + ["surname_diffs", "fraktion_diffs", "ratio_median", "ratio_outliers"]))
        for row in result["rows"]:
            counts = [row["classes"].get(name, 0) if row["only_theirs"] is not None else None for name in classes]
            handle.write(tsv_line([row["sitting"], row["ours"], row["theirs"], row["both"], row["only_ours"],
                                   row["only_theirs"]] + counts + [row["surname_diffs"], row["fraktion_diffs"],
                                                                  row["ratio_median"], row["ratio_outliers"]]))
        handle.write("\n# differences: one row per difference; status is known when the known-differences file lists it\n")
        handle.write(tsv_line(["sitting", "kind", "rede_id", "ours", "theirs", "detail", "status"]))
        for key, kind, rede_id, ours, theirs, detail in result["differences"]:
            field = kind.split(":")[0]
            if kind.startswith("only_theirs:"):
                klass = kind.split(":", 1)[1]
                if klass not in READ_BY_HAND:
                    status = "classified"
                else:
                    status = "known" if is_known(known, "only_theirs", rede_id, "", "") else "read_by_hand"
            elif field in ("surname", "fraktion"):
                status = "known" if is_known(known, field, rede_id, ours, theirs) else "read_by_hand"
            else:
                status = "read_by_hand"
            handle.write(tsv_line([key, kind, rede_id, ours, theirs, detail, status]))
        handle.write("\n# summary\n")
        handle.write(tsv_line(["item", "value"]))
        for name, digest, note in inputs:
            handle.write(tsv_line([f"input:{name}", f"{digest}  {note}"]))
        for name, value in sorted(result["totals"].items()):
            handle.write(tsv_line([name, value]))
        for name in classes:
            handle.write(tsv_line([f"only_theirs_class:{name}", result["by_class"].get(name, 0)]))
        for name, value in sorted(result["ours_skipped"].items()):
            handle.write(tsv_line([f"ours_skipped:{name}", value]))
        for name, value in sorted(result["theirs_skipped"].items()):
            handle.write(tsv_line([f"theirs_skipped:{name}", value]))
        handle.write(tsv_line(["theirs_duplicate_rede_ids", result["duplicates"]]))
        handle.write(tsv_line(["ratio_tolerance", RATIO_TOLERANCE]))
        handle.write(tsv_line(["ratio_min_tokens", RATIO_MIN_TOKENS]))
        for name, value in sorted(by_wp_extra.items()):
            handle.write(tsv_line([name, value]))


def by_wahlperiode(rows: list[dict]) -> dict:
    out = Counter()
    for row in rows:
        wp = row["sitting"].split("/")[0]
        out[f"wp{wp}:sittings_ours"] += row["ours"] is not None
        out[f"wp{wp}:sittings_theirs"] += row["theirs"] is not None
        out[f"wp{wp}:sittings_both"] += row["ours"] is not None and row["theirs"] is not None
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--export", required=True, type=Path, help="release SQLite (.sqlite or .sqlite.gz)")
    parser.add_argument("--xml-dir", required=True, type=Path, help="directory of plenarprotokoll-<WP>-<NR>.xml")
    parser.add_argument("--cpp-bt", required=True, type=Path, help="CPP-BT speech metadata zip or CSV")
    parser.add_argument("--out", required=True, type=Path, help="TSV to write")
    parser.add_argument("--known-differences", type=Path,
                        default=Path(__file__).resolve().with_name("cpp_bt_known_differences.tsv"))
    parser.add_argument("--wp-min", type=int, default=18)
    args = parser.parse_args(argv)
    try:
        if not args.xml_dir.is_dir():
            raise InputError(f"--xml-dir {args.xml_dir}: not a directory")
        if not args.out.parent.is_dir():
            raise InputError(f"--out {args.out}: the directory does not exist")
        if args.out.is_dir():
            raise InputError(f"--out {args.out}: is a directory")
        for flag, other in (("--export", args.export), ("--cpp-bt", args.cpp_bt),
                            ("--known-differences", args.known_differences)):
            if other is not None and args.out.resolve() == other.resolve():
                raise InputError(f"--out {args.out}: is the same file as {flag}, which the report would overwrite")
        with tempfile.TemporaryDirectory() as workdir:
            connection = open_export(args.export, Path(workdir))
            try:
                result = compare(connection, read_cpp_bt(args.cpp_bt), args.xml_dir, args.wp_min)
            finally:
                connection.close()
            refuse_empty_comparison(result)
            inputs = [("export", sha256_of(args.export), args.export.name),
                      ("cpp_bt", sha256_of(args.cpp_bt), args.cpp_bt.name),
                      ("xml_files", str(len(list(args.xml_dir.glob("plenarprotokoll-*.xml")))), str(args.xml_dir.name))]
        partial = args.out.with_name(args.out.name + ".part")
        try:
            write_report(result, partial, inputs, known_differences(args.known_differences),
                         by_wahlperiode(result["rows"]))
            os.replace(partial, args.out)  # a stopped run leaves the earlier report whole, never half a new one
        finally:
            partial.unlink(missing_ok=True)
    except InputError as error:
        print(f"compare_cpp_bt: {error}", file=sys.stderr)
        return 2
    except sqlite3.Error as error:
        print(f"compare_cpp_bt: --export {args.export}: unexpected schema ({error})", file=sys.stderr)
        return 2
    print(f"compare_cpp_bt: wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
