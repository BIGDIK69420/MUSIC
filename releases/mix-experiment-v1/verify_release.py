"""Verify V1 or its downloaded package with Python's standard library only."""
from pathlib import Path
import hashlib
import json
import sys

root = Path(__file__).resolve().parent
manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
checked, external, errors = [], [], []
for row in manifest['files']:
    path = root / row['file']
    if not path.is_file():
        if row['in_package']:
            errors.append({'file': row['file'], 'error': 'Missing required package file'})
        else:
            external.append(row['file'])
        continue
    sha = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            sha.update(block)
    if path.stat().st_size != row['bytes'] or sha.hexdigest() != row['sha256']:
        errors.append({'file': row['file'], 'error': 'Size or SHA-256 mismatch'})
    else:
        checked.append(row['file'])

result = {'status': 'PASS' if not errors else 'FAIL', 'verified_files': len(checked),
          'separately_downloadable_stems_not_present': external, 'errors': errors,
          'scope': 'File integrity against the V1 manifest. Does not assess sound quality.'}
print(json.dumps(result, ensure_ascii=False, indent=2))
sys.exit(bool(errors))
