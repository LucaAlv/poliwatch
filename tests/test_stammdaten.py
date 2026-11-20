"""C1 step 4: the cached MdB-Stammdaten zip, read into the records
``derive.mdb_zugehoerigkeiten`` takes (docs/plans/c1-seat-counts.md)."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import tempfile
import urllib.error
import urllib.request
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import _support  # noqa: F401
import derive
import person_registry as registry
import stammdaten
from _support import FIXTURES

SPD = "Fraktion der Sozialdemokratischen Partei Deutschlands"
XML = (FIXTURES / "mdb-stammdaten-mini.xml").read_bytes()


def name(nachname: str, vorname: str, von: str, *, ortszusatz=None, adel=None, praefix=None) -> dict:
    return {"NACHNAME": nachname, "VORNAME": vorname, "ORTSZUSATZ": ortszusatz, "ADEL": adel, "PRAEFIX": praefix, "HISTORIE_VON": von}


def fraktion(ins_lang: str, von: str, bis: str | None = None, art: str = "Fraktion/Gruppe") -> dict:
    return {"INSART_LANG": art, "INS_LANG": ins_lang, "MDBINS_VON": von, "MDBINS_BIS": bis}


class ReadZipTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def zip(self, members: dict[str, bytes]) -> Path:
        path = self.tmp / "MdB-Stammdaten.zip"
        with zipfile.ZipFile(path, "w") as archive:
            for member, data in members.items():
                archive.writestr(member, data)
        return path

    # Value: protects=the reader turns the Bundestag's zip into the MDB records the derivation reads,
    #   keeping only ids, names, Mandate and memberships (no biography), skipping the __MACOSX fork,
    #   and stamps the Stand from VERSION and the file's sha256; fails_when=a field derive needs is
    #   dropped or renamed, BIOGRAFISCHE_ANGABEN leaks into the records, the resource fork is read as the
    #   XML, or the Stand is the fetch time; why_new=C1 step 4; seam=stammdaten.read_zip
    def test_the_zip_becomes_records_with_the_stand_and_sha256(self) -> None:
        path = self.zip({"__MACOSX/._MDB_STAMMDATEN.XML": b"\x00\x05\x16\x07 not xml",
                         "MDB_STAMMDATEN.DTD": b"<!ELEMENT DOCUMENT (VERSION, MDB+)>", "MDB_STAMMDATEN.XML": XML})
        result = stammdaten.read_zip(path)
        self.assertEqual(result.stand, "2026-04-29T08:03:03+00:00")
        self.assertEqual(result.sha256, hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(result.records, [
            {"ID": "11009901",
             "NAMEN": [name("Beispiel", "Anna", "22.10.2013"), name("Muster", "Anna", "01.07.2022")],
             "WAHLPERIODEN": [
                 {"WP": "17", "MDBWP_VON": "27.10.2009", "MDBWP_BIS": "22.10.2013", "INSTITUTIONEN": [fraktion(SPD, "27.10.2009")]},
                 {"WP": "20", "MDBWP_VON": "26.10.2021", "MDBWP_BIS": "25.03.2025",
                  "INSTITUTIONEN": [fraktion(SPD, "26.10.2021"), fraktion(SPD, "26.10.2021")]},
             ]},
            {"ID": "11009902",
             "NAMEN": [name("Wechsel", "Bernd", "25.03.2025", ortszusatz="(Musterhausen)", adel="Freiherr", praefix="von")],
             "WAHLPERIODEN": [
                 {"WP": "21", "MDBWP_VON": "25.03.2025", "MDBWP_BIS": None, "INSTITUTIONEN": [
                     fraktion("Fraktion Alternative für Deutschland", "25.03.2025", "10.11.2025"),
                     fraktion("Fraktionslos", "10.11.2025"),
                     fraktion("Ausschuss für Beispiele", "01.06.2025", art="Ausschuss"),
                 ]},
             ]},
            {"ID": "11009903",
             "NAMEN": [name("Ohneamt", "Clara", "25.03.2025")],
             "WAHLPERIODEN": [{"WP": "21", "MDBWP_VON": "25.03.2025", "MDBWP_BIS": None, "INSTITUTIONEN": []}]},
        ])

    # Value: protects=the records go through the derivation as the step-2 rules expect: the function
    #   duplicate counts once, the name in force on the first day, the committee is no Zugehörigkeit, an
    #   empty INSTITUTIONEN is fraktionslos, WP 17 is skipped; fails_when=the reader's shape drifts from
    #   what derive reads (e.g. an empty INSTITUTIONEN read as missing); why_new=C1 step 4; seam=stammdaten.read_zip
    def test_the_records_derive_the_expected_zugehoerigkeiten(self) -> None:
        records = stammdaten.read_zip(self.zip({"MDB_STAMMDATEN.XML": XML})).records
        rows = derive.mdb_zugehoerigkeiten(records, since_wahlperiode=18)
        self.assertEqual([(r["mdb_id"], r["name"], r["wahlperiode"], r["party"], r["valid_from"], r["valid_until"]) for r in rows], [
            ("11009901", "Anna Beispiel", 20, "SPD", "2021-10-26", "2025-03-26"),
            ("11009902", "Bernd Freiherr von Wechsel (Musterhausen)", 21, "AfD", "2025-03-25", "2025-11-10"),
            ("11009902", "Bernd Freiherr von Wechsel (Musterhausen)", 21, "fraktionslos", "2025-11-10", None),
            ("11009903", "Clara Ohneamt", 21, "fraktionslos", "2025-03-25", None),
        ])

    # Value: protects=a damaged or unexpected download ends in StammdatenError naming the cause, never a
    #   traceback or records from the wrong member; fails_when=the reader lets KeyError/ValueError/
    #   BadZipFile/ParseError escape (the rebuild catches StammdatenError only), reads an oversized member
    #   whole, or accepts an MDB without ID or with a non-numeric WP; why_new=step 3 handover; seam=stammdaten.read_zip
    def test_a_bad_file_raises_stammdatenerror_naming_the_cause(self) -> None:
        no_id = XML.replace(b"<ID>11009903</ID>", b"<ID> </ID>", 1)
        bad_wp = XML.replace(b"<WP>20</WP>", b"<WP>XX</WP>", 1)
        no_version = XML.replace(b"<VERSION>1777449783</VERSION>", b"", 1)
        cases = {
            "not a zip": (None, "not a zip"),
            "no xml member": ({"__MACOSX/._MDB_STAMMDATEN.XML": XML, "MDB_STAMMDATEN.DTD": b""}, "no MDB_STAMMDATEN.XML"),
            "broken xml": ({"MDB_STAMMDATEN.XML": XML[:500]}, "does not parse"),
            "wrong root": ({"MDB_STAMMDATEN.XML": b"<DOKUMENT/>"}, "root element"),
            "blank id": ({"MDB_STAMMDATEN.XML": no_id}, "MDB without ID"),
            "bad wp": ({"MDB_STAMMDATEN.XML": bad_wp}, "MdB 11009901: WP 'XX'"),
            "no version": ({"MDB_STAMMDATEN.XML": no_version}, "VERSION"),
            # datetime raises ValueError past year 9999 and OverflowError past time_t.
            "version past year 9999": ({"MDB_STAMMDATEN.XML": XML.replace(b"1777449783", b"99999999999999", 1)}, "VERSION"),
            "version past time_t": ({"MDB_STAMMDATEN.XML": XML.replace(b"1777449783", b"999999999999999999999", 1)}, "VERSION"),
            # str.isdigit accepts superscripts, which int() rejects.
            "non-ascii version digit": ({"MDB_STAMMDATEN.XML": XML.replace(b"1777449783", "177744978²".encode(), 1)}, "VERSION"),
            "non-ascii wp digit": ({"MDB_STAMMDATEN.XML": XML.replace(b"<WP>20</WP>", "<WP>2²</WP>".encode(), 1)}, "WP '2²'"),
            # expat raises LookupError, not ParseError, for an encoding it does not know.
            "unknown encoding": ({"MDB_STAMMDATEN.XML": XML.replace(b'encoding="UTF-8"', b'encoding="foo"', 1)}, "does not parse"),
        }
        for label, (members, message) in cases.items():
            with self.subTest(label):
                if members is None:
                    path = self.tmp / "MdB-Stammdaten.zip"
                    path.write_bytes(b"<html>Wartungsarbeiten</html>")
                else:
                    path = self.zip(members)
                with self.assertRaisesRegex(derive.StammdatenError, message):
                    stammdaten.read_zip(path)
        # The LZMA stream starts after zipfile's 4-byte header and 5 property bytes.
        for label, method, skip in (("corrupt deflate stream", zipfile.ZIP_DEFLATED, 0),
                                    ("corrupt lzma stream", zipfile.ZIP_LZMA, 9),
                                    ("corrupt bzip2 stream", zipfile.ZIP_BZIP2, 0)):
            with self.subTest(label):
                path = self.tmp / "MdB-Stammdaten.zip"
                with zipfile.ZipFile(path, "w", method) as archive:
                    archive.writestr("MDB_STAMMDATEN.XML", XML)
                data = bytearray(path.read_bytes())
                # Overwrite the start of the compressed stream, after the 30-byte local header and the name.
                start = 30 + len("MDB_STAMMDATEN.XML") + skip
                data[start:start + 16] = b"\xff" * 16
                path.write_bytes(bytes(data))
                with self.assertRaisesRegex(derive.StammdatenError, "not a zip file"):
                    stammdaten.read_zip(path)

    def test_an_oversized_xml_member_is_refused_before_it_is_read(self) -> None:
        path = self.zip({"MDB_STAMMDATEN.XML": XML})
        with mock.patch.object(stammdaten, "MAX_XML_BYTES", 100):
            with self.assertRaisesRegex(derive.StammdatenError, "larger than"):
                stammdaten.read_zip(path)

    # Value: protects=the sha256 read_zip returns names the bytes its records and Stand came from, even when
    #   a concurrent refresh replaces the file between two reads; fails_when=read_zip parses one read of the
    #   file and hashes another (path.read_bytes() after the zip was parsed), so the store's
    #   mdb_stammdaten_stand names a file the seat rows did not come from; why_new=TODOS C1 deferred item 11;
    #   seam=io.open, which swaps the file on the second open; no_claim=a real concurrent build
    def test_the_sha256_names_the_bytes_the_records_came_from(self) -> None:
        path = self.zip({"MDB_STAMMDATEN.XML": XML})
        first = path.read_bytes()
        other = self.tmp / "other.zip"
        with zipfile.ZipFile(other, "w") as archive:
            archive.writestr("MDB_STAMMDATEN.XML", XML.replace(b"1777449783", b"1780000000", 1))
        real_open = io.open
        opened: list[str] = []

        def swapping_open(file, *args, **kwargs):
            if isinstance(file, (str, os.PathLike)) and os.fspath(file) == os.fspath(path):
                opened.append("open")
                if len(opened) == 2:  # a concurrent refresh lands between the reads
                    os.replace(other, path)
            return real_open(file, *args, **kwargs)

        with mock.patch("io.open", swapping_open):
            result = stammdaten.read_zip(path)
        self.assertEqual(result.stand, "2026-04-29T08:03:03+00:00")
        self.assertEqual(result.sha256, hashlib.sha256(first).hexdigest())
        self.assertEqual(opened, ["open"])

    # Value: protects=an XML member whose prolog declares entities (a DOCTYPE with an internal subset, a bare
    #   ENTITY) is refused before expat parses it, as is a prolog that reaches no root element in its first
    #   bytes (a UTF-16 file hides a DOCTYPE from a byte scan); the Bundestag's own external-only DOCTYPE and
    #   the comment after it still read; fails_when=read_zip hands any prolog to ET.fromstring, so entity
    #   expansion rests on the linked expat alone; why_new=TODOS C1 deferred item 17, whose premise that the
    #   real file has no DOCTYPE is wrong: it has <!DOCTYPE DOCUMENT SYSTEM "MDB_STAMMDATEN.DTD">;
    #   seam=stammdaten.read_zip
    def test_a_prolog_that_declares_entities_is_refused_before_it_is_parsed(self) -> None:
        body = b"<DOCUMENT>" + XML.split(b"<DOCUMENT>", 1)[1]
        declaration = b'<?xml version="1.0" encoding="UTF-8"?>\n'
        refused = {
            "internal subset": declaration + b'<!DOCTYPE DOCUMENT [<!ENTITY a "Muster">]>\n' + body,
            "external id and internal subset": declaration + b'<!DOCTYPE DOCUMENT SYSTEM "x.dtd" [<!ENTITY a "b">]>' + body,
            "subset after a comment": declaration + b'<!-- c --><!DOCTYPE DOCUMENT[<!ENTITY a "b">]>' + body,
            "bare entity": b'<!ENTITY a "b">' + body,
            "two doctypes": b'<!DOCTYPE DOCUMENT SYSTEM "x.dtd"><!DOCTYPE DOCUMENT [<!ENTITY a "b">]>' + body,
            "utf-16": XML.decode("utf-8").replace('encoding="UTF-8"', 'encoding="UTF-16"').encode("utf-16"),
            "root past the first bytes": b"<!--" + b"x" * stammdaten.PROLOG_BYTES + b"-->" + body,
        }
        for label, xml in refused.items():
            with self.subTest(label), self.assertRaisesRegex(derive.StammdatenError, "DOCTYPE|root element"):
                stammdaten.read_zip(self.zip({"MDB_STAMMDATEN.XML": xml}))
        accepted = {
            "the Bundestag's prolog": XML,
            "public id": b'<!DOCTYPE DOCUMENT PUBLIC "-//X//DTD//DE" \'x.dtd\'>' + body,
            "utf-8 byte order mark": b"\xef\xbb\xbf" + XML,
            "no prolog": body,
        }
        for label, xml in accepted.items():
            with self.subTest(label):
                self.assertEqual(stammdaten.read_zip(self.zip({"MDB_STAMMDATEN.XML": xml})).stand, "2026-04-29T08:03:03+00:00")

    # Value: protects=a VERSION stamp before 2017 or later than a day from now is refused, so it never becomes
    #   the Stand that drives after_stand, the manifest, the Daten page and r2's caveat date; the bounds
    #   themselves read; fails_when=read_zip accepts any VERSION that fits a datetime (0 is 1970, 99999999999
    #   is the year 5138, which silences the drift warning); why_new=TODOS C1 deferred item 37; seam=stammdaten._now
    def test_a_stand_before_2017_or_after_tomorrow_is_refused(self) -> None:
        now = datetime(2026, 11, 17, 12, tzinfo=timezone.utc)
        tomorrow = int((now + timedelta(days=1)).timestamp())
        cases = {0: False, 1483228799: False, 1483228800: True, tomorrow: True, tomorrow + 1: False, 99999999999: False}
        for version, ok in cases.items():
            with self.subTest(version=version), mock.patch.object(stammdaten, "_now", return_value=now):
                path = self.zip({"MDB_STAMMDATEN.XML": XML.replace(b"1777449783", str(version).encode(), 1)})
                if ok:
                    self.assertEqual(stammdaten.read_zip(path).stand,
                                     datetime.fromtimestamp(version, timezone.utc).isoformat())
                else:
                    with self.assertRaisesRegex(derive.StammdatenError, "VERSION .* is a Stand before 2017 or after"):
                        stammdaten.read_zip(path)

    # Value: protects=a cached file over MAX_ZIP_BYTES or missing is a StammdatenError before any byte is read,
    #   not a MemoryError or a bare OSError; fails_when=read_zip reads the file whole first;
    #   why_new=TODOS C1 deferred items 38, 42, 44; seam=stammdaten.read_zip
    def test_an_oversized_or_missing_cached_file_is_a_stammdaten_error(self) -> None:
        path = self.zip({"MDB_STAMMDATEN.XML": XML})
        with mock.patch.object(stammdaten, "MAX_ZIP_BYTES", 100), \
                mock.patch.object(Path, "read_bytes", side_effect=AssertionError("read before the size check")):
            with self.assertRaisesRegex(stammdaten.StammdatenError, "larger than 100 bytes"):
                stammdaten.read_zip(path)
        with self.assertRaisesRegex(stammdaten.StammdatenError, "not a zip file"):
            stammdaten.read_zip(self.tmp / "absent.zip")


CDU_CSU = "Fraktion der Christlich Demokratischen Union/Christlich - Sozialen Union"


def whole_bundestag_zip(path: Path, version: int = 1777449783, art: str = "Fraktion/Gruppe", prolog: str = "") -> bytes:
    """A zip the size check accepts: a WP 21 Bundestag of 630 CDU/CSU MdBs
    from the constituent day, in the file's element names. ``art`` is the
    ``INSART_LANG`` label of their membership, ``prolog`` what precedes the
    root element."""
    mdbs = "".join(
        f"<MDB><ID>110{index:05d}</ID><NAMEN><NAME><NACHNAME>Muster{index}</NACHNAME><VORNAME>Max</VORNAME>"
        f"<HISTORIE_VON>25.03.2025</HISTORIE_VON></NAME></NAMEN><WAHLPERIODEN><WAHLPERIODE><WP>21</WP>"
        f"<MDBWP_VON>25.03.2025</MDBWP_VON><MDBWP_BIS/><INSTITUTIONEN><INSTITUTION><INSART_LANG>{art}</INSART_LANG>"
        f"<INS_LANG>{CDU_CSU}</INS_LANG><MDBINS_VON>25.03.2025</MDBINS_VON><MDBINS_BIS/></INSTITUTION></INSTITUTIONEN>"
        f"</WAHLPERIODE></WAHLPERIODEN></MDB>"
        for index in range(630)
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("MDB_STAMMDATEN.XML", f"{prolog}<DOCUMENT><VERSION>{version}</VERSION>{mdbs}</DOCUMENT>")
    return path.read_bytes()


class FakeResponse(io.BytesIO):
    def __init__(self, body: bytes, etag: str | None) -> None:
        super().__init__(body)
        self.headers = {"ETag": etag} if etag else {}
        self.status = 200


class RefreshTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.database = self.tmp / "site" / "data" / "bundestag-pulse.sqlite"
        self.database.parent.mkdir(parents=True)
        self.cache = stammdaten.cache_path(self.database)
        self.good = whole_bundestag_zip(self.tmp / "good.zip")
        self.newer = whole_bundestag_zip(self.tmp / "newer.zip", version=1780000000)
        self.requests: list = []

    def refresh(self, answer) -> str:
        def urlopen(request, timeout=None):
            self.requests.append(request)
            if isinstance(answer, BaseException):
                raise answer
            return FakeResponse(*answer)

        err = io.StringIO()
        with mock.patch("urllib.request.OpenerDirector.open", side_effect=urlopen), contextlib.redirect_stderr(err):
            stammdaten.refresh(self.database, since_wahlperiode=18)
        return err.getvalue()

    def seed(self, body: bytes, etag: str = '"old"') -> None:
        self.cache.parent.mkdir(parents=True, exist_ok=True)
        self.cache.write_bytes(body)
        stammdaten.etag_path(self.database).write_text(json.dumps({"etag": etag, "fetched_at": "2026-05-01T00:00:00+00:00"}))

    def leftovers(self) -> list[str]:
        return sorted(path.name for path in self.cache.parent.iterdir() if path.name.startswith(".mdb-stammdaten"))

    # Value: protects=a fetched file that passes the rebuild's own checks replaces the cache and its ETag
    #   is kept for the next conditional GET; fails_when=the file is written in place (a crash leaves half a
    #   zip), the ETag is lost, or the URL is not the Bundestag's; why_new=C1 step 4; seam=stammdaten.refresh
    def test_a_valid_download_replaces_the_cache_and_keeps_its_etag(self) -> None:
        self.cache.parent.mkdir(parents=True, exist_ok=True)
        (self.cache.parent / ".mdb-stammdaten.crashed.tmp").write_bytes(b"half a zip")  # a killed earlier refresh
        err = self.refresh((self.good, '"new"'))
        self.assertEqual(self.cache.read_bytes(), self.good)
        self.assertEqual(json.loads(stammdaten.etag_path(self.database).read_text())["etag"], '"new"')
        self.assertEqual(self.requests[0].full_url, "https://www.bundestag.de/resource/blob/472878/MdB-Stammdaten.zip")
        self.assertIsNone(self.requests[0].get_header("If-none-match"))
        self.assertIn("stammdaten: fetched, Stand 29.04.2026", err)
        self.assertEqual(self.leftovers(), [])

    # Value: protects=an unchanged file costs one 304 and touches nothing; fails_when=no If-None-Match is
    #   sent, or urllib's HTTPError(304) is treated as a failure; why_new=C1 step 4; seam=stammdaten.refresh
    def test_a_304_keeps_the_cache_and_says_unchanged(self) -> None:
        self.seed(self.good)
        err = self.refresh(urllib.error.HTTPError(stammdaten.URL, 304, "Not Modified", {}, None))
        self.assertEqual(self.requests[0].get_header("If-none-match"), '"old"')
        self.assertEqual(self.cache.read_bytes(), self.good)
        self.assertIn("stammdaten: unchanged", err)

    def test_a_304_without_a_cached_file_is_a_failure_not_a_crash(self) -> None:
        err = self.refresh(urllib.error.HTTPError(stammdaten.URL, 304, "Not Modified", {}, None))
        self.assertIn("warning: [stammdaten]", err)
        self.assertIn("no cached file: keine Sitzzahlen", err)
        self.assertFalse(self.cache.exists())

    # Value: protects=a failed fetch or a download that fails validation never replaces a good cache and
    #   says so, and with no cache says the seat tables stay empty; fails_when=a maintenance page, a truncated
    #   zip or a file breaking a seat rule overwrites the cache, or the failure is silent or a traceback;
    #   why_new=C1 step 4 keep-previous rule; seam=stammdaten.refresh
    def test_a_failed_or_invalid_download_keeps_the_previous_file_and_warns(self) -> None:
        mini = io.BytesIO()
        with zipfile.ZipFile(mini, "w") as archive:
            archive.writestr("MDB_STAMMDATEN.XML", XML)
        cases = {
            "network": (urllib.error.URLError("timed out"), "timed out"),
            "server": (urllib.error.HTTPError(stammdaten.URL, 503, "Service Unavailable", {}, None), "503"),
            "not a zip": ((b"<html>Wartungsarbeiten</html>", '"x"'), "not a zip"),
            "seat rule": ((mini.getvalue(), '"y"'), "WP 20: at most 1 seats on any day, never the legal 736"),
        }
        for label, (answer, cause) in cases.items():
            for seeded in (True, False):
                with self.subTest(label, seeded=seeded):
                    if seeded:
                        self.seed(self.good)
                    else:
                        self.cache.unlink(missing_ok=True)
                        stammdaten.etag_path(self.database).unlink(missing_ok=True)
                    err = self.refresh(answer)
                    self.assertIn("warning: [stammdaten]", err)
                    self.assertIn(cause, err)
                    if seeded:
                        self.assertEqual(self.cache.read_bytes(), self.good)
                        self.assertEqual(json.loads(stammdaten.etag_path(self.database).read_text())["etag"], '"old"')
                        self.assertIn("keeping the cached file (Stand 29.04.2026)", err)
                    else:
                        self.assertFalse(self.cache.exists())
                        self.assertIn("no cached file: keine Sitzzahlen", err)
                    self.assertEqual(self.leftovers(), [])

    # Value: protects=a download whose Fraktion/Gruppe label was renamed (every MdB then reads fraktionslos,
    #   630 seats, the legal size) is refused and the cached file kept, with a warning naming the cause;
    #   fails_when=refresh caches a file that publishes fraktionslos at 100 %; why_new=TODOS C1 deferred
    #   item 30; seam=stammdaten.refresh
    def test_a_download_with_a_renamed_fraktion_label_keeps_the_previous_file_and_warns(self) -> None:
        self.seed(self.good)
        renamed = whole_bundestag_zip(self.tmp / "renamed.zip", version=1780000000, art="Fraktion")
        err = self.refresh((renamed, '"r"'))
        self.assertIn("warning: [stammdaten] the downloaded file fails the seat checks", err)
        self.assertIn("WP 21: every Mandat is fraktionslos", err)
        self.assertIn("keeping the cached file (Stand 29.04.2026)", err)
        self.assertEqual(self.cache.read_bytes(), self.good)
        self.assertEqual(json.loads(stammdaten.etag_path(self.database).read_text())["etag"], '"old"')
        self.assertEqual(self.leftovers(), [])

    # Value: protects=with a cached zip that read_zip rejects, a failed fetch, an invalid download or a failed
    #   cache write says that the cached file is unreadable, names it with the cause, and says the next rebuild
    #   stops until a fetch succeeds or the file is removed, where it used to say "no cached file" and promise
    #   a build without seat counts; with no cached file at all the old wording stays and a failed cache write
    #   leaves no cache; fails_when=kept words a corrupt cache like an absent one; why_new=TODOS C1 deferred
    #   items 22 and 24 (the corrupt-cache and no-cache rows of the matrix); seam=stammdaten.refresh
    def test_a_lost_etag_write_says_the_file_is_cached(self) -> None:
        # Value: protects=once the good file is in place, a failed ETag write is reported as that, not as the
        #   state before the download; fails_when=the sidecar shares the except of the file swap again;
        #   why_new=every cache-write row above fails the swap itself; seam=none;
        #   no_claim=a real full disk (the write is mocked)
        real_write_text = Path.write_text

        def failing(path, *args, **kwargs):
            if path.name == stammdaten.ETAG_NAME:
                raise OSError(28, "No space left on device")
            return real_write_text(path, *args, **kwargs)

        for label, before, gone in (
            ("corrupt cache", b"<html>half a zip</html>", "unreadable"),
            ("no cache", None, "no cached file"),
            ("good cache", self.good, "keeping the cached file"),
        ):
            with self.subTest(label):
                self.cache.unlink(missing_ok=True)
                if before:
                    self.seed(before)
                with mock.patch.object(Path, "write_text", failing):
                    err = self.refresh((self.newer, '"n"'))
                self.assertEqual(self.cache.read_bytes(), self.newer)
                self.assertNotIn(gone, err)
                self.assertNotIn("could not be cached", err)
                self.assertIn("No space left on device", err)
                self.assertIn("the next run downloads it in full", err)
                self.assertIn("stammdaten: fetched", err)

    def test_a_corrupt_cache_is_named_unreadable_when_the_fetch_or_the_cache_write_fails(self) -> None:
        mini = io.BytesIO()
        with zipfile.ZipFile(mini, "w") as archive:
            archive.writestr("MDB_STAMMDATEN.XML", XML)
        corrupt = b"<html>half a zip</html>"
        cases = {
            "network": ((urllib.error.URLError("timed out"), None), "timed out"),
            "server": ((urllib.error.HTTPError(stammdaten.URL, 503, "Service Unavailable", {}, None), None), "503"),
            "not a zip": (((b"<html>Wartungsarbeiten</html>", '"x"'), None), "not a zip"),
            "seat rule": (((mini.getvalue(), '"y"'), None), "WP 20: at most 1 seats on any day"),
            "cache write": (((self.newer, '"n"'), OSError(28, "No space left on device")), "No space left on device"),
        }
        for label, (answer_and_failure, cause) in cases.items():
            answer, failure = answer_and_failure
            for cached in (corrupt, None):
                with self.subTest(label, cached=bool(cached)):
                    self.cache.unlink(missing_ok=True)
                    if cached:
                        self.seed(cached)
                    with mock.patch.object(stammdaten.os, "replace", side_effect=failure) if failure else contextlib.nullcontext():
                        err = self.refresh(answer)
                    self.assertIn("warning: [stammdaten]", err)
                    self.assertIn(cause, err)
                    if cached:
                        self.assertIn(f"the cached file {self.cache.name} is unreadable (", err)
                        self.assertIn("not a zip file the Stammdaten can be read from", err)
                        self.assertIn("the next rebuild stops until a fetch succeeds or the file is removed", err)
                        self.assertNotIn("no cached file", err)
                        self.assertEqual(self.cache.read_bytes(), cached)
                    else:
                        self.assertIn("no cached file: keine Sitzzahlen", err)
                        self.assertNotIn("unreadable", err)
                        self.assertFalse(self.cache.exists())
                    self.assertEqual(self.leftovers(), [])

    # Value: protects=refresh checks the private directory before it reads the cache, sweeps, fetches or
    #   writes: a symlink planted at its place (here with the ETag sidecar pointing at a file elsewhere,
    #   and a stale temp file inside) is refused with a warning, so no file behind it is truncated or
    #   swept; fails_when=refresh reads, sweeps or writes before registry.ensure_private_dir, or lets its
    #   PermissionError out; why_new=TODOS C1 deferred item 33 (Codex's reproduction) and 8; seam=stammdaten.refresh
    def test_a_symlinked_private_directory_is_refused_before_anything_is_fetched_or_written(self) -> None:
        elsewhere = self.tmp / "elsewhere"
        elsewhere.mkdir()
        victim = self.tmp / "victim.json"
        victim.write_text("keep", encoding="utf-8")
        (elsewhere / stammdaten.ETAG_NAME).symlink_to(victim)
        (elsewhere / ".mdb-stammdaten.old.tmp").write_bytes(b"not swept")
        self.cache.parent.symlink_to(elsewhere)
        err = self.refresh((self.good, '"n"'))
        self.assertIn("warning: [stammdaten] not fetching, the private directory cannot be used", err)
        self.assertIn("symbolic link", err)
        self.assertEqual(self.requests, [])
        self.assertEqual(victim.read_text(encoding="utf-8"), "keep")
        self.assertEqual(sorted(path.name for path in elsewhere.iterdir()), [".mdb-stammdaten.old.tmp", stammdaten.ETAG_NAME])

    def test_a_private_directory_that_cannot_be_created_is_a_warning_not_a_crash(self) -> None:
        with mock.patch.object(stammdaten.registry, "ensure_private_dir", side_effect=OSError(13, "Permission denied")):
            err = self.refresh((self.good, '"n"'))
        self.assertIn("warning: [stammdaten] not fetching, the private directory cannot be used (", err)
        self.assertIn("Permission denied", err)
        self.assertEqual(self.requests, [])

    # Value: protects=a cache write that fails (disk full, a concurrent refresh) keeps the previous file
    #   and warns instead of ending the build in a traceback; fails_when=the OSError from writing or
    #   os.replace escapes refresh; why_new=checklist class 10 on step 4; seam=stammdaten.refresh with os.replace failing
    def test_a_failed_cache_write_keeps_the_previous_file_and_warns(self) -> None:
        self.seed(self.good)
        with mock.patch.object(stammdaten.os, "replace", side_effect=OSError(28, "No space left on device")):
            err = self.refresh((self.newer, '"n"'))
        self.assertIn("warning: [stammdaten]", err)
        self.assertIn("No space left on device", err)
        self.assertEqual(self.cache.read_bytes(), self.good)
        self.assertEqual(json.loads(stammdaten.etag_path(self.database).read_text())["etag"], '"old"')
        self.assertEqual(self.leftovers(), [])

    # Value: protects=a conditional GET is sent only for a cached file that reads and an ETag sidecar that
    #   parses to a string; an unreadable cache or a damaged sidecar sends none, so the server's full body
    #   replaces the file instead of a 304 keeping it; fails_when=refresh sends the stale ETag for a corrupt
    #   cache (a 304 would pin the bad file forever) or a damaged sidecar raises out of refresh;
    #   why_new=TODOS C1 deferred item 18 names the corrupt-cache half, the sidecar variants are new;
    #   seam=none; no_claim=the real server's ETag handling (urlopen is faked)
    def test_a_conditional_get_needs_a_readable_cache_and_a_well_formed_sidecar(self) -> None:
        sidecars = {
            "not json": "{{",
            "not an object": json.dumps(["etag"]),
            "etag not a string": json.dumps({"etag": 7}),
            "no etag": json.dumps({"fetched_at": "2026-05-01T00:00:00+00:00"}),
        }
        with self.subTest("corrupt cache, stale sidecar"):
            self.seed(b"<html>half a zip</html>")
            err = self.refresh((self.newer, '"new"'))
            self.assertIsNone(self.requests[-1].get_header("If-none-match"))
            self.assertEqual(self.cache.read_bytes(), self.newer)
            self.assertIn("stammdaten: fetched, Stand", err)
            self.assertEqual(self.leftovers(), [])
        for label, sidecar in sidecars.items():
            with self.subTest(label):
                self.seed(self.good)
                stammdaten.etag_path(self.database).write_text(sidecar, encoding="utf-8")
                err = self.refresh((self.newer, '"new"'))
                self.assertIsNone(self.requests[-1].get_header("If-none-match"))
                self.assertEqual(self.cache.read_bytes(), self.newer)
                self.assertIn("stammdaten: fetched, Stand", err)
                self.assertNotIn("warning:", err)

    def test_a_download_over_the_size_cap_is_refused(self) -> None:
        self.seed(self.good)
        with mock.patch.object(stammdaten, "MAX_ZIP_BYTES", 100):
            err = self.refresh((self.newer, '"z"'))
        self.assertIn("larger than 100 bytes", err)
        self.assertEqual(self.cache.read_bytes(), self.good)

    # Value: protects=a redirect off https://www.bundestag.de (another host, plain http) is refused and the
    #   cache is kept; fails_when=urllib's default handler follows it; why_new=TODOS C1 deferred item 28;
    #   seam=stammdaten._download with the real opener, no network
    def test_a_redirect_off_the_bundestag_host_is_refused(self) -> None:
        handler = stammdaten._SameHostRedirects()
        request = urllib.request.Request(stammdaten.URL)
        for target in ("http://www.bundestag.de/x.zip", "https://evil.example/x.zip", "https://www.bundestag.de.evil.example/x"):
            with self.subTest(target), self.assertRaisesRegex(stammdaten.StammdatenError, "redirect"):
                handler.redirect_request(request, None, 302, "Found", {}, target)
        followed = handler.redirect_request(request, io.BytesIO(), 302, "Found", {}, "https://www.bundestag.de/other.zip")
        self.assertEqual(followed.full_url, "https://www.bundestag.de/other.zip")

    # Value: protects=a server that drips bytes cannot stall a build past the total deadline; fails_when=the body
    #   is read in one call under a per-socket timeout only; why_new=TODOS C1 deferred item 32;
    #   seam=stammdaten._download with a slow fake response
    def test_a_slow_drip_download_stops_at_the_total_deadline(self) -> None:
        self.seed(self.good)
        ticks = iter(range(0, 100000, 400))
        with mock.patch.object(stammdaten.time, "monotonic", side_effect=lambda: next(ticks)):
            err = self.refresh((self.newer, '"z"'))
        self.assertIn("deadline", err)
        self.assertEqual(self.cache.read_bytes(), self.good)

    # Value: protects=the deadline holds against a real http.client.HTTPResponse whose server sends one byte
    #   per socket read, each just inside the socket timeout; fails_when=a body read waits for a whole chunk
    #   (HTTPResponse.read(n) blocks until n bytes), so the deadline is checked only after 64 KiB of drip;
    #   why_new=the fake response above returns at once and cannot show a blocking read; seam=none
    def test_a_one_byte_drip_through_a_real_http_response_stops_near_the_deadline(self) -> None:
        import http.client

        clock = {"now": 0.0}
        head = b'HTTP/1.1 200 OK\r\nContent-Length: 200000\r\nETag: "z"\r\n\r\n'
        wire = head + b"x" * 200000

        class Drip(io.RawIOBase):
            def __init__(self) -> None:
                self.position = 0

            def readable(self) -> bool:
                return True

            def readinto(self, buffer) -> int:
                if self.position >= len(wire):
                    return 0
                buffer[0] = wire[self.position]
                self.position += 1
                if self.position > len(head):
                    clock["now"] += 59  # one body byte per socket read, just inside the 60 s timeout
                return 1

        class Sock:
            def makefile(self, mode):
                return io.BufferedReader(Drip())

        def opener_open(request, timeout=None):
            response = http.client.HTTPResponse(Sock(), method="GET")
            response.begin()
            return response

        self.seed(self.good)
        err = io.StringIO()
        with mock.patch.object(stammdaten.time, "monotonic", side_effect=lambda: clock["now"]), \
                mock.patch("urllib.request.OpenerDirector.open", side_effect=opener_open), contextlib.redirect_stderr(err):
            stammdaten.refresh(self.database, since_wahlperiode=18)
        self.assertIn("deadline", err.getvalue())
        self.assertEqual(self.cache.read_bytes(), self.good)
        # The body may overshoot the deadline by one socket read, never by a whole chunk of drip.
        self.assertLessEqual(clock["now"], stammdaten.FETCH_DEADLINE_SECONDS + 59)

    def refresh_download(self, body: bytes) -> str:
        """``refresh`` with ``_download`` answering ``body`` under the ETag "n"."""
        err = io.StringIO()
        with mock.patch.object(stammdaten, "_download", return_value=(body, '"n"')), contextlib.redirect_stderr(err):
            stammdaten.refresh(self.database, since_wahlperiode=18)
        return err.getvalue()

    # Value: protects=a download whose Stand is older than the cached file's (a CDN serving an old zip under
    #   another ETag) keeps the cached file and its ETag and warns with both Stands, so the seat tables, r2
    #   and the manifest Stand never move backwards; a newer or equal Stand still replaces it; fails_when=
    #   refresh never compares the Stand and replaces a newer cache with only a "fetched" line;
    #   why_new=TODOS C1 deferred item 15; seam=stammdaten._download stubbed
    def test_an_older_download_keeps_the_newer_cached_file_and_warns(self) -> None:
        self.seed(self.newer)
        err = self.refresh_download(self.good)
        self.assertEqual(self.cache.read_bytes(), self.newer)
        self.assertEqual(json.loads(stammdaten.etag_path(self.database).read_text())["etag"], '"old"')
        self.assertIn("warning: [stammdaten] the downloaded file has Stand 29.04.2026, older than the cached file's", err)
        self.assertIn("keeping the cached file (Stand 28.05.2026)", err)
        self.assertNotIn("stammdaten: fetched", err)
        self.assertEqual(self.leftovers(), [])
        same_stand = whole_bundestag_zip(self.tmp / "same-stand.zip", prolog="<!-- republished -->")
        for label, cached, fetched in (("newer", self.good, self.newer), ("same Stand", self.good, same_stand)):
            with self.subTest(label):
                self.seed(cached)
                err = self.refresh_download(fetched)
                self.assertEqual(self.cache.read_bytes(), fetched)
                self.assertEqual(json.loads(stammdaten.etag_path(self.database).read_text())["etag"], '"n"')
                self.assertIn("stammdaten: fetched", err)
                self.assertNotIn("warning:", err)

    # Value: protects=a download that declares entities in its prolog, or stamps a Stand before 2017 or after
    #   tomorrow, is refused and the cached file kept, with the cause named; fails_when=refresh caches a file
    #   read_zip would accept only before these checks; why_new=TODOS C1 deferred items 17 and 37;
    #   seam=stammdaten._download stubbed
    def test_a_download_with_entities_or_an_implausible_stand_keeps_the_cached_file(self) -> None:
        bad = {
            "entity": (whole_bundestag_zip(self.tmp / "entity.zip", version=1780000000,
                                           prolog='<!DOCTYPE DOCUMENT [<!ENTITY a "b">]>'), "DOCTYPE"),
            "far future": (whole_bundestag_zip(self.tmp / "future.zip", version=99999999999), "after"),
            "before 2017": (whole_bundestag_zip(self.tmp / "old.zip", version=1400000000), "before 2017"),
        }
        for label, (body, cause) in bad.items():
            with self.subTest(label):
                self.seed(self.good)
                err = self.refresh_download(body)
                self.assertIn("warning: [stammdaten]", err)
                self.assertIn(cause, err)
                self.assertIn("keeping the cached file (Stand 29.04.2026)", err)
                self.assertEqual(self.cache.read_bytes(), self.good)
                self.assertEqual(json.loads(stammdaten.etag_path(self.database).read_text())["etag"], '"old"')
                self.assertEqual(self.leftovers(), [])


class CachePathTests(unittest.TestCase):
    # Value: protects=the cached zip lives in the store's private directory, never in the published
    #   OUTPUT tree (its redistribution terms are open, plan D7); fails_when=cache_path points into
    #   OUTPUT/data; why_new=C1 step 4 owner decision; seam=stammdaten.cache_path
    def test_the_cache_lives_in_the_stores_private_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / "site" / "data" / "bundestag-pulse.sqlite"
            database.parent.mkdir(parents=True)
            path = stammdaten.cache_path(database)
            self.assertEqual(path.parent, registry.private_dir(database))
            self.assertNotIn(Path(tmp) / "site", path.parents)


if __name__ == "__main__":
    unittest.main()
