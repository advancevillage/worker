#!/usr/bin/env python3
"""One visible browser, one tab per image, configurable serial TinyPNG upload/download rounds."""
import argparse
import asyncio
import fcntl
import html
import json
import os
import re
import shutil
import time
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
from pathlib import Path

from common import DEFAULT_WORK, read_json, sha256, write_json

DEFAULT_ROUNDS = 2
LEGACY_ROUNDS = 5


def target_rounds(state):
    value = state.get("target_rounds", LEGACY_ROUNDS)
    if type(value) is not int or value < 1:
        raise ValueError("Invalid target rounds")
    return value
DOWNLOAD_SELECTOR = 'a[href*="/backend/opt/download/"]'


def stamp():
    return datetime.now(timezone.utc).isoformat()


def image_info(path):
    from PIL import Image
    path = Path(path)
    with Image.open(path) as image:
        image.load()
        if image.format not in ('JPEG','PNG') or min(image.size) < 1:
            raise ValueError('Expected a decodable PNG/JPEG')
        width, height = image.size
    return dict(sha256=sha256(path), bytes=path.stat().st_size, width=width, height=height)


def discover(books):
    tasks = []
    seen = set()
    for book in books:
        book = Path(book).resolve()
        receipt = read_json(book / 'archive.json')
        target = Path(receipt['target'])
        for row in receipt['files']:
            relative = Path(row['file'])
            if relative.is_absolute() or relative.parent != Path('image'):
                raise ValueError('Unsafe archive image path')
            name = Path(row['file']).name
            if re.fullmatch(r'(封面-\d+|[1-9]\d*)\.(?:jpg|png)', name):
                image_path = target / row['file']
                if image_path.is_symlink() or not image_path.resolve().is_relative_to(target.resolve()):
                    raise ValueError('Image escapes book output directory')
                if str(image_path.resolve()) in seen:
                    raise ValueError('Duplicate image in input books')
                seen.add(str(image_path.resolve()))
                tasks.append(dict(book=book, target=target / row['file'], file=row['file'],
                                  expected_sha256=row['sha256'], resource_id=receipt['resource_id']))
    tasks.sort(key=lambda t: (str(t['book']), not t['target'].name.startswith('封面-'),
                              int(t['target'].stem) if t['target'].stem.isdigit() else 0, t['file']))
    return tasks


def extension(state):
    return Path(state["target"]).suffix.lower()


def prepare(task, rounds=None):
    if rounds is not None and (type(rounds) is not int or rounds < 1):
        raise ValueError("Invalid target rounds")
    suffix = task["target"].suffix.lower()
    folder = task['book'] / 'compression' / task['target'].name
    folder.mkdir(parents=True, exist_ok=True)
    manifest = folder / 'state.json'
    journal = folder / 'round-pending.json'
    if journal.exists():
        recover_round(folder)
    current = image_info(task['target'])
    if manifest.exists():
        state = read_json(manifest)
        if state['target'] != str(task['target']) or state['resource_id'] != task['resource_id']:
            raise ValueError('Compression state belongs to another image')
        goal = target_rounds(state)
        if rounds is not None and rounds != goal:
            raise ValueError('Existing task has another target; use --action set-rounds explicitly')
        previous = state['original']
        if image_info(folder / f'original{suffix}') != previous:
            raise ValueError('Original backup is damaged')
        for i, row in enumerate(state['rounds'], 1):
            if row.get('method') != 'website_upload_download' or row['round'] != i or row['input_sha256'] != previous['sha256']:
                raise ValueError('Broken compression round chain')
            info = image_info(folder / f'round-{i:02d}{suffix}')
            if info != row['output'] or (info['width'], info['height']) != (previous['width'], previous['height']):
                raise ValueError('Round checksum or dimensions changed')
            previous = info
        allowed = {state['original']['sha256']}
        allowed.update(row['output']['sha256'] for row in state['rounds'])
        if current['sha256'] not in allowed:
            raise ValueError('Output was modified outside this compression task')
        selected = state['rounds'][goal-1]['output'] if len(state['rounds']) >= goal else None
        if selected and (current['sha256'] != selected['sha256']
                         or task['expected_sha256'] != selected['sha256']):
            state['status'] = 'ready'  # A restored original or interrupted receipt needs republication.
            write_json(manifest, state)
    else:
        if current['sha256'] != task['expected_sha256']:
            raise ValueError('Output differs from archive receipt')
        if current['bytes'] > 5_000_000:
            raise ValueError('Image exceeds the website 5 MB limit')
        backup = folder / f'original{suffix}'
        if backup.exists() and sha256(backup) != current['sha256']:
            raise ValueError('Existing original backup conflicts')
        if not backup.exists():
            temp = folder / f'original{suffix}.part'
            shutil.copyfile(task['target'], temp)
            os.replace(temp, backup)
        state = dict(resource_id=task['resource_id'], target=str(task['target']),
                     service='https://tinypng.com/', original=current, rounds=[],
                     target_rounds=rounds if rounds is not None else DEFAULT_ROUNDS,
                     status='pending', created_at=stamp())
        write_json(manifest, state)
    return folder, state


