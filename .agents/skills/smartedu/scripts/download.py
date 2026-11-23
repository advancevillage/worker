#!/usr/bin/env python3
"""Download SmartEdu grade-one Chinese pages with explicit completeness state."""
import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import quote

BASE = 'https://s-file-1.ykt.cbern.com.cn/zxx'
TAGS = {'e7bbb2de-0590-11ed-9c79-92fc3b3249d5',
        '6a749654-0772-11ed-ac74-092ab92074e6',
        '44bee8bc-54e6-11ed-9c34-850ba61fa9f4',
        'e7bbd296-0590-11ed-9c79-92fc3b3249d5'}


class HTTPError(Exception):
    def __init__(self, status):
        self.status = status
        super().__init__(f'HTTP {status}')


def fetch(url, path):
    for attempt in range(3):
        result = subprocess.run(['curl', '--silent', '--show-error', '--location',
                                 '--connect-timeout', '15', '--max-time', '60',
                                 '--output', str(path), '--write-out', '%{http_code}',
                                 quote(url, safe=':/?=&%')], capture_output=True, text=True)
        code = int(result.stdout) if result.stdout.isdigit() else 0
        if result.returncode == 0 and code == 200:
            return
        if code in (401, 403) or (code and code != 429 and code < 500):
            raise HTTPError(code)
        if attempt == 2:
            raise HTTPError(code)
        time.sleep(2 ** attempt)


def get_json(url):
    with tempfile.TemporaryDirectory(prefix='smartedu-') as tmp:
        path = Path(tmp) / 'response.json'
        fetch(url, path)
        return json.loads(path.read_text())


def write_meta(path, meta):
    temp = path.with_suffix('.json.part')
    temp.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def component(value):
    if not value or value in ('.', '..') or '/' in value or '\\' in value:
        raise ValueError('Invalid output path component')
    return value


