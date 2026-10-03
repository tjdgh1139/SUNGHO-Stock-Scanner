"""Official DART/Naver adapters. Results carry timestamps; errors never become evidence."""
from io import BytesIO
import html
import re
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import requests

class FeedError(RuntimeError):
    pass

def dart_corporations(api_key, get=requests.get):
    if not api_key: raise FeedError('DART_NOT_CONFIGURED')
    response=get('https://opendart.fss.or.kr/api/corpCode.xml',params={'crtfc_key':api_key},timeout=20)
    response.raise_for_status()
    try:
        with zipfile.ZipFile(BytesIO(response.content)) as archive:
            info=next(i for i in archive.infolist() if i.filename.upper().endswith('CORPCODE.XML'))
            if info.file_size>64*1024*1024: raise FeedError('DART_MAP_TOO_LARGE')
            root=ET.fromstring(archive.read(info))
    except (zipfile.BadZipFile,StopIteration,ET.ParseError) as exc:
        raise FeedError('DART_MAP_INVALID_RESPONSE') from exc
    return {x.findtext('stock_code','').strip():x.findtext('corp_code','').strip()
            for x in root.findall('list') if re.fullmatch(r'\d{6}',x.findtext('stock_code','').strip())
            and re.fullmatch(r'\d{8}',x.findtext('corp_code','').strip())}

def clean_text(text):
    return html.unescape(re.sub(r'<[^>]+>','',str(text or '')))

def naver_news(name,code,client_id,client_secret,get=requests.get):
    if not client_id or not client_secret: raise FeedError('NEWS_NOT_CONFIGURED')
    response=get('https://openapi.naver.com/v1/search/news.json',
                 params={'query':name,'display':20,'sort':'date'},
                 headers={'X-Naver-Client-Id':client_id,'X-Naver-Client-Secret':client_secret},timeout=10)
    response.raise_for_status()
    payload=response.json()
    if 'items' not in payload: raise FeedError('NEWS_INVALID_RESPONSE')
    result=[]
    now=datetime.now(timezone.utc)
    for item in payload['items']:
        try: stamp=parsedate_to_datetime(item.get('pubDate','')).astimezone(timezone.utc)
        except (ValueError,TypeError): continue
        if not 0<=(now-stamp).total_seconds()<=86400: continue
        title=clean_text(item.get('title'));body=clean_text(item.get('description'))
        # The provider's query match alone is insufficient for stock association.
        if name not in title+' '+body: continue
        result.append({'title':title,'body':body,'stock_code':str(code),'stock_name':name,
                       '_ts':stamp.isoformat(),'published_at':stamp.isoformat(),
                       'url':item.get('originallink') or item.get('link',''),'source':'NAVER Search'})
    return result