def record_round(folder, state, number, path):
    suffix = extension(state)
    if number != len(state['rounds']) + 1 or number > target_rounds(state):
        raise ValueError('Out-of-order round')
    previous = state['rounds'][-1]['output'] if state['rounds'] else state['original']
    result = image_info(path)
    from PIL import Image
    with Image.open(path) as im:
        if im.format != ('PNG' if suffix=='.png' else 'JPEG'):
            raise ValueError('Compression changed image format')
    if (result['width'], result['height']) != (state['original']['width'], state['original']['height']):
        raise ValueError('TinyPNG changed pixel dimensions')
    final = folder / f'round-{number:02d}{suffix}'
    record = dict(round=number, input_sha256=previous['sha256'], output=result,
                  completed_at=stamp(), method='website_upload_download')
    write_json(folder / 'round-pending.json', dict(record=record, temp=path.name))
    os.replace(path, final)
    state['rounds'].append(record)
    state['status'] = 'ready' if number == target_rounds(state) else 'running'
    state.pop('error', None)
    write_json(folder / 'state.json', state)
    (folder / 'round-pending.json').unlink()


def recover_round(folder):
    journal = read_json(folder / 'round-pending.json')
    record = journal['record']
    number = record['round']
    state = read_json(folder / 'state.json')
    if type(number) is not int or not 1 <= number <= target_rounds(state):
        raise ValueError('Invalid pending round')
    suffix = extension(state)
    final = folder / f'round-{number:02d}{suffix}'
    temp = folder / journal['temp']
    if Path(journal['temp']).name != journal['temp']:
        raise ValueError('Unsafe pending round path')
    previous = state['original'] if number == 1 else state['rounds'][number - 2]['output']
    if record['input_sha256'] != previous['sha256']:
        raise ValueError('Pending round input mismatch')
    if not final.exists():
        if not temp.exists() or image_info(temp) != record['output']:
            raise ValueError('Pending round payload missing/corrupt')
        os.replace(temp, final)
    if image_info(final) != record['output']:
        raise ValueError('Pending round checksum mismatch')
    if len(state['rounds']) == number - 1:
        state['rounds'].append(record)
        state['status'] = 'ready' if number == target_rounds(state) else 'paused'
        write_json(folder / 'state.json', state)
    elif len(state['rounds']) != number or state['rounds'][-1] != record:
        raise ValueError('Pending round state conflict')
    (folder / 'round-pending.json').unlink()


