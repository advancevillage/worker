"""Flat readalong protocol, strict validation and reviewed-input conversion."""
import copy
import hashlib
import json
import re
from pathlib import Path
from PIL import Image
from common import sha256, write_json
from extract_content import polygon_points, exclusion

VERSION = '0.1.0-draft'
CATEGORIES = {'封面':'cover','序言':'preface','目录':'content','正文':'body',
              '后记':'afterword','版权页':'copyright','封底':'back_cover','空白页':'blank'}
PID = re.compile(r'[0-9a-f]{32}\.(?:png|jpg)')


def read(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f'Duplicate JSON key: {key}')
            result[key] = value
        return result
    return json.loads(Path(path).read_text(), object_pairs_hook=unique,
                      parse_constant=lambda s: (_ for _ in ()).throw(ValueError(s)))


def md5(path):
    return hashlib.md5(Path(path).read_bytes(), usedforsecurity=False).hexdigest()


def image_pid(path):
    image_info(path)
    return md5(path)+Path(path).suffix.lower()


def image_name(pid):
    # Read legacy JPEG references, while all new output uses extension-bearing pid.
    if re.fullmatch('[0-9a-f]{32}',pid):return pid+'.jpg'
    if not (PID.fullmatch(pid) or re.fullmatch('[0-9a-f]{32}',pid)):raise ValueError('Invalid image pid')
    return pid


def media_type(pid):
    return 'image/png' if image_name(pid).endswith('.png') else 'image/jpeg'


def asset_name(asset):
    uri=asset.get('uri','')
    if not isinstance(uri,str) or not uri.startswith('asset:image/'):
        raise ValueError('Only controlled image assets allowed')
    name=uri[len('asset:image/'):]
    if not PID.fullmatch(name):raise ValueError('Invalid image asset reference')
    return name


def validate_assets(root,page):
    root=Path(root)
    for key in ('areas','trans'):
        for area in page.get(key,[]):
            for asset in area['edurich']['assets'].values():
                name=asset_name(asset);path=root/'image'/name
                if image_pid(path)!=name or image_info(path)!=(asset['width'],asset['height']):
                    raise ValueError('Image asset identity/dimensions mismatch')


def image_info(path):
    path = Path(path)
    if path.stat().st_size > 30_000_000:
        raise ValueError('Image exceeds 30MB')
    with Image.open(path) as im:
        if im.format not in ('JPEG','PNG') or im.width*im.height > 40_000_000 or im.getexif().get(274,1) != 1:
            raise ValueError('Requires orientation-normalized PNG/JPEG, <=40MP')
        if path.suffix.lower() not in ('.png','.jpg') or (im.format=='PNG') != (path.suffix.lower()=='.png'):
            raise ValueError('Image extension differs from actual format')
        im.load()
        return im.size


class TellMe(ValueError):
    pass


def tell_me(work, key, reason, image=None):
    path = Path(work)/'pending-confirmations.json'
    queue = read(path) if path.exists() else {}
    queue[key] = {'event':'tell-me','reason':str(reason),'image':str(image) if image else None}
    write_json(path, queue)
    print(f'tell-me [{key}]: {reason}', flush=True)


def resolve(work, key):
    path = Path(work)/'pending-confirmations.json'
    if path.exists():
        queue=read(path);queue.pop(key,None);write_json(path,queue)


def document(identity, language=None):
    return {'protocol':'edurich','version':VERSION,
            'modules':{'core':{'version':VERSION,'required':True}},
            'document':{'id':identity,'metadata':{'language':language} if language else {},
                        'profile':'reflow','body':[]},'assets':{},'styles':{}}


def paragraph(identity, text):
    return {'id':identity,'type':'core:paragraph','children':[
        {'id':identity+'-text','type':'core:text','value':text}]}


def add_module(doc, module):
    doc['modules'][module]={'version':VERSION,'required':True}


def text_blocks(doc):
    return [''.join(c.get('value',c.get('latex','')) for c in n.get('children',[]))
            for n in doc['document']['body'] if n['type'] in ('core:paragraph','core:heading')]


