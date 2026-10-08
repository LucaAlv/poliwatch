"""Capture source labels/text lengths for a bounded A1 parser comparison.

Run from the checkout with Python >=3.11. Inputs are read-only XML directories;
output is a gzip JSON snapshot. Baselines must be captured with the base parser.
"""
import argparse
import gzip
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import validate_dip_protocol as dip


def capture(directories):
    protocols = {}
    started = time.monotonic()
    for path in sorted(p for directory in directories for p in directory.glob('*.xml')):
        raw = path.read_text(encoding='utf-8')
        parsed = dip.parse_protocol_xml(raw)
        units = []
        items = [*parsed['agenda_items'], {'index': 0, 'speeches': [], 'contributions': parsed.get('sitting_contributions', [])}]
        for top in items:
            for field in ('speeches', 'contributions'):
                for i, unit in enumerate(top[field]):
                    units.append({'top': top['index'], 'id': unit.get('rede_id') or f"flat:{unit.get('sequence', i)}",
                                  'kind': unit.get('kind', 'rede'), 'chars': unit['char_count']})
        if path.name in protocols:
            raise ValueError(f'duplicate source filename: {path.name}')
        protocols[path.name] = {'sha256': hashlib.sha256(raw.encode('utf-8')).hexdigest(), 'units': units}
    return {'seconds': time.monotonic() - started, 'protocols': protocols}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xml-dir', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = capture(args.xml_dir)
    with gzip.open(args.output, 'wt', encoding='utf-8') as target:
        json.dump(result, target, ensure_ascii=False, separators=(',', ':'))
    print(f"{len(result['protocols'])} sources, {result['seconds']:.2f}s, {args.output}")
