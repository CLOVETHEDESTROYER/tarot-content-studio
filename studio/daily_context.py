"""Calculated calendar/sky facts and timestamped optional public news context."""
import itertools
import json
import math
import re
import uuid
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time, timedelta, timezone
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import astronomy
import httpx
from lunar_python import Solar
from .config import DATA

SIGNS = ('Aries','Taurus','Gemini','Cancer','Leo','Virgo','Libra','Scorpio','Sagittarius','Capricorn','Aquarius','Pisces')
ANIMALS = ('Rat','Ox','Tiger','Rabbit','Dragon','Snake','Horse','Goat','Monkey','Rooster','Dog','Pig')
ELEMENTS = ('Wood','Wood','Fire','Fire','Earth','Earth','Metal','Metal','Water','Water')
FEEDS = (
    ('BBC World','https://feeds.bbci.co.uk/news/world/rss.xml'),
    ('UN News','https://news.un.org/feed/subscribe/en/news/all/rss.xml'),
)


def edition_instant(day, edition, zone):
    try:
        value = date.fromisoformat(day)
        tz = ZoneInfo(zone)
    except (ValueError, TypeError, ZoneInfoNotFoundError):
        raise ValueError('Choose a valid calendar date and IANA timezone.')
    if not 1900 <= value.year <= 2099:
        raise ValueError('Choose a date between 1900 and 2099.')
    if edition not in ('morning','evening'):
        raise ValueError('Choose a morning or evening edition.')
    return datetime.combine(value, time(6 if edition == 'morning' else 18), tzinfo=tz)


def astro_time(value):
    value = value.astimezone(timezone.utc)
    return astronomy.Time.Make(value.year,value.month,value.day,value.hour,value.minute,value.second)


def longitude(body, instant):
    return astronomy.Ecliptic(astronomy.GeoVector(body,astro_time(instant),True)).elon % 360


