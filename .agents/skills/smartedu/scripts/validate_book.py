#!/usr/bin/env python3
"""Validate flat resources; publish a candidate index only if all references are complete."""
import argparse
import re
from pathlib import Path
from common import write_json
from readalong import CATEGORIES, PID, image_name, bilingual, image_info, read, validate_page, validate_assets
from preview_content import render


def validate(root,index,require_preview=True):
    root=Path(root)
    if set(index)!=set(CATEGORIES.values()):raise ValueError('Index must contain exactly eight categories')
    refs=[]
    for category,values in index.items():
        if category=='body':
            if not isinstance(values,dict) or any(not re.fullmatch('[1-9][0-9]*',n) for n in values):
                raise ValueError('body requires printed page -> pid mapping')
            pairs=values.items()
        else:
            if not isinstance(values,list):raise ValueError('Non-body category requires array')
            pairs=((None,pid) for pid in values)
        for page,pid in pairs:
            if not isinstance(pid,str) or not (PID.fullmatch(pid) or re.fullmatch('[0-9a-f]{32}',pid)):raise ValueError('Invalid indexed pid')
            refs.append((category,page,pid))
    if not refs:raise ValueError('Empty book')
    for category,printed,pid in refs:
        image=root/'image'/image_name(pid)
        page=validate_page(read(root/'content'/'edurich'/f'{pid}.json'),image,printed)
        validate_assets(root,page)
        if not page['areas'] and category!='blank':raise ValueError('Nonblank page has no content')
        if category=='blank' and page['areas']:raise ValueError('Blank page has content; confirm classification')
        english=any(bilingual(a['edurich']) for a in page['areas'])
        if english or 'trans' in page:
            if not page.get('trans') or image_info(root/'trans'/image_name(pid))!=(page['width'],page['height']):
                raise ValueError('English page requires translated image and translated areas')
        if require_preview and not (root/'content'/'preview'/f'{pid}.html').exists():raise ValueError('Missing preview')
    meta=read(root/'meta.json')
    if set(meta)!={'isbn','subject','volume','publisher'}:raise ValueError('Invalid meta fields')
    return sorted(set(pid for _,_,pid in refs))


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--candidate',type=Path)
    a=p.parse_args();index=read(a.candidate or a.root/'content'/'book.json')
    pids=validate(a.root,index,False)
    for pid in pids:render(a.root,read(a.root/'content'/'edurich'/f'{pid}.json'),index)
    validate(a.root,index)
    if a.candidate:write_json(a.root/'content'/'book.json',index)
    print(f'Validated {len(pids)} unique images')

if __name__=='__main__':main()
