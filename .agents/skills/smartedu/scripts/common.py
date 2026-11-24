"""Shared state utilities. Runtime records never go into final meta.json."""
import hashlib
import json
import os
import re
from pathlib import Path
from urllib.parse import unquote

DEFAULT_WORK = Path.home() / 'Library/Caches/smartedu-pipeline'
DEFAULT_OUTPUT = Path.home() / 'Downloads/教材'


def read_json(path):
    return json.loads(Path(path).read_text())


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.part')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    os.replace(temp, path)


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def safe_component(value):
    if not isinstance(value, str) or not value or value in ('.', '..') or any(c in value for c in '/\\\0'):
        raise ValueError('Invalid directory component')
    return value


def isbn_from_filename(filename):
    # Only bounded ISBN-like strings, never arbitrary timestamps/substrings.
    candidates = re.findall(r'(?<![0-9A-Za-z])(?:97[89][0-9-]{10,16}|[0-9][0-9-]{8,14}[0-9Xx])(?![0-9A-Za-z])', unquote(filename))
    valid = set()
    for token in candidates:
        value = token.replace('-', '').upper()
        if len(value) == 13 and value.isdigit() and value.startswith(('978', '979')):
            if sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(value)) % 10 == 0:
                valid.add(value)
        elif len(value) == 10 and value[:9].isdigit() and (value[-1].isdigit() or value[-1] == 'X'):
            if sum((10 - i) * (10 if c == 'X' else int(c)) for i, c in enumerate(value)) % 11 == 0:
                valid.add(value)
    if len(valid) > 1:
        raise ValueError('Multiple ISBNs in filename; explicit review required')
    return next(iter(valid), None)


def check_pdf(path):
    import pymupdf
    with pymupdf.open(path) as doc:
        if not doc.is_pdf or doc.needs_pass or doc.page_count == 0:
            raise ValueError('PDF is invalid, empty or encrypted')
        # Read every page object to detect broken page trees.
        for page in doc:
            _ = page.rect
        return doc.page_count