def publish(task, folder, state):
    suffix = extension(state)
    goal = target_rounds(state)
    if len(state['rounds']) < goal:
        raise ValueError(f'{goal} completed rounds are required')
    final = state['rounds'][goal-1]['output']
    if image_info(folder / f'round-{goal:02d}{suffix}') != final:
        raise ValueError('Final compression result is damaged')
    current = sha256(task['target'])
    allowed = {state['original']['sha256'], *(r['output']['sha256'] for r in state['rounds'])}
    if current not in allowed:
        raise ValueError('Target changed before publication')
    receipt_path = task['book'] / 'archive.json'
    receipt = read_json(receipt_path)
    row = next(r for r in receipt['files'] if r['file'] == task['file'])
    if row['sha256'] not in allowed:
        raise ValueError('Archive identity conflict')
    if (state['status'] == 'complete' and current == final['sha256']
            and row.get('sha256') == final['sha256'] and row.get('compression_rounds') == goal and row.get('compression_target_rounds') == goal):
        return
    if current != final['sha256']:
        temp = task['target'].with_name(task['target'].name+'.compress-part')
        shutil.copyfile(folder / f'round-{goal:02d}{suffix}', temp)
        os.replace(temp, task['target'])
    # All callers run on one event loop; no await inside this read/modify/write.
    row.update(sha256=final['sha256'], original_sha256=state['original']['sha256'],
               compression_rounds=goal, compression_target_rounds=goal, compression_service='tinypng.com')
    write_json(receipt_path, receipt)
    state['status'] = 'complete'
    state['published_at'] = stamp()
    write_json(folder / 'state.json', state)


class WebsitePaused(Exception):
    pass


@contextmanager
def instance_lock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('已有压缩进程占用此工作目录，请使用 --action status/pause/resume') from None
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def select_tasks(tasks, sample=False, names=None):
    if names:
        tasks = [t for t in tasks if t['target'].name in names]
    if sample:
        covers = [t for t in tasks if t['target'].name.startswith('封面-')]
        body = [t for t in tasks if t['target'].stem.isdigit()]
        if not covers or not body:
            raise ValueError('试跑需要至少一张封面及一张正文')
        tasks = [covers[0], body[0]]
    if not tasks:
        raise ValueError('No matching cover/body images')
    return tasks


async def compress_round(page, source, target, timeout, pending=None):
    """Resume a submitted upload in the same tab without submitting it twice."""
    from urllib.parse import urlsplit, unquote
    pending = pending if pending is not None else {}
    if 'source_sha256' not in pending:
        pending.pop('network_error', None)
        pending.update(source_sha256=sha256(source),
                       before=await page.locator(DOWNLOAD_SELECTOR).evaluate_all('(els)=>els.map(e=>e.href)'),
                       submitted=False)
    if pending['source_sha256'] != sha256(source):
        raise ValueError('Input changed while a website operation is pending')
    if pending.get('network_error'):
        raise WebsitePaused(pending['network_error'])
    if not pending['submitted']:
        # DOMContentLoaded can precede hydration: selecting into an inert input silently loses the file.
        await page.wait_for_load_state('networkidle', timeout=30000)
        try:
            async with page.expect_request(
                    lambda request: request.method == 'POST' and 'tinypng.com/backend/' in request.url,
                    timeout=min(30000, timeout*1000)):
                await page.locator('input[type=file]').set_input_files(str(source))
            pending['submitted'] = True
            print(f'UPLOAD_STARTED {source.name}', flush=True)
        except Exception as error:
            raise WebsitePaused('未观察到上传请求，不能计为已上传；请检查页面初始化及上传控件') from error
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        links = page.locator(DOWNLOAD_SELECTOR)
        hrefs = await links.evaluate_all('(els)=>els.map(e=>e.href)')
        fresh = [i for i, href in enumerate(hrefs) if href not in pending['before']
                 and urlsplit(href).hostname == 'tinypng.com'
                 and unquote(urlsplit(href).path).endswith('/' + source.name)]
        if len(fresh) == 1:
            async with page.expect_download(timeout=90000) as event:
                await links.nth(fresh[0]).click()
            download = await event.value
            await download.save_as(str(target))
            return
        if len(fresh) > 1:
            raise WebsitePaused('多个下载结果匹配同一输入，请检查原tab')
        if pending.get('network_error'):
            raise WebsitePaused(pending['network_error'])
        errors = page.locator('[role=alert], .image-card__error, .error-message')
        for element in await errors.all():
            if await element.is_visible():
                text = (await element.inner_text()).strip()
                if text:
                    raise WebsitePaused('网站提示：' + text[:250])
        await asyncio.sleep(.5)
    raise WebsitePaused('等待网页结果超时；保留原tab，可处理验证后resume，不自动重新上传')


