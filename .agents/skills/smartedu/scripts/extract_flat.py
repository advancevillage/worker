#!/usr/bin/env python3
"""Extract flat areas from hash-bound reviewed input; queue uncertain OCR for tell-me."""
import argparse
import json
import shutil
import subprocess
from pathlib import Path
from common import sha256, write_json
from identify_pages import compile_ocr
from readalong import TellMe, from_review, image_pid, read, resolve, tell_me, asset_name, image_info, validate_assets


def extract(image,output,work,review=None,printed_page=None):
    image,output,work=map(Path,(image,output,work));pid=image_pid(image)
    work.mkdir(parents=True,exist_ok=True)
    try:
        if review is None or not Path(review).exists():
            cache=work/'ocr'/f'{pid}.json'
            if not cache.exists():
                binary=compile_ocr(work)
                result=subprocess.run([str(binary),str(image.resolve())],check=True,capture_output=True,text=True)
                write_json(cache,dict(image_sha256=sha256(image),words=json.loads(result.stdout)))
            raise TellMe(f'Confirm text, language and image boundaries using OCR draft: {cache}')
        page=from_review(image,read(review),printed_page)
        for area in page['areas']:
            for asset in area['edurich']['assets'].values():
                name=asset_name(asset)
                if name==pid:continue
                source=Path(review).parent/'image'/name
                if image_pid(source)!=name or image_info(source)!=(asset['width'],asset['height']):
                    raise ValueError('Reviewed image asset mismatch')
                dest=output/'image'/name;dest.parent.mkdir(parents=True,exist_ok=True)
                if dest.exists() and dest.read_bytes()!=source.read_bytes():raise ValueError('Image asset collision')
                if source.resolve()!=dest.resolve():shutil.copyfile(source,dest)
        validate_assets(output,page)
        write_json(output/'content'/'edurich'/f'{pid}.json',page)
        resolve(work,pid)
        return page
    except (ValueError,KeyError,TypeError,OSError,subprocess.SubprocessError) as e:
        tell_me(work,pid,e,image)
        return None


def main():
    p=argparse.ArgumentParser();p.add_argument('--image',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--work-dir',type=Path,required=True)
    p.add_argument('--review',type=Path);p.add_argument('--printed-page')
    a=p.parse_args();return 0 if extract(a.image,a.output,a.work_dir,a.review,a.printed_page) else 2

if __name__=='__main__':raise SystemExit(main())
