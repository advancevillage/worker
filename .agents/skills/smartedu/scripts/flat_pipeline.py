#!/usr/bin/env python3
"""Build a separate flat export. Samples are explicitly selected; incomplete books stay staged."""
import argparse
import os
import tempfile
import time
from pathlib import Path
from common import write_json
from build_book_index import build
from extract_flat import extract
from readalong import read, tell_me
from preview_content import render
from validate_book import validate


def recover(work):
    work=Path(work);journal=work/'publish-pending.json'
    if not journal.exists():return
    state=read(journal);stage=Path(state['stage']);output=Path(state['output']);backup=Path(state['backup'])
    if not output.exists() and backup.exists():
        os.rename(backup,output)
    elif output.exists() and not stage.exists():
        write_json(work/'publish.json',dict(output=str(output),backup=str(backup) if backup.exists() else None))
    elif output.exists() and stage.exists() and backup.exists():
        raise ValueError('Ambiguous publication recovery; tell-me before changing files')
    journal.unlink()


def publish(stage, output, work):
    stage,output,work=map(Path,(stage,output,work))
    output.parent.mkdir(parents=True,exist_ok=True)
    backup=work/'backups'/str(time.time_ns())
    backup.parent.mkdir(parents=True,exist_ok=True)
    journal=work/'publish-pending.json'
    write_json(journal,dict(stage=str(stage),output=str(output),backup=str(backup)))
    moved=False
    if output.exists():
        os.rename(output,backup)
        moved=True
    try:
        os.rename(stage,output)
    except BaseException:
        if moved:os.rename(backup,output)
        raise
    write_json(work/'publish.json',dict(output=str(output),backup=str(backup) if moved else None))
    journal.unlink()


def run(book_dir,output,work,review_dir,images=None):
    output=Path(output).expanduser().resolve();work=Path(work).expanduser().resolve()
    source=Path(read(Path(book_dir)/'archive.json')['target']).resolve()
    if output==source or source.is_relative_to(output) or output.is_relative_to(source):
        raise ValueError('Flat output must be separate from active source archive')
    if work.is_relative_to(output) or output.is_relative_to(work):
        raise ValueError('Output and runtime work directory must not contain each other')
    work.mkdir(parents=True,exist_ok=True)
    recover(work)
    final=output
    output=Path(tempfile.mkdtemp(prefix='flat-stage-',dir=work))
    result=build(book_dir,output,work,images)
    jobs=read(Path(work)/'jobs.json');index=read(Path(work)/'candidate-book.json')
    for job in jobs:
        review=Path(review_dir)/(Path(job['name']).stem+'.review.json') if review_dir else None
        image=Path(output)/'image'/job['pid']
        page=extract(image,output,work,review,job['printed_page'])
        if page is None:result=2;continue
        render(output,page,index)
    if result:return result
    try:
        pids=validate(output,index)
        write_json(Path(output)/'content'/'book.json',index)
        write_json(Path(work)/'validation.json',dict(sample=bool(images),images=len(pids),valid=True))
        publish(output,final,work)
        output=final
        print(f'{"样本" if images else "整书"}完成：{output}，{len(pids)}张')
        return 0
    except (ValueError,OSError) as e:
        tell_me(work,'book',e);return 2

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--book-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--work-dir',type=Path,required=True);p.add_argument('--review-dir',type=Path);p.add_argument('--images',nargs='+')
    a=p.parse_args();raise SystemExit(run(a.book_dir,a.output,a.work_dir,a.review_dir,a.images))