class CompressionRunner:
    """Bounded queue, preserved tabs, and all actions in a single browser context."""
    def __init__(self, args, books, context, round_function=compress_round):
        self.args, self.books, self.context = args, books, context
        self.work = args.work_dir.expanduser().resolve()
        self.control = self.work / 'compression-control'
        self.control.mkdir(exist_ok=True)
        self.status_path = self.work / 'compression-run.json'
        self.round_function = round_function
        self.pages, self.inflight, self.states = {}, {}, []
        self.paused = (self.control / 'pause').exists()
        self.closing = False
        self.active = set()
        self.started = stamp()
        self.errors = []
        self.summary_page = None
        self.closed = False
        self.context.on('close', self.browser_closed)
        self.load_tasks()

    def browser_closed(self, *_):
        self.closed = self.closing = self.paused = True

    def load_tasks(self):
        tasks = select_tasks(discover(self.books), self.args.sample, self.args.files)
        self.states = [(t, *prepare(t, getattr(self.args, 'rounds', None))) for t in tasks]

    def update(self, status=None):
        complete = sum(s['status'] == 'complete' for _, _, s in self.states)
        if status is None:
            status = ('complete' if complete == len(self.states) else
                      'paused' if self.paused else 'running')
        result = dict(status=status, pid=os.getpid(), total=len(self.states), complete=complete,
                      rounds_completed=sum(len(s['rounds']) for _, _, s in self.states),
                      selected_rounds_completed=sum(min(len(s['rounds']),target_rounds(s)) for _, _, s in self.states),
                      target_rounds=sorted({target_rounds(s) for _, _, s in self.states}),
                      sample=self.args.sample, tabs=self.args.tabs, active_tabs=len(self.pages),
                      active_files=sorted(self.active), errors=self.errors,
                      started_at=self.started, updated_at=stamp(),
                      original_bytes=sum(s['original']['bytes'] for _, _, s in self.states),
                      final_bytes=sum(s['rounds'][target_rounds(s)-1]['output']['bytes'] if s['status'] == 'complete'
                                      else s['original']['bytes'] for _, _, s in self.states))
        write_json(self.status_path, result)
        return result

    async def summary(self):
        result = self.update()
        if self.summary_page and not self.summary_page.is_closed():
            await self.summary_page.set_content(
                '<meta charset="utf-8"><title>TinyPNG 压缩进度</title>'
                f'<h1>TinyPNG 压缩（目标轮数：{result["target_rounds"]}）</h1>'
                f'<p>{html.escape(result["status"])}：{result["complete"]}/{result["total"]}张；'
                f'目标内已完成{result["selected_rounds_completed"]}轮；历史累计{result["rounds_completed"]}轮</p>'
                '<p>命令行 --action pause / resume / continue-full / status / close 管理此窗口。'
                '限额和验证需在原tab处理，不通过新tab绕过。</p>')
        return result

    async def action(self, action):
        if action == 'pause':
            self.paused = True
            (self.control / 'pause').touch()
        elif action == 'close':
            self.closing = self.paused = True
            (self.control / 'pause').touch()
        elif action in ('resume', 'continue-full'):
            if self.active:
                raise ValueError('当前轮次尚未收尾，请等status显示active_files为空后恢复')
            if action == 'continue-full':
                if not self.args.sample:
                    raise ValueError('当前不是试跑任务')
                if any(len(s['rounds']) < target_rounds(s) for _, _, s in self.states):
                    raise ValueError('试跑尚未完成目标轮数，不能开始全量')
                self.args.sample = False
            # Revalidate cached outputs before resuming; existing page objects are retained.
            self.load_tasks()
            for pending in self.inflight.values():
                if pending.get('network_error'):
                    pending.clear()  # Explicit resume retries a confirmed failed HTTP operation.
            self.paused = False
            (self.control / 'pause').unlink(missing_ok=True)
            self.errors = []
        else:
            raise ValueError(f'Unknown action: {action}')
        self.update()

    async def get_page(self, key):
        page = self.pages.get(key)
        if page and page.is_closed():
            self.pages.pop(key)
            self.inflight.pop(key, None)
            raise WebsitePaused('图片tab已被关闭；再次显式resume后才能创建替代tab')
        if not page:
            if len(self.pages) >= self.args.tabs:
                raise ValueError('Active image tab limit exceeded')
            page = await self.context.new_page()
            self.pages[key] = page
            self.inflight[key] = {}
            def response_seen(response):
                if (key in self.inflight and 'tinypng.com/backend/opt/' in response.url and response.request.method == 'POST'
                        and response.status in (401, 403, 429, 500, 502, 503)):
                    self.inflight[key]['network_error'] = f'网站返回HTTP {response.status}，需在原tab检查'
            page.on('response', response_seen)
            await page.goto('https://tinypng.com/', wait_until='load', timeout=60000)
        return page

    async def process(self, task, folder, state):
        key = str(task['target'])
        if self.paused or self.closing:
            return
        self.active.add(key)
        page = None
        try:
            if len(state['rounds']) >= target_rounds(state):
                publish(task, folder, state)
                return
            page = await self.get_page(key)
            for number in range(len(state['rounds']) + 1, target_rounds(state) + 1):
                if self.paused or self.closing:
                    state['status'] = 'paused'
                    write_json(folder / 'state.json', state)
                    return
                suffix = extension(state)
                source = folder / (f'original{suffix}' if number == 1 else f'round-{number-1:02d}{suffix}')
                expected = state['original'] if number == 1 else state['rounds'][-1]['output']
                if image_info(source) != expected:
                    raise ValueError('Round input checksum/dimensions changed')
                state['status'] = 'running'
                write_json(folder / 'state.json', state)
                temp = folder / f'round-{number:02d}{suffix}.part'
                pending = self.inflight[key]
                await self.round_function(page, source, temp, self.args.timeout, pending)
                record_round(folder, state, number, temp)
                pending.clear()
                self.update()
                print(f"{task['target'].parent.parent.name}/{task['target'].name}: {number}/{target_rounds(state)}; "
                      f"{state['rounds'][-1]['output']['bytes']} bytes", flush=True)
            publish(task, folder, state)
            await page.close()
            self.pages.pop(key, None)
            self.inflight.pop(key, None)
            print(f'COMPLETE {task["target"].name}', flush=True)
        except Exception as error:
            self.paused = True
            (self.control / 'pause').touch()
            state['status'] = 'paused'
            state['error'] = f'{type(error).__name__}: {str(error)[:350]}'
            write_json(folder / 'state.json', state)
            self.errors.append(dict(file=key, error=state['error']))
            if page and not page.is_closed():
                try:
                    await page.screenshot(path=str(folder / 'paused.png'))
                except Exception:
                    pass
            print(f'PAUSED {task["target"].name}: {state["error"]}', flush=True)
        finally:
            self.active.discard(key)
            self.update()

    async def batch(self):
        # Retained tabs get priority so a resume cannot exceed the tab limit.
        entries = sorted(self.states, key=lambda entry: str(entry[0]['target']) not in self.pages)
        queue = asyncio.Queue()
        for entry in entries:
            if entry[2]['status'] != 'complete':
                queue.put_nowait(entry)
        async def consumer():
            while not self.paused and not self.closing:
                try:
                    entry = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                await self.process(*entry)
                queue.task_done()
        await asyncio.gather(*(consumer() for _ in range(self.args.tabs)))
        return await self.summary()

    async def loop(self):
        self.summary_page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        await self.summary_page.goto('about:blank')
        wave = None
        last_summary = 0
        while not self.closing:
            if (self.control / 'close').exists():
                await self.action('close')
                (self.control / 'close').unlink(missing_ok=True)
            if (self.control / 'pause').exists() and not self.paused:
                await self.action('pause')
            for command in sorted(self.control.glob('command-*.json')):
                try:
                    await self.action(read_json(command)['action'])
                    print(f'CONTROL accepted {command.name}', flush=True)
                except Exception as error:
                    print(f'CONTROL rejected: {error}', flush=True)
                finally:
                    command.unlink(missing_ok=True)
            if wave and wave.done():
                await wave
                wave = None
                result = await self.summary()
                print('RUN_RESULT ' + json.dumps(result, ensure_ascii=False), flush=True)
                if self.args.close_when_done:
                    self.closing = True
            if (not wave and not self.paused and not self.closing
                    and any(s['status'] != 'complete' for _, _, s in self.states)):
                wave = asyncio.create_task(self.batch())
            if time.monotonic() - last_summary > 5:
                await self.summary()
                last_summary = time.monotonic()
            if self.args.close_when_done and not wave and all(s['status'] == 'complete' for _, _, s in self.states):
                self.closing = True
            await asyncio.sleep(.3)
        if wave:
            await wave  # Finish/checkpoint in-flight round, but don't start another upload.
        self.update('complete' if all(s['status'] == 'complete' for _, _, s in self.states) else 'paused')
        return 0 if all(s['status'] == 'complete' for _, _, s in self.states) else 2


