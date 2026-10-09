"""Official DART/Naver adapters. Results carry timestamps; errors never become evidence."""
from io import BytesIO
import html
import re
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit, parse_qs
import requests

class FeedError(RuntimeError):
    pass

def dart_corporations(api_key, get=requests.get):
    if not api_key: raise FeedError('DART_NOT_CONFIGURED')
    response=get('https://opendart.fss.or.kr/api/corpCode.xml',params={'crtfc_key':api_key},timeout=20)
    response.raise_for_status()
    if not response.content.startswith(b'PK'):
        try:
            error_root=ET.fromstring(response.content)
            status=error_root.findtext('status','')
        except ET.ParseError:
            status=''
        if re.fullmatch(r'\d{3}',status):
            raise FeedError('DART_API_STATUS_'+status)
        raise FeedError('DART_MAP_INVALID_RESPONSE')
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

def public_news(name,code,get=requests.get):
    """Public RSS headlines; no credentials, article bodies or inferred evidence."""
    if not str(name).strip():raise FeedError('NEWS_NAME_REQUIRED')
    response=get('https://www.bing.com/news/search',
        params={'q':'"'+str(name)+'"','format':'rss','setlang':'ko-KR'},timeout=8)
    response.raise_for_status()
    if len(response.content)>2*1024*1024:raise FeedError('NEWS_RESPONSE_TOO_LARGE')
    try:root=ET.fromstring(response.content)
    except ET.ParseError as exc:raise FeedError('NEWS_INVALID_RESPONSE') from exc
    if root.tag!='rss' or root.find('channel') is None:raise FeedError('NEWS_INVALID_RESPONSE')
    now=datetime.now(timezone.utc);result=[];seen=set()
    normalized=re.sub(r'\s+','',str(name))
    for item in root.findall('./channel/item')[:50]:
        title=clean_text(item.findtext('title',''));url=item.findtext('link','').strip()
        parts=urlsplit(url)
        if parts.hostname in ('www.bing.com','bing.com') and parts.path=='/news/apiclick.aspx':
            url=parse_qs(parts.query).get('url',[''])[0]
        try:
            stamp=parsedate_to_datetime(item.findtext('pubDate',''))
            if stamp.tzinfo is None:continue
            stamp=stamp.astimezone(timezone.utc)
        except (TypeError,ValueError):continue
        if not 0<=(now-stamp).total_seconds()<=86400:continue
        if normalized not in re.sub(r'\s+','',title):continue
        if not url.startswith('https://') or title in seen:continue
        seen.add(title)
        result.append({'title':title,'body':'','stock_code':str(code),'stock_name':str(name),
            '_ts':stamp.isoformat(),'published_at':stamp.isoformat(),'url':url,
            'source':'Bing News RSS','publisher':clean_text(item.findtext('source',''))})
    return result[:20]

def naver_news(name,code,client_id,client_secret,get=requests.get,provider='LEGACY'):
    if not client_id or not client_secret: raise FeedError('NEWS_NOT_CONFIGURED')
    provider=str(provider).strip().upper()
    if provider=='HUB':
        endpoint='https://naverapihub.apigw.ntruss.com/search/v1/news'
        headers={'X-NCP-APIGW-API-KEY-ID':client_id,'X-NCP-APIGW-API-KEY':client_secret}
    elif provider=='LEGACY':
        endpoint='https://openapi.naver.com/v1/search/news.json'
        headers={'X-Naver-Client-Id':client_id,'X-Naver-Client-Secret':client_secret}
    else:
        raise FeedError('NEWS_INVALID_PROVIDER')
    response=get(endpoint,
                 params={'query':name,'display':20,'sort':'date'},
                 headers=headers,timeout=10)
    response.raise_for_status()
    payload=response.json()
    if not isinstance(payload,dict) or not isinstance(payload.get('items'),list):
        raise FeedError('NEWS_INVALID_RESPONSE')
    result=[]
    now=datetime.now(timezone.utc)
    for item in payload['items']:
        if not isinstance(item,dict): continue
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
