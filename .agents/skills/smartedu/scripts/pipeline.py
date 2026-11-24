#!/usr/bin/env python3
"""Run independent download, render, identify and archive steps."""
import argparse
import subprocess
import sys
from pathlib import Path

from common import DEFAULT_OUTPUT, DEFAULT_WORK, read_json, safe_component


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--subject')
    p.add_argument('--grade')
    p.add_argument('--stage', default='小学')
    p.add_argument('--version', default='')
    p.add_argument('--year', default='')
    p.add_argument('--volume', default='全部', choices=['全部', '上册', '下册'])
    p.add_argument('--work-dir', type=Path, default=DEFAULT_WORK)
    p.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    p.add_argument('--dpi', type=int, default=300)
    p.add_argument('--login-timeout', type=int, default=900)
    p.add_argument('--start', choices=['download', 'render', 'identify', 'organize', 'compress', 'extract', 'flat'], default='download')
    p.add_argument('--content-images', nargs='+', help='样本提取文件名，如 封面-01.jpg 4.jpg')
    p.add_argument('--content-review-dir', type=Path, help='含 {图片名不含后缀}.review.json 的核对目录')
    p.add_argument('--compress', action='store_true', help='归档后通过TinyPNG对封面和正文连续压缩（默认两轮）')
    p.add_argument('--compression-rounds', type=int, help='新任务默认2轮；旧任务保留目标')
    p.add_argument('--compression-tabs', type=int, default=3)
    p.add_argument('--compression-action', choices=['run', 'status', 'pause', 'resume', 'continue-full', 'close'], default='run')
    p.add_argument('--book-dir', type=Path, help='恢复单册时指定目录')
    args = p.parse_args()
    scripts = Path(__file__).resolve().parent
    def run(name, arguments):
        return subprocess.run([sys.executable, str(scripts / name), *map(str, arguments)]).returncode
    if args.start == 'flat':
        if not args.book_dir:
            p.error('--start flat requires --book-dir')
        arguments = ['--book-dir', args.book_dir, '--output', args.output, '--work-dir', args.work_dir]
        if args.content_images:
            arguments += ['--images', *args.content_images]
        if args.content_review_dir:
            arguments += ['--review-dir', args.content_review_dir]
        return run('flat_pipeline.py', arguments)
    if args.start == 'compress':
        arguments = ['--work-dir', args.work_dir, '--tabs', args.compression_tabs, '--action', args.compression_action]
        if args.book_dir:
            arguments += ['--book-dir', args.book_dir]
        if args.compression_rounds is not None:
            arguments += ['--rounds', args.compression_rounds]
        return run('compress_images.py', arguments)
    if args.start == 'download':
        args.subject = args.subject or input('学科：').strip()
        args.grade = args.grade or input('年级：').strip()
        code = run('download_pdf.py', ['--subject', args.subject, '--grade', args.grade,
                   '--stage', args.stage, '--version', args.version, '--year', args.year, '--volume', args.volume, '--work-dir', args.work_dir,
                   '--login-timeout', args.login_timeout])
        if code:
            return code
    books = [str(args.book_dir)] if args.book_dir else read_json(args.work_dir.expanduser() / 'books.json')
    if args.start == 'extract':
        if not args.content_images:
            p.error('样本提取需显式提供 --content-images')
        failed = False
        for book in books:
            target = Path(read_json(Path(book) / 'archive.json')['target'])
            for name in args.content_images:
                safe_component(name)
                if Path(name).suffix.lower() not in ('.jpg','.png'):
                    p.error('样本支持PNG/JPEG')
                arguments = ['--image', target / 'image' / name, '--output', target / 'content',
                             '--work-dir', Path(book) / 'content-work']
                if Path(name).stem.isdigit():
                    arguments += ['--printed-page', Path(name).stem]
                if args.content_review_dir:
                    arguments += ['--review', args.content_review_dir / (Path(name).stem + '.review.json')]
                failed = bool(run('extract_content.py', arguments)) or failed
        return 2 if failed else 0
    pending = False
    for book in books:
        if args.start in ('download', 'render'):
            if run('render_pdf.py', ['--book-dir', book, '--dpi', args.dpi]):
                pending = True
                continue
        if args.start in ('download', 'render', 'identify'):
            if run('identify_pages.py', ['--book-dir', book]):
                print(f'需核对：{Path(book) / "review.html"}；修正mapping.json后 --start organize', flush=True)
                pending = True
                continue
        if run('organize_book.py', ['--book-dir', book, '--output', args.output]):
            pending = True
    if args.compress and not pending:
        arguments = ['--work-dir', args.work_dir, '--tabs', args.compression_tabs]
        if args.book_dir:
            arguments += ['--book-dir', args.book_dir]
        if args.compression_rounds is not None:
            arguments += ['--rounds', args.compression_rounds]
        return run('compress_images.py', arguments)
    return 2 if pending else 0


if __name__ == '__main__':
    raise SystemExit(main())