def inspect_image(path):
    if path.read_bytes()[:3] != b'\xff\xd8\xff':
        raise ValueError('Not JPEG')
    # Re-encoding forces ImageIO to decode the pixels, beyond checking the header.
    with tempfile.TemporaryDirectory(prefix='smartedu-check-') as tmp:
        checked = Path(tmp) / 'checked.jpg'
        result = subprocess.run(['sips', '-s', 'format', 'jpeg', str(path),
                                 '--out', str(checked)], capture_output=True)
        if result.returncode or not checked.exists():
            raise ValueError('Image cannot be decoded')
    result = subprocess.run(['sips', '-g', 'pixelWidth', '-g', 'pixelHeight', str(path)],
                            capture_output=True, text=True, check=True)
    width = re.search(r'pixelWidth: (\d+)', result.stdout)
    height = re.search(r'pixelHeight: (\d+)', result.stdout)
    if not width or not height or min(int(width[1]), int(height[1])) <= 0:
        raise ValueError('Invalid image size')
    return dict(width=int(width[1]), height=int(height[1]),
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def download_book(detail, root, catalog_version):
    tags = {t['tag_dimension_id']: t['tag_name'] for t in detail['tag_list']}
    identity = dict(grade=tags['zxxnj'], subject=tags['zxxxk'],
                    version=tags['zxxbb'], volume=tags['zxxcc'],
                    publisher='、'.join(p['name'] for p in detail['provider_list']),
                    resource_id=detail['id'], source_update_time=detail['update_time'])
    target = root.joinpath(*(component(identity[k]) for k in ('grade', 'subject', 'volume')))
    meta_path = target / 'meta.json'
    old = json.loads(meta_path.read_text()) if meta_path.exists() else None
    if old and any(old.get(k) != v for k, v in identity.items()):
        raise ValueError(f'Existing resource/version conflict: {target}')
    if not old and target.exists() and any(target.iterdir()):
        raise ValueError(f'Existing files without metadata: {target}')
    item = next(t for t in detail['ti_items'] if t['ti_file_flag'] == 'image')
    count = int(next(r['value'] for r in item['custom_properties']['requirements']
                     if r['name'] == 'pagesize'))
    previews = {int(k.removeprefix('Slide')): v for k, v in
                detail['custom_properties']['preview'].items() if re.fullmatch(r'Slide\d+', k)}
    # Source metadata declares a page-image folder; preview entries establish 1-based filenames.
    for n, url in previews.items():
        if not url.endswith(f'/image/{n}.jpg') or not 1 <= n <= count:
            raise ValueError('Unrecognized page numbering')
    image_dir = target / 'image'
    image_dir.mkdir(parents=True, exist_ok=True)
    expected_names = {f'{i}.jpg' for i in range(count)}
    if any(p.name not in expected_names and not p.name.endswith('.part') for p in image_dir.iterdir()):
        raise ValueError('Unexpected image files; refusing to mix page sets')
    meta = dict(identity, title=detail['title'], revision='根据2022年版课程标准修订',
                source_url=f"{BASE}/ndrv2/resources/tch_material/details/{detail['id']}.json",
                catalog_version=catalog_version, expected_pages=count,
                downloaded_pages=0, status='downloading', pages=[])
    records = {p['index']: p for p in (old or {}).get('pages', [])}
    blocked = False
    write_meta(meta_path, meta)
    for index in range(count):
        page_number = index + 1
        path = image_dir / f'{index}.jpg'
        record = dict(index=index, source_page=page_number, file=f'image/{index}.jpg')
        try:
            cached = records.get(index, {})
            good = False
            if path.exists() and cached.get('sha256'):
                try:
                    info = inspect_image(path)
                    good = info['sha256'] == cached['sha256']
                except (ValueError, subprocess.CalledProcessError):
                    pass
            if not good:
                if blocked and page_number not in previews:
                    raise HTTPError(401)
                url = previews.get(page_number) or item['ti_storages'][0].rstrip('/') + f'/{page_number}.jpg'
                temp = path.with_suffix('.jpg.part')
                try:
                    fetch(url, temp)
                    info = inspect_image(temp)
                    temp.replace(path)
                finally:
                    temp.unlink(missing_ok=True)
            record.update(info, status='verified', acquisition_method='source_image')
        except HTTPError as exc:
            if exc.status in (401, 403):
                blocked = True
            record.update(status='requires_authentication' if blocked else 'failed',
                          error=str(exc))
        except (ValueError, subprocess.CalledProcessError) as exc:
            record.update(status='failed', error=type(exc).__name__)
        meta['pages'].append(record)
        meta['downloaded_pages'] = sum(p['status'] == 'verified' for p in meta['pages'])
        write_meta(meta_path, meta)
        if page_number % 10 == 0:
            print(f"{identity['volume']}: {meta['downloaded_pages']}/{count}", flush=True)
        time.sleep(0.1)
    meta['missing_pages'] = [p['index'] for p in meta['pages'] if p['status'] != 'verified']
    meta['status'] = ('complete' if not meta['missing_pages'] else
                      'requires_authentication' if blocked else 'failed')
    write_meta(meta_path, meta)
    print(f"{identity['volume']}: {meta['status']} {meta['downloaded_pages']}/{count}", flush=True)
    return meta['status'] == 'complete'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('~/Downloads/教材'))
    args = parser.parse_args()
    version = get_json(f'{BASE}/ndrs/resources/tch_material/version/data_version.json')
    matches = []
    for url in version['urls'].split(','):
        matches.extend(x for x in get_json(url)
                       if TAGS <= {t['tag_id'] for t in x['tag_list']})
    by_volume = {}
    for x in matches:
        volume = next(t['tag_name'] for t in x['tag_list'] if t['tag_dimension_id'] == 'zxxcc')
        if volume in by_volume:
            raise ValueError(f'Ambiguous edition: {volume}')
        by_volume[volume] = x
    if set(by_volume) != {'上册', '下册'}:
        raise ValueError('Expected exactly upper and lower volumes')
    complete = True
    for volume in ('上册', '下册'):
        detail = get_json(f"{BASE}/ndrv2/resources/tch_material/details/{by_volume[volume]['id']}.json")
        complete = download_book(detail, args.output.expanduser(), version['module_version']) and complete
    return 0 if complete else 2


if __name__ == '__main__':
    raise SystemExit(main())
