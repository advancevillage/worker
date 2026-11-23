#!/usr/bin/env python3
"""Render all physical PDF pages and preserve text positions for page-number detection."""
import argparse
from pathlib import Path

from common import read_json, sha256, write_json


def render(book_dir, dpi=300, image_format="png"):
    import pymupdf
    from PIL import Image
    if image_format not in ('png','jpg'):raise ValueError('Supported formats: png/jpg')
    if not 72 <= dpi <= 600:
        raise ValueError('DPI must be between 72 and 600')
    book_dir = Path(book_dir)
    pdf = book_dir / 'source.pdf'
    source = read_json(book_dir / 'download.json')
    digest = sha256(pdf)
    if digest != source['sha256']:
        raise ValueError('PDF differs from download manifest')
    state_path = book_dir / 'render.json'
    if state_path.exists():
        old = read_json(state_path)
        if old['pdf_sha256'] == digest and old['dpi'] == dpi and old.get('image_format','jpg') == image_format:
            try:
                for row in old['pages']:
                    path = book_dir / row['image']
                    if sha256(path) != row['sha256']:
                        raise ValueError('Image changed')
                    with Image.open(path) as im:
                        im.load()
                if len(old['pages']) == source['pages']:
                    print('复用已校验渲染结果', flush=True)
                    return old
            except (ValueError, OSError):
                pass
    images = book_dir / 'physical'
    images.mkdir(exist_ok=True)
    rows = []
    with pymupdf.open(pdf) as doc:
        for i, page in enumerate(doc):
            path = images / f'{i + 1:04d}.{image_format}'
            pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False)
            temp = path.with_name(path.name+'.part')
            temp.write_bytes(pix.tobytes('png') if image_format=='png' else pix.tobytes('jpeg', jpg_quality=95))
            with Image.open(temp) as im:
                im.load()
            temp.replace(path)
            # Text bbox coordinates normalized in displayed page coordinates.
            words = []
            for x0, y0, x1, y1, text, *_ in page.get_text('words'):
                rect = pymupdf.Rect(x0, y0, x1, y1) * page.rotation_matrix
                words.append(dict(text=text, x0=rect.x0 / page.rect.width,
                                  y0=rect.y0 / page.rect.height,
                                  x1=rect.x1 / page.rect.width, y1=rect.y1 / page.rect.height,
                                  confidence=1.0, method='pdf_text'))
            rows.append(dict(physical_page=i + 1, image=str(path.relative_to(book_dir)),
                             sha256=sha256(path), width=pix.width, height=pix.height,
                             text=page.get_text(), words=words))
            if (i + 1) % 20 == 0:
                print(f'渲染 {i + 1}/{len(doc)}', flush=True)
    state = dict(pdf_sha256=digest, dpi=dpi, image_format=image_format, pages=rows)
    write_json(state_path, state)
    return state


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--book-dir', type=Path, required=True)
    parser.add_argument('--dpi', type=int, default=300)
    parser.add_argument('--format', choices=['png','jpg'], default='png')
    args = parser.parse_args()
    render(args.book_dir, args.dpi, args.format)
