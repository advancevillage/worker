#!/usr/bin/env python3
"""Visible browser download; login is performed by the user in the browser."""
import argparse
import asyncio
import json
import time
from pathlib import Path
from urllib.parse import unquote, urlparse, urlencode

from common import DEFAULT_WORK, check_pdf, isbn_from_filename, read_json, sha256, write_json
from download import BASE, get_json

CATALOG = 'https://basic.smartedu.cn/elecEdu'


def select_resources(subject, grade, version, volume, stage="小学", year=""):
    manifest = get_json(f'{BASE}/ndrs/resources/tch_material/version/data_version.json')
    found = []
    for url in manifest['urls'].split(','):
        for book in get_json(url):
            tags = {t['tag_dimension_id']: t['tag_name'] for t in book.get('tag_list', [])}
            if tags.get('zxxxk') == subject and tags.get('zxxnj') == grade and tags.get('zxxxd') == stage:
                if year and tags.get('bknd') != year:
                    continue
                if version and tags.get('zxxbb') != version:
                    continue
                if volume != '全部' and tags.get('zxxcc') != volume:
                    continue
                found.append(book)
    if not found:
        raise ValueError('No textbooks match subject/grade/version/volume')
    editions = sorted({next(t['tag_name'] for t in x['tag_list'] if t['tag_dimension_id'] == 'zxxbb') for x in found})
    if len(editions) > 1:
        for i, name in enumerate(editions, 1):
            print(f'{i}. {name}')
        version = editions[int(input('请选择教材版本编号：')) - 1]
        found = [x for x in found if any(t['tag_name'] == version and t['tag_dimension_id'] == 'zxxbb' for t in x['tag_list'])]
    volumes = {}
    for book in found:
        term = next(t['tag_name'] for t in book['tag_list'] if t['tag_dimension_id'] == 'zxxcc')
        if term in volumes:
            raise ValueError(f'tell-me: {term}存在多个资源，请指定版本及 --year（如 2025年度），不能自动选择')
        volumes[term] = book
    return [volumes[v] for v in sorted(volumes, key=lambda v: (v != '上册', v))]


def book_info(detail):
    tags = {t['tag_dimension_id']: t['tag_name'] for t in detail['tag_list']}
    item = next(t for t in detail['ti_items'] if t.get('ti_is_source_file') and t.get('ti_format') == 'pdf')
    filename = unquote(Path(urlparse(item['ti_storages'][0]).path).name)
    req = {x['name']: x['value'] for x in item.get('custom_properties', {}).get('requirements', [])}
    return dict(resource_id=detail['id'], title=detail['title'], grade=tags['zxxnj'],
                subject=tags['zxxxk'], volume=tags['zxxcc'], version=tags['zxxbb'],
                publisher='、'.join(p['name'] for p in detail['provider_list']),
                source_filename=filename, isbn=isbn_from_filename(filename),
                source_update_time=detail['update_time'], expected_pages=int(req.get('pagesize', 0)),
                detail_url='https://basic.smartedu.cn/tchMaterial/detail?' + urlencode({
                    'contentType': 'assets_document', 'contentId': detail['id'],
                    'catalogType': 'tchMaterial', 'subCatalog': 'dzjc'}))


async def wait_reader(context, resource_id, timeout, work=None):
    deadline = time.monotonic() + timeout
    reported = 0
    while time.monotonic() < deadline:
        for page in context.pages:
            for frame in page.frames:
                try:
                    state = await frame.evaluate('''() => {
                        const a = window.PDFViewerApplication;
                        return {loaded: !!a?.pdfDocument, url: location.href};
                    }''')
                    if state['loaded'] and resource_id in unquote(state['url']):
                        return page, frame
                except Exception:
                    pass
        if time.monotonic() - reported > 30:
            print('等待教材阅读器；如页面要求登录，请在浏览器内手动登录。登录完成后自动继续。', flush=True)
            reported = time.monotonic()
            if work and context.pages:
                try:
                    await context.pages[0].screenshot(path=str(Path(work)/'reader-status.png'))
                except Exception:
                    pass
        await asyncio.sleep(1)
    raise TimeoutError('等待阅读器超时；登录状态已保留，可重新运行')


def load_cookies(path):
    path=Path(path).expanduser()
    if path.stat().st_mode & 0o077:
        raise ValueError('Cookie file must have owner-only permissions (chmod 600)')
    values=json.loads(path.read_text())
    if not isinstance(values,list) or not values:
        raise ValueError('Cookie file must contain a nonempty array')
    for cookie in values:
        if set(cookie)-{'name','value','domain','path','secure','httpOnly','sameSite','expires'}:
            raise ValueError('Unexpected cookie fields')
        if cookie.get('domain') not in ('basic.smartedu.cn','.basic.smartedu.cn') or cookie.get('path')!='/':
            raise ValueError('Cookies must be scoped to basic.smartedu.cn')
        if not all(isinstance(cookie.get(k),str) and cookie[k] for k in ('name','value')):
            raise ValueError('Invalid cookie fields')
    return values


