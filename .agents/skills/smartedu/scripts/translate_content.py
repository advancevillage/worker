#!/usr/bin/env python3
"""Apply explicitly reviewed bilingual EduRich content; no implicit translation provider."""
import argparse
from pathlib import Path
from common import write_json
from readalong import read, validate_page, tell_me


def main():
    p=argparse.ArgumentParser();p.add_argument('--page',type=Path,required=True)
    p.add_argument('--review',type=Path,required=True);p.add_argument('--work-dir',type=Path,required=True)
    a=p.parse_args();page=read(a.page);review=read(a.review)
    try:
        if review.get('pid')!=page['pid'] or review.get('reviewed') is not True:
            raise ValueError('Translation must be confirmed and bound to source pid')
        # Match by exact polygon AND exact original document, not an unstable list index.
        for entry in review['changes']:
            matches=[x for x in page['areas'] if x['polygon']==entry['polygon'] and x['edurich']==entry['source_edurich']]
            if len(matches)!=1:raise ValueError('Translation source changed or ambiguous')
            matches[0]['edurich']=entry['edurich']
        validate_page(page)
        write_json(a.page,page)
        return 0
    except ValueError as e:
        tell_me(a.work_dir,page['pid'],e);return 2

if __name__=='__main__':raise SystemExit(main())
