#!/usr/bin/env python3
"""Identify printed numbers and sections; unresolved pages require explicit review."""
import argparse
import html
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

from common import read_json, sha256, write_json

CATEGORIES = {'封面', '版权页', '序言', '目录', '正文', '后记', '封底', '空白页'}


def footer_candidates(words):
    candidates = []
    for word in words:
        text = word['text'].strip().translate(str.maketrans('０１２３４５６７８９', '0123456789'))
        if (re.fullmatch(r'[1-9][0-9]{0,3}', text) and word['y0'] >= .86
                and (word['x1'] <= .35 or word['x0'] >= .65)
                and word.get('confidence', 0) >= .8):
            candidates.append(int(text))
    return sorted(set(candidates))


def compile_ocr(book_dir):
    source = Path(__file__).with_name('vision_ocr.swift')
    cache = Path(book_dir).parent / 'tools'
    cache.mkdir(exist_ok=True)
    binary = cache / 'vision_ocr'
    stamp = cache / 'vision_ocr.sha256'
    digest = sha256(source)
    if not binary.exists() or not stamp.exists() or stamp.read_text() != digest:
        subprocess.run(['swiftc', '-module-cache-path', str(cache / 'module-cache'),
                        str(source), '-o', str(binary)], check=True)
        stamp.write_text(digest)
    return binary


def recognize(book_dir, row, binary):
    cache = Path(book_dir) / 'ocr'
    cache.mkdir(exist_ok=True)
    path = cache / f"{row['physical_page']:04d}.json"
    if path.exists():
        old = read_json(path)
        if old['image_sha256'] == row['sha256']:
            return old['words']
    result = subprocess.run([str(binary), str(Path(book_dir) / row['image'])],
                            check=True, capture_output=True, text=True)
    words = json.loads(result.stdout)
    write_json(path, dict(image_sha256=row['sha256'], words=words))
    return words


def classify(text, physical_page, total, number):
    compact = re.sub(r'\s+', '', text)
    lines = [re.sub(r'\s+', '', line) for line in text.splitlines()]
    if any(line in ('后记', '编后记', '后记。') for line in lines):
        return '后记', 'explicit_heading'
    if any(line in ('目录', '目次', 'CONTENTS', 'Contents') for line in lines) and number is None:
        return '目录', 'explicit_heading'
    if any(line in ('前言', '序言', '编者的话', '致同学', '致同学们', '写给同学们') for line in lines) and number is None:
        return '序言', 'explicit_heading'
    if number is not None:
        return '正文', 'printed_footer'
    if (('ISBN' in text.upper() and ('定价' in compact or '责任编辑' in compact or '版次' in compact))
            or ('责任编辑' in compact and ('编修委员会' in compact or '出版' in compact))):
        return ('封底' if physical_page == total else '版权页'), 'copyright_text'
    if physical_page <= 3 and ('教科书' in compact or '出版社' in compact) and ('册' in compact or '年级' in compact):
        return '封面', 'cover_text'
    return None, 'needs_review'


def validate_mapping(mapping, count):
    errors = []
    rows = mapping['pages']
    if [r['physical_page'] for r in rows] != list(range(1, count + 1)):
        errors.append('映射未按物理页顺序完整覆盖PDF')
    numbers = []
    for row in rows:
        n = row.get('printed_page')
        if row.get('category') not in CATEGORIES:
            errors.append(f"物理页{row['physical_page']}分类未确认")
        if row.get('category') == '正文':
            if type(n) is not int or n <= 0:
                errors.append(f"物理页{row['physical_page']}缺少正整数印刷页码")
            else:
                numbers.append(n)
        if row.get('issues') and not row.get('reviewed', False):
            errors.append(f"物理页{row['physical_page']}需核对：{'；'.join(row['issues'])}")
    duplicate = [n for n, c in Counter(numbers).items() if c > 1]
    if duplicate:
        errors.append(f'正文页码重复：{duplicate}')
    if numbers != sorted(numbers):
        errors.append('正文页码未递增')
    return errors


