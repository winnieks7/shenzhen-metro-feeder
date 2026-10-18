"""Download only Shenzhen entries from the public CPTOND-2025 v2 archive.

Uses verified HTTP byte ranges and ZIP CRC checks; does not download the 2 GB
national archive and does not execute any code shipped in the dataset.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import struct
import urllib.request
import zlib

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://ndownloader.figshare.com/files/58153174'
TOTAL = 2163720849


def fetch_group(label, entries):
    start = min(e['offset'] for e in entries)
    end = max(e['offset'] + 30 + len(e['name'].encode()) + e['compressed'] + 512 for e in entries)
    cache = ROOT / 'research' / 'download_ranges' / f'{label}_{start}_{end}.bin'
    cache.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(5):
        have = cache.stat().st_size if cache.exists() else 0
        if have == end-start+1:
            break
        if have > end-start+1:
            raise RuntimeError('Invalid cached range length')
        req = urllib.request.Request(URL, headers={'Range': f'bytes={start+have}-{end}'})
        with urllib.request.urlopen(req, timeout=120) as response:
            expected = f'bytes {start+have}-{end}/{TOTAL}'
            if response.status != 206 or response.headers.get('Content-Range') != expected:
                raise RuntimeError(f'Unexpected range response for {label}: {response.status}, {response.headers.get("Content-Range")}')
            with cache.open('ab') as output:
                while True:
                    chunk = response.read(1024*1024)
                    if not chunk:
                        break
                    output.write(chunk)
    if cache.stat().st_size != end-start+1:
        raise RuntimeError('Incomplete range after retries')
    block = cache.read_bytes()
    records = []
    for entry in entries:
        pos = entry['offset'] - start
        header = struct.unpack_from('<IHHHHHIIIHH', block, pos)
        if header[0] != 0x04034B50:
            raise RuntimeError('Invalid local ZIP header')
        name_len, extra_len = header[-2:]
        observed = block[pos+30:pos+30+name_len].decode('utf-8')
        if observed != entry['name']:
            raise RuntimeError('ZIP member name mismatch')
        begin = pos + 30 + name_len + extra_len
        compressed = block[begin:begin+entry['compressed']]
        payload = zlib.decompress(compressed, -15) if entry['method'] == 8 else compressed
        if len(payload) != entry['bytes'] or zlib.crc32(payload) != entry['crc']:
            raise RuntimeError('ZIP member length or CRC mismatch')
        target = ROOT / 'data' / 'CPTOND2025_Shenzhen' / label / Path(entry['name']).name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        records.append({'archive_member': entry['name'], 'local_path': str(target.relative_to(ROOT)),
                        'bytes': len(payload), 'crc32': entry['crc'],
                        'sha256': hashlib.sha256(payload).hexdigest()})
    print(f'{label}: verified and extracted {len(records)} files', flush=True)
    return records


def main():
    entries = json.loads((ROOT / 'research/CPTOND_archive_index.json').read_text())
    groups = {}
    for mode in ['bus', 'metro']:
        groups[mode] = [e for e in entries if f'/dataset/{mode}/shapefiles/Shenzhen/' in e['name'] and not e['name'].endswith('/')]
    groups['documentation'] = [e for e in entries if e['name'] == 'CPTOND-2025/code/README.md']
    records = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(fetch_group, label, group) for label, group in groups.items()]
        for future in futures:
            records.extend(future.result())
    manifest = {'doi': '10.6084/m9.figshare.29377427.v2', 'source': URL,
                'download_date_Asia_Shanghai': datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat(), 'license': 'CC BY 4.0',
                'data_snapshot': 'June 2025, per dataset description',
                'national_archive_md5_from_publisher': '8b786408d8a9d4d16faa531f98cc9fc6',
                'verification': 'Each extracted ZIP member CRC32 verified; national archive MD5 not independently verified because only a subset was downloaded',
                'files': records}
    expected = {r['archive_member']: r['sha256'] for r in json.loads((ROOT / 'research/input_manifest.json').read_text())['files']}
    if any(expected.get(r['archive_member']) != r['sha256'] for r in records):
        raise RuntimeError('Downloaded members differ from the study input manifest')
    (ROOT / 'data/CPTOND2025_Shenzhen/manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')


if __name__ == '__main__':
    main()
