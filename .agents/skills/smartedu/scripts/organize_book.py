#!/usr/bin/env python3
"""Validate reviewed page map and replace final book directory with a backed-up transaction."""
import argparse
import os
import shutil
import tempfile
import time
from collections import Counter
from pathlib import Path

from common import DEFAULT_OUTPUT, check_pdf, read_json, safe_component, sha256, write_json
from identify_pages import validate_mapping


def organize(book_dir, output=DEFAULT_OUTPUT):
    from PIL import Image
    book_dir = Path(book_dir).resolve()
    download = read_json(book_dir / 'download.json')
    rendered = read_json(book_dir / 'render.json')
    mapping = read_json(book_dir / 'mapping.json')
    source = book_dir / 'source.pdf'
    digest = sha256(source)
    if any(x != digest for x in (download['sha256'], rendered['pdf_sha256'], mapping['pdf_sha256'])):
        raise ValueError('Pipeline stages do not refer to the same PDF')
    count = check_pdf(source)
    mapping_digest = sha256(book_dir / 'mapping.json')
    errors = validate_mapping(mapping, count)
    if errors:
        raise ValueError('归档暂停，需核对mapping.json：\n' + '\n'.join(errors))
    records = {r['physical_page']: r for r in rendered['pages']}
    for row in mapping['pages']:
        record = records[row['physical_page']]
        if row['image'] != record['image'] or row['image_sha256'] != record['sha256']:
            raise ValueError('Mapping changed the physical image identity')
        path = (book_dir / row['image']).resolve()
        if not path.is_relative_to(book_dir) or sha256(path) != row['image_sha256']:
            raise ValueError('Image path or checksum does not match render manifest')
        with Image.open(path) as im:
            im.load()
    target = Path(output).expanduser().resolve().joinpath(*(
        safe_component(download[k]) for k in ('grade', 'subject', 'volume')))
    meta = {k: download.get(k) for k in ('isbn', 'subject', 'volume', 'publisher')}
    receipt_path = book_dir / 'archive.json'
    journal_path = book_dir / 'archive-pending.json'
    if journal_path.exists():
        journal = read_json(journal_path)
        if journal['target'] != str(target) or journal['pdf_sha256'] != digest:
            raise ValueError('An unfinished archive belongs to another output/version')
        if target.exists() and (target / '教材.pdf').exists() and sha256(target / '教材.pdf') == digest:
            if all((target / r['file']).exists() and sha256(target / r['file']) == r['sha256']
                   for r in journal['files']) and read_json(target / 'meta.json') == meta:
                write_json(receipt_path, journal)
                journal_path.unlink()
        elif not target.exists() and journal.get('backup') and Path(journal['backup']).exists():
            os.rename(journal['backup'], target)
            journal_path.unlink()
    receipt = read_json(receipt_path) if receipt_path.exists() else None
    if target.exists():
        old_meta = target / 'meta.json'
        if not old_meta.exists():
            raise ValueError('Existing directory has no metadata; refusing to replace')
        old = read_json(old_meta)
        if old.get('resource_id'):
            if old['resource_id'] != download['resource_id']:
                raise ValueError('Existing book belongs to another resource')
            if old.get('version') and old['version'] != download['version']:
                raise ValueError('Existing edition differs')
            if old.get('source_update_time') and old['source_update_time'] != download['source_update_time']:
                raise ValueError('Existing resource revision differs')
        elif not receipt or receipt.get('target') != str(target) or receipt.get('pdf_sha256') != digest:
            raise ValueError('No matching archive receipt; cannot establish existing book identity')
        for key in ('subject', 'volume', 'publisher'):
            if old.get(key) != meta[key]:
                raise ValueError(f'Existing metadata conflict: {key}')
        if (receipt and receipt.get('mapping_sha256') == mapping_digest
                and old == meta and (target / '教材.pdf').exists()
                and sha256(target / '教材.pdf') == digest
                and len(list((target / 'image').glob('*.*'))) == count
                and all((target / row['file']).exists() and sha256(target / row['file']) == row['sha256']
                        for row in receipt['files'])):
            print(f'复用已校验归档：{target}', flush=True)
            return target
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f'.{target.name}-stage-', dir=target.parent))
    backup = None
    renamed = False
    try:
        (staging / 'image').mkdir()
        counters = Counter()
        names = set()
        file_records = []
        for row in mapping['pages']:
            category = row['category']
            if category == '正文':
                name = f"{row['printed_page']}{Path(row['image']).suffix}"
            else:
                counters[category] += 1
                name = f'{category}-{counters[category]:02d}{Path(row["image"]).suffix}'
            if name in names:
                raise ValueError(f'Duplicate output filename: {name}')
            names.add(name)
            shutil.copyfile(book_dir / row['image'], staging / 'image' / name)
            file_records.append(dict(physical_page=row['physical_page'], file=f'image/{name}',
                                     sha256=row['image_sha256']))
        shutil.copyfile(source, staging / '教材.pdf')
        write_json(staging / 'meta.json', meta)
        if len(list((staging / 'image').iterdir())) != count:
            raise ValueError('Output count differs from PDF')
        if target.exists():
            backups = book_dir / 'backups'
            backups.mkdir(exist_ok=True)
            backup = backups / f'{target.name}-{time.time_ns()}'
        new_receipt = dict(target=str(target), pdf_sha256=digest,
                           mapping_sha256=mapping_digest,
                           resource_id=download['resource_id'], pages=count,
                           backup=str(backup) if backup else None, files=file_records)
        write_json(journal_path, new_receipt)
        if backup:
            # Rename rather than delete; a cross-device error leaves original untouched.
            os.rename(target, backup)
            renamed = True
        try:
            os.rename(staging, target)
        except BaseException:
            if renamed:
                os.rename(backup, target)
            raise
        write_json(receipt_path, new_receipt)
        journal_path.unlink()
        print(f'归档完成：{target}（{count}张）', flush=True)
        return target
    finally:
        if staging.exists():
            shutil.rmtree(staging)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--book-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    organize(args.book_dir, args.output)