def write_review(book_dir, mapping, errors):
    blocks = []
    body_pages = [r['physical_page'] for r in mapping['pages'] if r.get('category') == '正文']
    boundaries = {body_pages[0], body_pages[-1]} if body_pages else set()
    for row in mapping['pages']:
        issues = row.get('issues', [])
        if not issues and row.get('category') == '正文' and row['physical_page'] not in boundaries:
            continue
        blocks.append(f'<section><h2>物理页 {row["physical_page"]}</h2>'
                      f'<p>{html.escape(str(row.get("category")))}；页码 {row.get("printed_page")}；'
                      f'{html.escape("；".join(issues))}</p>'
                      f'<img loading="lazy" src="{html.escape(row["image"])}"></section>')
    body = '<!doctype html><meta charset="utf-8"><title>教材页码核对</title><style>body{font-family:sans-serif;margin:24px}section{display:inline-block;vertical-align:top;width:45%;margin:1%}img{width:100%}</style>'
    body += '<h1>教材分类与印刷页码核对</h1><p>编辑 mapping.json 对应页的 category、printed_page、reviewed。不能跳过或丢弃PDF页面。</p>'
    body += '<pre>' + html.escape('\n'.join(errors)) + '</pre>' + ''.join(blocks)
    (Path(book_dir) / 'review.html').write_text(body)


def identify(book_dir, use_ocr=True, refresh=False):
    book_dir = Path(book_dir)
    rendered = read_json(book_dir / 'render.json')
    target = book_dir / 'mapping.json'
    if target.exists() and not refresh:
        mapping = read_json(target)
        if mapping['pdf_sha256'] != rendered['pdf_sha256']:
            raise ValueError('Mapping belongs to another PDF')
        errors = validate_mapping(mapping, len(rendered['pages']))
        write_review(book_dir, mapping, errors)
        return mapping, errors
    binary = None
    mapped = []
    total = len(rendered['pages'])
    for row in rendered['pages']:
        words = row['words']
        candidates = footer_candidates(words)
        text = row['text']
        if use_ocr and (len(candidates) != 1 or len(text.strip()) < 30):
            binary = binary or compile_ocr(book_dir)
            ocr = recognize(book_dir, row, binary)
            # A conflict between text and OCR is explicit, not silently resolved.
            candidates = sorted(set(candidates + footer_candidates(ocr)))
            if len(text.strip()) < 30:
                text = '\n'.join(w['text'] for w in ocr)
        number = candidates[0] if len(candidates) == 1 else None
        category, reason = classify(text, row['physical_page'], total, number)
        issues = []
        if category is None:
            issues.append('页面类别或页码未识别')
        if len(candidates) > 1:
            issues.append(f'页脚存在多个候选：{candidates}')
        mapped.append(dict(physical_page=row['physical_page'], image=row['image'],
                           image_sha256=row['sha256'], category=category, printed_page=number,
                           candidates=candidates, reason=reason, reviewed=False, issues=issues))
        if row['physical_page'] % 20 == 0:
            print(f"页码识别 {row['physical_page']}/{total}", flush=True)
    # Check actual observed numbers, never synthesize a page number from an offset.
    body = [r for r in mapped if r['category'] == '正文']
    for i, row in enumerate(body):
        adjacent = ((i > 0 and body[i - 1]['printed_page'] + 1 == row['printed_page']
                     and body[i - 1]['physical_page'] + 1 == row['physical_page']) or
                    (i + 1 < len(body) and body[i + 1]['printed_page'] - 1 == row['printed_page']
                     and body[i + 1]['physical_page'] - 1 == row['physical_page']))
        if not adjacent:
            row['issues'].append('页码未获邻页连续性支持')
        if i and (row['printed_page'] != body[i - 1]['printed_page'] + 1):
            row['issues'].append('正文印刷页码跳号或重复，需核对')
    mapping = dict(pdf_sha256=rendered['pdf_sha256'], pages=mapped)
    write_json(target, mapping)
    errors = validate_mapping(mapping, total)
    write_review(book_dir, mapping, errors)
    return mapping, errors


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--book-dir', type=Path, required=True)
    p.add_argument('--no-ocr', action='store_true')
    p.add_argument('--refresh', action='store_true', help='重新识别，覆盖人工映射；默认保留修正')
    args = p.parse_args()
    mapping, errors = identify(args.book_dir, not args.no_ocr, args.refresh)
    print('\n'.join(errors) if errors else '全部页面映射检查通过')
    raise SystemExit(2 if errors else 0)
