#!/usr/bin/env python3
"""Build MD5 images and a candidate index; publish book.json only after validation."""
import argparse
import shutil
from pathlib import Path
from common import sha256, write_json
from readalong import CATEGORIES, TellMe, image_info, image_pid, read, resolve, tell_me


def build(book_dir, output, work, names=None):
    book_dir,output,work=map(Path,(book_dir,output,work))
    receipt=read(book_dir/'archive.json');mapping=read(book_dir/'mapping.json')
    source=Path(receipt['target'])
    if output.resolve()==source.resolve():raise ValueError('Use a separate staged output; active compression archive must be preserved')
    index={v:({} if v=='body' else []) for v in CATEGORIES.values()}
    records={r['physical_page']:r for r in receipt['files']}
    if len(records)!=len(receipt['files']) or len(records)!=len(mapping['pages']):raise ValueError('Archive/map count mismatch')
    selected=set(names or []);found=set();jobs=[];errors=[]
    for row in mapping['pages']:
        record=records[row['physical_page']];image=(source/record['file']).resolve()
        if not image.is_relative_to(source.resolve()):raise ValueError('Unsafe archive path')
        if selected and image.name not in selected:continue
        found.add(image.name)
        try:
            if row.get('issues'):
                raise TellMe(f'Unresolved mapping issues: {row["issues"]}')
            category=CATEGORIES.get(row['category'])
            if not category:raise TellMe(f'Confirm category {row["category"]!r}; allowed: {list(CATEGORIES.values())}')
            if sha256(image)!=record['sha256']:raise TellMe('Archived image changed; reconcile compression receipt')
            image_info(image);pid=image_pid(image)
            if category in ('cover','body'):
                goal = record.get('compression_target_rounds', 5)
                if type(goal) is not int or goal < 1 or record.get('compression_rounds') != goal:
                    raise TellMe('Target TinyPNG rounds not complete; finish compression before assigning final pid')
                if 'compression_target_rounds' in record:
                    from compress_images import prepare, target_rounds
                    task = dict(book=book_dir, target=image, file=record['file'],
                                resource_id=receipt['resource_id'], expected_sha256=record['sha256'])
                    _, state = prepare(task)
                    if (target_rounds(state) != goal or len(state['rounds']) < goal
                            or state['rounds'][goal-1]['output']['sha256'] != record['sha256']):
                        raise TellMe('Compression receipt does not match verified round output')
            page=None
            if category=='body':
                n=row.get('printed_page')
                if type(n) is not int or n<=0:raise TellMe('Confirm printed textbook page number')
                page=str(n)
                if page in index['body']:raise TellMe(f'Duplicate printed page {page}')
                index['body'][page]=pid
            else:index[category].append(pid)
            target=output/'image'/pid;target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists() and target.read_bytes()!=image.read_bytes():raise ValueError('MD5 collision: refusing overwrite')
            if not target.exists():shutil.copyfile(image,target)
            jobs.append(dict(pid=pid,source=str(image),name=image.name,category=category,printed_page=page))
            resolve(work,image.name)
        except (ValueError,KeyError,OSError) as e:
            tell_me(work,image.name,e,image);errors.append(image.name)
    if selected-found:raise ValueError(f'Unknown selected images: {selected-found}')
    if not jobs:raise ValueError('No processable images')
    meta=read(source/'meta.json')
    if set(meta)!={'isbn','subject','volume','publisher'}:raise ValueError('Expected four-field metadata')
    output.mkdir(parents=True,exist_ok=True);write_json(output/'meta.json',meta)
    # A partial sample must not masquerade as a whole textbook/PDF export.
    if not selected and not errors:shutil.copyfile(source/'教材.pdf',output/'教材.pdf')
    write_json(work/'candidate-book.json',index)
    write_json(work/'jobs.json',jobs)
    write_json(work/'build.json',dict(sample=bool(selected),errors=errors,output=str(output.resolve()),expected=len(mapping['pages']) if not selected else len(selected)))
    return 2 if errors else 0


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--book-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--work-dir',type=Path,required=True);p.add_argument('--images',nargs='+')
    a=p.parse_args();return build(a.book_dir,a.output,a.work_dir,a.images)

if __name__=='__main__':raise SystemExit(main())