def western_context(instant):
    bodies = ('Sun','Moon','Mercury','Venus','Mars','Jupiter','Saturn')
    positions = {}
    for name in bodies:
        body = getattr(astronomy.Body,name)
        value = longitude(body,instant)
        delta = (longitude(body,instant+timedelta(hours=12))-longitude(body,instant-timedelta(hours=12))+180)%360-180
        positions[name] = dict(longitude=round(value,5),sign=SIGNS[int(value//30)],degree=round(value%30,2),retrograde=delta<0)
    phase = (positions['Moon']['longitude']-positions['Sun']['longitude'])%360
    phases = ('New Moon','Waxing Crescent','First Quarter','Waxing Gibbous','Full Moon','Waning Gibbous','Last Quarter','Waning Crescent')
    name = phases[int((phase+22.5)//45)%8]
    aspects=[]
    for a,b in itertools.combinations(bodies,2):
        separation=abs((positions[a]['longitude']-positions[b]['longitude']+180)%360-180)
        for angle,label in ((0,'conjunction'),(60,'sextile'),(90,'square'),(120,'trine'),(180,'opposition')):
            orb=abs(separation-angle)
            if orb<=3:aspects.append(dict(first=a,second=b,aspect=label,orb=round(orb,2)))
    aspects.sort(key=lambda a:a['orb'])
    return dict(system='Tropical, geocentric zodiac',instant_utc=instant.astimezone(timezone.utc).isoformat(),
                positions=positions,moon_phase=name,phase_angle=round(phase,2),
                illumination=round(astronomy.Illumination(astronomy.Body.Moon,astro_time(instant)).phase_fraction*100,1),
                aspects=aspects[:3],source='https://github.com/cosinekitty/astronomy')


def chinese_context(day):
    value=date.fromisoformat(day)
    lunar=Solar.fromYmd(value.year,value.month,value.day).getLunar()
    year_stem,year_branch=lunar.getYearGanIndex(),lunar.getYearZhiIndex()
    day_stem,day_branch=lunar.getDayGanIndex(),lunar.getDayZhiIndex()
    return dict(lunar_year=lunar.getYear(),lunar_month=lunar.getMonth(),lunar_day=lunar.getDay(),
                year_animal=ANIMALS[year_branch],year_element=ELEMENTS[year_stem],year_polarity='Yang' if year_stem%2==0 else 'Yin',
                year_pillar=lunar.getYearInGanZhi(),day_animal=ANIMALS[day_branch],day_element=ELEMENTS[day_stem],
                day_polarity='Yang' if day_stem%2==0 else 'Yin',day_pillar=lunar.getDayInGanZhi(),
                convention='Annual zodiac changes at Chinese New Year; stem–branch day uses the publication calendar date and midnight rollover. Collective calendar symbolism, not a personal BaZi chart.',
                source='https://github.com/6tail/lunar-python')


def numerology_context(day):
    digits=[int(c) for c in day if c.isdigit()]
    value=sum(digits);steps=[value]
    while value>9 and value not in (11,22,33):
        value=sum(int(c) for c in str(value));steps.append(value)
    return dict(number=value,digit_sum=steps[0],steps=steps,
                calculation=' + '.join(map(str,digits))+' = '+' → '.join(map(str,steps)),
                method='Sum all Gregorian date digits; reduce repeatedly, preserving 11, 22, and 33 at each step. This is a stated symbolic convention, not astronomical data.')


def parse_feed(data,publisher,cutoff):
    if len(data)>1_000_000 or b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise ValueError('Unsupported news feed.')
    root=ET.fromstring(data)
    results=[]
    for item in root.findall('.//item')[:40]:
        title=re.sub('<[^>]*>','',item.findtext('title','')).strip()
        link=item.findtext('link','').strip()
        stamp=item.findtext('pubDate','')
        try:
            published=parsedate_to_datetime(stamp).astimezone(timezone.utc)
        except (ValueError,TypeError,AttributeError):continue
        if not title or not link.startswith('https://') or not cutoff-timedelta(hours=36)<=published<=cutoff:continue
        results.append(dict(title=title[:280],url=link,publisher=publisher,published=published.isoformat()))
    return results


def news_context(instant,now=None):
    current=(now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    cutoff=min(current,instant.astimezone(timezone.utc))
    def fetch(feed):
        publisher,url=feed
        try:
            with httpx.Client(timeout=7,follow_redirects=True,headers={'User-Agent':'StarPowerContentStudio/2.0 (+local editorial reader)'}) as client:
                response=client.get(url);response.raise_for_status()
                items=parse_feed(response.content,publisher,cutoff)
            return items,dict(publisher=publisher,url=url,status='ok',items=len(items))
        except Exception:
            return [],dict(publisher=publisher,url=url,status='unavailable',items=0)
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(fetch,FEEDS))
    items=[item for found,_ in results for item in found if datetime.fromisoformat(item['published'])>=instant.astimezone(timezone.utc)-timedelta(hours=36)]
    items.sort(key=lambda item:item['published'],reverse=True)
    seen=set();unique=[]
    for item in items:
        if item['title'].casefold() not in seen:unique.append(item);seen.add(item['title'].casefold())
    return dict(enabled=True,as_of=current.isoformat(),cutoff=cutoff.isoformat(),headlines=unique[:6],
                feeds=[state for _,state in results],status='available' if unique else 'No recent source headlines available for this edition; no news claims will be added.')


def build_context(config,now=None):
    instant=edition_instant(config['date'],config['edition'],config['timezone'])
    current=now or datetime.now(timezone.utc)
    result=dict(id=uuid.uuid4().hex,date=config['date'],edition=config['edition'],timezone=config['timezone'],
                publication_time=instant.isoformat(),calculated_at=current.isoformat(),western=western_context(instant),
                chinese=chinese_context(config['date']),numerology=numerology_context(config['date']))
    result['news']=news_context(instant,current) if config.get('include_news') else dict(enabled=False,headlines=[],status='Off')
    folder=DATA/'contexts';folder.mkdir(parents=True,exist_ok=True)
    (folder/(result['id']+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result


def saved_context(key,config):
    if not isinstance(key,str) or not re.fullmatch('[a-f0-9]{32}',key):raise ValueError('Refresh the daily context before generating.')
    path=DATA/'contexts'/(key+'.json')
    if not path.is_file():raise ValueError('This context snapshot is unavailable. Refresh it.')
    result=json.loads(path.read_text(encoding='utf-8'))
    if any(result[k]!=config[k] for k in ('date','edition','timezone')) or result['news']['enabled']!=config['include_news']:
        raise ValueError('Date, edition, timezone, or news changed. Refresh the context first.')
    if datetime.now(timezone.utc)-datetime.fromisoformat(result['calculated_at'])>timedelta(hours=6):raise ValueError('Refresh this context snapshot; it is over six hours old.')
    return result