def send_action(work, action):
    work = Path(work).expanduser().resolve()
    status = work / 'compression-run.json'
    if action == 'status':
        result = read_json(status) if status.exists() else {'status': 'not_started'}
        try:
            with instance_lock(work / 'compression.lock'):
                result['controller_running'] = False
        except RuntimeError:
            result['controller_running'] = True
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    control = work / 'compression-control'
    control.mkdir(parents=True, exist_ok=True)
    if action == 'pause':
        (control / 'pause').touch()
        print('暂停已请求：当前轮次完成校验后停止，不启动新上传。')
        return
    if action == 'close':
        (control / 'close').touch()
        print('关闭已请求：当前轮次收尾后关闭浏览器。')
        return
    try:
        with instance_lock(work / 'compression.lock'):
            running = False
    except RuntimeError:
        running = True
    if not running:
        # Explicit resume clears the persistent pause. The caller can then run normally.
        if action == 'resume':
            (control / 'pause').unlink(missing_ok=True)
            (control / 'close').unlink(missing_ok=True)
            print('无运行中的浏览器，暂停标记已解除；再次运行压缩命令可从缓存恢复。')
            return
        raise ValueError('continue-full需要仍在运行的试跑浏览器')
    write_json(control / f'command-{time.time_ns()}.json', dict(action=action))
    print(f'已发送{action}，由原浏览器进程执行。')


