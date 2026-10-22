"""Backfill pacing for dserver XML (decision 9, docs/plans/a3-rule5-wp18-19-round2.md):
2 s spacing, about 50 XML per window, a 60-minute pause, a stop on the first answer over 10 s."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _support  # noqa: F401
import build_dip_pulse_site as build
import validate_dip_protocol as dip


class FakeClock:
    def __init__(self):
        self.now = 100.0
        self.sleeps = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def pacer(clock, **kwargs):
    return dip.XmlPacer(clock=clock.clock, sleep=clock.sleep, **kwargs)


class XmlPacerTests(unittest.TestCase):
    def fetch(self, p, clock, took=0.5, url='https://dserver.bundestag.de/btp/18/18001.xml'):
        def fake(_url):
            clock.now += took
            return '<xml/>'
        with mock.patch.object(dip, 'fetch_text', side_effect=fake):
            return p.fetch(url)

    def test_defaults_are_the_decided_pacing(self):
        p = dip.XmlPacer()
        self.assertEqual((p.spacing, p.window_size, p.window_pause, p.slow_stop), (2.0, 50, 3600.0, 10.0))

    def test_requests_are_spaced_two_seconds_apart(self):
        clock = FakeClock()
        p = pacer(clock)
        self.assertEqual(self.fetch(p, clock), '<xml/>')
        self.assertEqual(clock.sleeps, [])
        clock.now += 0.5
        self.fetch(p, clock)
        self.assertEqual(clock.sleeps, [1.5])
        clock.now += 5
        self.fetch(p, clock)
        self.assertEqual(clock.sleeps, [1.5])

    def test_a_full_window_pauses_an_hour_before_the_next_request(self):
        clock = FakeClock()
        p = pacer(clock, window_size=3)
        for _ in range(3):
            self.fetch(p, clock)
        self.assertNotIn(3600.0, clock.sleeps)
        with mock.patch('sys.stderr'):
            self.fetch(p, clock)
        self.assertEqual(clock.sleeps[-1], 3600.0)
        self.assertEqual(p.in_window, 1)

    def test_the_first_slow_answer_stops_the_run(self):
        clock = FakeClock()
        p = pacer(clock)
        self.fetch(p, clock, took=9.9)
        with self.assertRaisesRegex(dip.SourceSlowError, '10.5 s'):
            self.fetch(p, clock, took=10.5)
        # Not a DipError: a build skips a DipError sitting as unavailable and goes on.
        self.assertFalse(issubclass(dip.SourceSlowError, dip.DipError))

    def test_a_slow_failure_stops_too(self):
        clock = FakeClock()
        p = pacer(clock)

        def timeout(_url):
            clock.now += 60
            raise dip.DipError('timed out')
        with mock.patch.object(dip, 'fetch_text', side_effect=timeout):
            with self.assertRaises(dip.SourceSlowError):
                p.fetch('https://dserver.bundestag.de/btp/18/18001.xml')

    def test_build_report_fetches_through_the_runs_pacer(self):
        args = mock.Mock(api_key='k', sleep=0, xml_pacer=dip.XmlPacer())
        with mock.patch.object(dip.XmlPacer, 'fetch', side_effect=RuntimeError('paced')) as fetch, \
                mock.patch.object(dip, 'fetch_text', side_effect=AssertionError('unpaced fetch')):
            with self.assertRaisesRegex(RuntimeError, 'paced'):
                dip.build_report(args, protocol={'id': 1, 'dokumentnummer': '18/1',
                                                 'fundstelle': {'xml_url': 'https://dserver.bundestag.de/btp/18/18001.xml'}})
        fetch.assert_called_once_with('https://dserver.bundestag.de/btp/18/18001.xml')

    def test_fetch_missing_xml_uses_the_pacer(self):
        p = mock.Mock()
        p.fetch.side_effect = dip.SourceSlowError('slow')
        entries = [{'report': {'protocol': {'dokumentnummer': '18/1',
                                            'xml_url': 'https://dserver.bundestag.de/btp/18/18001.xml'}}}]
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(dip.SourceSlowError):
            build.fetch_missing_xml(Path(tmp), entries, pacer=p)

    def test_backfill_dip_api_spacing_is_two_seconds(self):
        self.assertEqual(build.BACKFILL_SLEEP_SECONDS, 2.0)


if __name__ == '__main__':
    unittest.main()