def bilingual(doc):
    # Contract: an English area has metadata.language=en, exactly source+Chinese paragraphs.
    return doc['document']['metadata'].get('language') == 'en'


def validate_doc(doc, pid, width, height):
    if set(doc) != {'protocol','version','modules','document','assets','styles'}:
        raise ValueError('Unexpected EduRich fields')
    if doc['protocol']!='edurich' or doc['version']!=VERSION or doc['styles']!={}:
        raise ValueError('Unsupported EduRich version/styles')
    if doc['modules'].get('core') != {'version':VERSION,'required':True}:
        raise ValueError('Missing core module')
    for mod, spec in doc['modules'].items():
        if mod not in ('core','math','media') or spec!={'version':VERSION,'required':True}:
            raise ValueError('Unsupported module')
    d=doc['document']
    if set(d)!={'id','metadata','profile','body'} or not isinstance(d['id'],str) or not d['id'] or d['profile']!='reflow':
        raise ValueError('Invalid document')
    if set(d['metadata'])-{'language'} or d['metadata'].get('language') not in (None,'zh','en'):
        raise ValueError('Language must be zh or en')
    if not isinstance(d['body'],list) or not 1<=len(d['body'])<=1000:
        raise ValueError('Area needs 1–1000 blocks')
    ids=set(); assets=set()
    def node(n, inline=False):
        if not isinstance(n.get('id'),str) or not n['id'] or n['id'] in ids:
            raise ValueError('Missing/duplicate node id')
        ids.add(n['id']);t=n.get('type')
        if len(ids)>2000:raise ValueError('Too many nodes')
        if inline and t=='core:text':
            if set(n)!={'id','type','value'} or not isinstance(n['value'],str) or not n['value']:
                raise ValueError('Invalid text')
        elif (inline and t=='math:inline') or (not inline and t=='math:block'):
            allowed={'id','type','latex','spoken'} | ({'align'} if not inline else set())
            if set(n)-allowed or not {'id','type','latex'}<=set(n) or 'math' not in doc['modules']:
                raise ValueError('Invalid math node')
            latex=n['latex']
            if not isinstance(latex,str) or not latex or len(latex)>2000 or '$' in latex or '<' in latex or '>' in latex:
                raise ValueError('Unsupported formula')
            commands=re.findall(r'\\([A-Za-z]+)',latex)
            if set(commands)-{'times','div','frac','sqrt','mathrm','text'} or latex.count('{')!=latex.count('}'):
                raise ValueError('Unsupported formula syntax; tell-me')
            if 'spoken' in n and not isinstance(n['spoken'],str):raise ValueError('Invalid spoken text')
            if n.get('align','center') not in ('start','center','end'):raise ValueError('Invalid align')
        elif not inline and t in ('core:paragraph','core:heading'):
            fields={'id','type','children'} | ({'level'} if t=='core:heading' else set())
            if set(n)!=fields or not isinstance(n['children'],list) or not n['children']:
                raise ValueError('Invalid paragraph/heading')
            if t=='core:heading' and (type(n['level']) is not int or not 1<=n['level']<=6):
                raise ValueError('Invalid heading level')
            for child in n['children']:node(child,True)
        elif not inline and t=='media:image':
            if set(n)!={'id','type','assetId','alt','decorative'} or 'media' not in doc['modules']:
                raise ValueError('Invalid media node')
            if not isinstance(n['alt'],str) or not n['alt'] or n['decorative'] is not False:
                raise ValueError('Image needs description')
            assets.add(n['assetId'])
        else:raise ValueError('Unsupported node type or position')
    for n in d['body']:node(n)
    if set(doc['assets'])!=assets:raise ValueError('Unresolved/unused asset')
    for a in doc['assets'].values():
        if set(a)!={'uri','mediaType','width','height'}:
            raise ValueError('Invalid asset fields')
        name=asset_name(a)
        if a['mediaType']!=media_type(name) or any(type(a[k]) is not int or a[k]<=0 for k in ('width','height')):
            raise ValueError('Invalid asset format/dimensions')
        if a['width']*a['height']>40_000_000:raise ValueError('Asset exceeds 40MP')
        if name==image_name(pid) and (a['width'],a['height'])!=(width,height):
            raise ValueError('Source asset dimensions differ from page')
    if bilingual(doc):
        blocks=text_blocks(doc)
        if len(d['body'])!=2 or len(blocks)!=2 or not re.search('[A-Za-z]',blocks[0]) or not re.search('[\u4e00-\u9fff]',blocks[1]):
            raise ValueError('English area requires source and Chinese translation paragraphs')


