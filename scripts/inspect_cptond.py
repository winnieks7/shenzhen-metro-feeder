"""Inspect downloaded CPTOND Shapefile attributes using only the standard library.

Counts are raw records, not independently validated operating routes/stations.
"""
from collections import Counter
from pathlib import Path
import json
import struct

ROOT = Path(__file__).resolve().parents[1]


def read_dbf(path):
    data = path.read_bytes()
    count, header_length, record_length = struct.unpack_from('<IHH', data, 4)
    fields = []
    for pos in range(32, header_length - 1, 32):
        raw = data[pos:pos+32]
        fields.append((raw[:11].split(b'\x00')[0].decode('ascii'), chr(raw[11]), raw[16]))
    records = []
    for index in range(count):
        raw = data[header_length+index*record_length:header_length+(index+1)*record_length]
        if len(raw) != record_length:
            raise ValueError('Truncated DBF')
        if raw[:1] == b'*':
            continue
        row, pos = {}, 1
        for name, kind, size in fields:
            row[name] = raw[pos:pos+size].decode('utf-8').strip()
            pos += size
        records.append(row)
    return fields, records


def main():
    base = ROOT / 'data/CPTOND2025_Shenzhen'
    report = {'scope': 'raw data feasibility inspection, not an operational network validation', 'layers': {}}
    for mode in ['bus', 'metro']:
        layers = {}
        for path in sorted((base/mode).glob('*.dbf')):
            fields, rows = read_dbf(path)
            entry = {'rows': len(rows), 'fields': [f[0] for f in fields], 'sample': rows[:2]}
            if path.stem.endswith('_routes'):
                entry['status_counts'] = dict(Counter(r.get('status', '') for r in rows))
                entry['type_counts'] = dict(Counter(r.get('route_type', '') for r in rows))
                entry['start_time_nonempty'] = sum(bool(r.get('start_time')) for r in rows)
                entry['end_time_nonempty'] = sum(bool(r.get('end_time')) for r in rows)
                entry['status_examples'] = {s: [r['route_cn'] for r in rows if r.get('status') == s][:4]
                                            for s in entry['status_counts']}
                layers['routes'] = rows
            if path.stem.endswith('_stops'):
                entry['unique_route_ids'] = len({r['route_id'] for r in rows})
                entry['sequence_missing'] = sum(not r.get('sequence') for r in rows)
                layers['stops'] = rows
            report['layers'][path.stem] = entry
        names = {r['route_cn'] for r in layers['routes']}
        report[mode+'_stop_rows_without_matching_route_name'] = sum(r['route_cn'] not in names for r in layers['stops'])
    report['important_limit'] = 'Raw metro routes include planned/under-construction names. Verify status meanings and line-specific opening dates before filtering. Unique-stops layer is not the operating station count.'
    (base/'feasibility.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    for name, layer in report['layers'].items():
        print(name, json.dumps({k:v for k,v in layer.items() if k!='sample'}, ensure_ascii=False))
    print(report['important_limit'])


if __name__ == '__main__':
    main()