async def run(args):
    from playwright.async_api import async_playwright
    work = args.work_dir.expanduser().resolve()
    work.mkdir(parents=True, exist_ok=True)
    books = [str(args.book_dir)] if args.book_dir else read_json(work / 'books.json')
    with ExitStack() as locks:
        locks.enter_context(instance_lock(work / 'compression.lock'))
        for book in sorted(set(str(Path(b).resolve()) for b in books)):
            locks.enter_context(instance_lock(Path(book) / 'compression.lock'))
        async with async_playwright() as pw:
            profile = work / 'tinypng-profile'
            profile.mkdir(exist_ok=True, mode=0o700)
            context = await pw.chromium.launch_persistent_context(str(profile), channel='chrome',
                      headless=False, accept_downloads=True, viewport={'width': 1400, 'height': 1000})
            try:
                runner = CompressionRunner(args, books, context)
                return await runner.loop()
            finally:
                await context.close()


def set_rounds(work, books, rounds, names=None):
    """Explicit offline migration; preserve history and the persistent pause marker."""
    if type(rounds) is not int or rounds < 1:
        raise ValueError('set-rounds requires a positive --rounds')
    work = Path(work).resolve()
    with ExitStack() as locks:
        locks.enter_context(instance_lock(work / 'compression.lock'))
        for book in sorted(set(str(Path(b).resolve()) for b in books)):
            locks.enter_context(instance_lock(Path(book) / 'compression.lock'))
        tasks = select_tasks(discover(books), False, names)
        # Validate all existing chains before the first migration mutation.
        states = [(task, *prepare(task)) for task in tasks]
        backup = work / 'round-migrations' / str(time.time_ns())
        for index, (task, folder, state) in enumerate(states):
            dest = backup / str(index)
            dest.mkdir(parents=True)
            for source in [folder / 'state.json', task['book'] / 'archive.json', task['target']]:
                shutil.copy2(source, dest / source.name)
            old = target_rounds(state)
            state.setdefault('migrations', []).append(dict(at=stamp(), from_rounds=old,
                to_rounds=rounds, history_rounds=len(state['rounds']), backup=str(dest)))
            state['target_rounds'] = rounds
            state['status'] = 'ready' if len(state['rounds']) >= rounds else 'paused'
            write_json(folder / 'state.json', state)
            if len(state['rounds']) >= rounds:
                publish(task, folder, state)
            else:
                receipt_path = task['book'] / 'archive.json'
                receipt = read_json(receipt_path)
                row = next(r for r in receipt['files'] if r['file'] == task['file'])
                row['compression_target_rounds'] = rounds
                write_json(receipt_path, receipt)
        result = dict(status='migrated', target_rounds=rounds, backup=str(backup),
            pages=[dict(file=t['file'], history_rounds=len(s['rounds']),
                        selected_round=rounds if s['status']=='complete' else None,
                        remaining=max(0, rounds-len(s['rounds']))) for t, _, s in states])
        write_json(backup / 'migration.json', result)
        print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work-dir', type=Path, default=DEFAULT_WORK)
    p.add_argument('--book-dir', type=Path)
    p.add_argument('--rounds', type=int, help='New tasks default to 2; existing tasks retain their stored target')
    p.add_argument('--tabs', type=int, default=3)
    p.add_argument('--timeout', type=int, default=180)
    p.add_argument('--sample', action='store_true', help='One cover and one body image')
    p.add_argument('--files', nargs='+')
    p.add_argument('--action', choices=['run', 'status', 'pause', 'resume', 'continue-full', 'close', 'set-rounds'], default='run')
    p.add_argument('--close-when-done', action='store_true')
    args = p.parse_args()
    if not 1 <= args.tabs <= 5 or args.timeout < 1:
        p.error('--tabs must be 1..5 and --timeout must be positive')
    if args.rounds is not None and args.rounds < 1:
        p.error('--rounds must be positive')
    if args.action == 'set-rounds':
        books = [str(args.book_dir)] if args.book_dir else read_json(args.work_dir / 'books.json')
        set_rounds(args.work_dir, books, args.rounds, args.files)
        return 0
    if args.action != 'run':
        send_action(args.work_dir, args.action)
        return 0
    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        return 130


if __name__ == '__main__':
    raise SystemExit(main())
