"""Check the immutable release files before regenerating outputs."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
manifest = json.loads((ROOT/'release_manifest.json').read_text(encoding='utf-8'))
failures = []
for name, expected in manifest['sha256'].items():
    path = ROOT/name
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        failures.append(name)
if failures:
    print('Changed or missing release files:', *failures, sep='\n')
    sys.exit(1)
print(f"Verified {len(manifest['sha256'])} release files.")