def validate_page(page, image=None, printed_page=None):
    if set(page)-{'pid','width','height','areas','trans'} or not {'pid','width','height','areas'}<=set(page):
        raise ValueError('Unexpected flat page fields')
    pid=page['pid'];w=page['width'];h=page['height']
    if not isinstance(pid,str) or not (PID.fullmatch(pid) or re.fullmatch('[0-9a-f]{32}',pid)):raise ValueError('Invalid pid')
    if any(type(n) is not int or n<=0 for n in (w,h)) or w*h>40_000_000:
        raise ValueError('Invalid dimensions')
    if image and (image_pid(image)!=image_name(pid) or image_info(image)!=(w,h)):
        raise ValueError('Source image identity mismatch')
    from region_conflicts import require_disjoint
    vertices=0
    for key in ('areas','trans'):
        if key not in page:continue
        if not isinstance(page[key],list) or len(page[key])>500:raise ValueError('Invalid area count')
        polygons=[]
        for area in page[key]:
            if set(area)!={'polygon','edurich'}:raise ValueError('Area must contain only polygon and edurich')
            points=polygon_points(area['polygon'],w,h);vertices+=len(points);polygons.append(points)
            validate_doc(area['edurich'],pid,w,h)
            for text in text_blocks(area['edurich']):
                if exclusion(dict(text=text,y0=min(y for x,y in points)/h,x0=min(x for x,y in points)/w,x1=max(x for x,y in points)/w),printed_page):
                    raise ValueError('Page number/watermark must not appear in content')
        require_disjoint(polygons,key)
    if vertices>20000:raise ValueError('Page exceeds 20000 vertices')
    if len(json.dumps(page,ensure_ascii=False).encode())>10_000_000:raise ValueError('Page exceeds 10MB')
    return page


def from_review(image, review, printed_page=None):
    """Migrate hash-bound reviewed input; unreviewed OCR never becomes a final artifact."""
    if review.get('image_sha256')!=sha256(image):raise TellMe('Review source image changed')
    w,h=image_info(image);pid=image_pid(image)
    if 'areas' in review:
        if review.get('reviewed') is not True:raise TellMe('Flat review must be explicitly reviewed')
        return validate_page(dict(pid=pid,width=w,height=h,areas=review['areas']),image,printed_page)
    areas=[]
    for i,r in enumerate(review.get('regions',[])):
        if r.get('reviewed') is not True:raise TellMe('Unreviewed text or boundary')
        doc=document(f'{pid}-{i}')
        if r['kind']=='text':
            lang={'zh-CN':'zh','zh-Latn-pinyin':'zh','zh-Latn':'zh','zh':'zh','en':'en'}.get(r.get('language'))
            if not lang:raise TellMe('Confirm text language: zh/en')
            doc['document']['metadata']={'language':lang}
            doc['document']['body']=[paragraph('source',r['text'])]
            if lang=='en':
                if not r.get('translation'):raise TellMe('English text needs confirmed Chinese translation')
                doc['document']['body'].append(paragraph('trans',r['translation']))
        elif r['kind']=='illustration':
            add_module(doc,'media')
            doc['assets']['source']={'uri':f'asset:image/{image_name(pid)}','mediaType':media_type(pid),'width':w,'height':h}
            doc['document']['body']=[{'id':'image','type':'media:image','assetId':'source','alt':r['alt'],'decorative':False}]
        else:raise TellMe('Unsupported review content; provide reviewed EduRich area')
        areas.append({'polygon':r['polygon'],'edurich':doc})
    if not areas and review.get('blank_confirmed') is not True:raise TellMe('Empty recognition requires blank-page confirmation')
    return validate_page(dict(pid=pid,width=w,height=h,areas=areas),image,printed_page)