async def inject_cookies(context, path):
    cookies=load_cookies(path)
    await context.add_cookies(cookies)
    # Report only the count, never cookie contents or token values.
    print(f'已注入 {len(cookies)} 条站点 Cookie',flush=True)


async def download_books(args, books):
    from playwright.async_api import async_playwright
    work = args.work_dir.expanduser().resolve()
    work.mkdir(parents=True, exist_ok=True)
    profile = (args.browser_profile.expanduser().resolve() if getattr(args, 'browser_profile', None) else work / 'browser-profile')
    profile.mkdir(exist_ok=True, mode=0o700)
    output = []
    async with async_playwright() as pw:
        context = await pw.chromium.launch_persistent_context(
            str(profile), channel='chrome', headless=False, accept_downloads=True,
            viewport={'width': 1400, 'height': 1000})
        try:
            if getattr(args, 'cookies_file', None):
                await inject_cookies(context, args.cookies_file)
            page = context.pages[0] if context.pages else await context.new_page()
            await page.goto(CATALOG, wait_until='domcontentloaded', timeout=60000)
            for entry in books:
                detail = await asyncio.to_thread(get_json, f"{BASE}/ndrv2/resources/tch_material/details/{entry['id']}.json")
                info = book_info(detail)
                book_dir = work / info['resource_id']
                book_dir.mkdir(exist_ok=True)
                source = book_dir / 'source.pdf'
                state_path = book_dir / 'download.json'
                if state_path.exists() and source.exists():
                    old = read_json(state_path)
                    if old.get('source_update_time') != info['source_update_time']:
                        raise ValueError('源版本已更新，请使用新的工作目录，避免混合版本')
                    if old.get('sha256') == sha256(source) and check_pdf(source) == old.get('pages'):
                        output.append(str(book_dir))
                        print(f"复用已校验PDF：{info['volume']}", flush=True)
                        continue
                await page.goto(info['detail_url'], wait_until='domcontentloaded', timeout=60000)
                reader_page, frame = await wait_reader(context, info['resource_id'], args.login_timeout, work)
                print(f"开始完整PDF下载：{info['title']}", flush=True)
                async with reader_page.expect_download(timeout=180000) as event:
                    await asyncio.wait_for(frame.evaluate('''async (filename) => {
                        const data = await window.PDFViewerApplication.pdfDocument.getData();
                        const url = URL.createObjectURL(new Blob([data], {type: 'application/pdf'}));
                        const a = document.createElement('a');
                        a.href = url; a.download = filename; document.body.appendChild(a); a.click();
                        setTimeout(() => {a.remove(); URL.revokeObjectURL(url)}, 60000);
                    }''', info['source_filename']), timeout=180)
                download = await event.value
                temp = book_dir / 'source.pdf.part'
                await download.save_as(str(temp))
                pages = check_pdf(temp)
                if info['expected_pages'] and pages != info['expected_pages']:
                    raise ValueError('下载PDF页数与目录声明不一致')
                temp.replace(source)
                info.update(pages=pages, sha256=sha256(source), status='complete')
                write_json(state_path, info)
                output.append(str(book_dir))
                print(f"已保存{info['volume']}：{pages}页，ISBN={info['isbn'] or '源文件名缺失'}", flush=True)
            write_json(work / 'books.json', output)
        finally:
            await context.close()
    return output


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--subject')
    p.add_argument('--grade')
    p.add_argument('--stage', default='小学')
    p.add_argument('--version', default='', help='存在多个版本时交互选择；可指定统编版等名称')
    p.add_argument('--volume', default='全部', choices=['全部', '上册', '下册'])
    p.add_argument('--work-dir', type=Path, default=DEFAULT_WORK)
    p.add_argument('--login-timeout', type=int, default=900)
    p.add_argument('--year', default='', help='目录年度，如 2025年度；同版同册多条时必须明确')
    p.add_argument('--browser-profile', type=Path, help='复用已登录的独立 Chrome 配置目录')
    p.add_argument('--cookies-file', type=Path, help='仅用户可读的 Cookie JSON；只注入 basic.smartedu.cn')
    return p


def main():
    args = parser().parse_args()
    args.subject = args.subject or input('学科：').strip()
    args.grade = args.grade or input('年级（如一年级）：').strip()
    books = select_resources(args.subject, args.grade, args.version, args.volume, args.stage, args.year)
    asyncio.run(download_books(args, books))


if __name__ == '__main__':
    main()
