"""ZenWave-style local Requests / Status / Ready / Reports exchange for Muse.

No public listener, Facebook login, or platform publishing is implemented here.
Generation and actual external publication acknowledgements remain separate.
"""
import copy
import hashlib
import json
import logging
import os
import re
import shutil
import threading
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date,datetime,timedelta
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
from .config import DATA,EXPORTS,ROOT
from .daily import COMPONENTS,TYPES,create_daily,validate_daily_settings
from .daily_context import edition_instant
from .daily_visuals import STYLES
from .engine import DURATIONS,VOICES
from .platform_support import default_voice
from .store import Conflict,now
from .operations import generation_action
from .version import VERSION

MAX_JSON=100_000
MEDIA=('reading.mp4','cover.jpg','caption.txt','subtitles.srt','reading.json','timeline.json','context.json','sources.txt')


def valid_id(value):
    return isinstance(value,str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}',value) and value.upper() not in {'CON','PRN','AUX','NUL',*[f'{p}{n}' for p in ('COM','LPT') for n in range(1,10)]}


def canonical(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'))


def checksum(path):
    digest=hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda:source.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


def inside(root,path):
    if not path.resolve().is_relative_to(root.resolve()):raise ValueError('Exchange paths must stay inside the selected exchange folder.')
    return path


def atomic_json(root,path,value):
    inside(root,path);path.parent.mkdir(parents=True,exist_ok=True)
    content=json.dumps(value,ensure_ascii=False,indent=2)+'\n'
    if path.is_file() and path.read_text(encoding='utf-8')==content:return
    temporary=inside(root,path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp'))
    temporary.write_text(content,encoding='utf-8');temporary.replace(path)


def validate_request(data):
    allowed={'schemaVersion','kind','requestId','brief','startDate','days','editions','timezone','morningType','eveningType','style','deck','voice','writer','components','duration','includeNews','campaign','requestedBy'}
    if not isinstance(data,dict) or set(data)-allowed:raise ValueError('Use only the documented reading-week request fields.')
    if type(data.get('schemaVersion')) is not int or data['schemaVersion']!=1 or data.get('kind') not in ('reading-week','connection-test') or not valid_id(data.get('requestId')):
        raise ValueError('Use schemaVersion 1, reading-week or connection-test, and a safe requestId.')
    brief=data.get('brief','')
    if not isinstance(brief,str) or not 1<=len(brief.strip())<=10000:raise ValueError('Supply the original brief (1–10,000 characters).')
    days=data.get('days',7);editions=data.get('editions',['morning','evening'])
    if type(days) is not int or not 1<=days<=7:raise ValueError('Choose one to seven calendar days.')
    if not isinstance(editions,list) or not editions or len(editions)!=len(set(editions)) or any(e not in ('morning','evening') for e in editions):raise ValueError('Choose morning, evening, or both without duplicates.')
    zone=data.get('timezone','America/Denver');start=data.get('startDate')
    edition_instant(start,'morning',zone)
    include_news=data.get('includeNews',False)
    if include_news and days>1:raise ValueError('Generate news editions one day at a time near publication; future headlines are not available for a weekly batch.')
    output={key:data[key] for key in ('duration',) if key in data}
    for key,default in [('style','esoteric-minimal'),('deck','esoteric-minimal'),('voice',default_voice()),('writer','local'),('components',list(COMPONENTS))]:output[key]=data.get(key,default)
    result=dict(schemaVersion=1,kind=data['kind'],requestId=data['requestId'],brief=brief.strip(),startDate=start,days=days,
                editions=[e for e in ('morning','evening') if e in editions],timezone=zone,
                morningType=data.get('morningType','combined'),eveningType=data.get('eveningType','combined'),includeNews=include_news,**output)
    for key in ('campaign','requestedBy'):
        value=data.get(key,'')
        if not isinstance(value,str) or len(value)>300:raise ValueError(f'{key} must be text up to 300 characters.')
        result[key]=value
    if result['kind']=='connection-test':
        result.update(days=1,editions=['morning'],morningType='numerology',voice='silent',writer='local',duration=30,includeNews=False)
    request_items(result)  # validate every resolved day/type before accepting
    return result


def request_items(request):
    items=[];start=date.fromisoformat(request['startDate'])
    for offset in range(request['days']):
        day=(start+timedelta(days=offset)).isoformat()
        for edition in request['editions']:
            kind=request[edition+'Type']
            settings=validate_daily_settings({**request,'date':day,'edition':edition,'reading_type':kind,
                'include_news':request['includeNews'],'duration':request.get('duration',90 if kind=='combined' else 45 if kind=='numerology' else 60)})
            items.append(dict(date=day,edition=edition,settings=settings,target=edition_instant(day,edition,request['timezone']).isoformat(),status='pending'))
    return items


class AgentJobs:
    def __init__(self,store,planner,jobs,start=False):
        self.store=store;self.planner=planner;self.jobs=jobs;self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='muse-batches')
        self._stop=threading.Event();self.guard=threading.Lock()
        with store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS agent_settings (id INTEGER PRIMARY KEY,body TEXT NOT NULL)')
            db.execute('INSERT OR IGNORE INTO agent_settings VALUES (1,?)',(canonical(dict(enabled=False,folder=str((DATA/'exchange').resolve()))),))
            db.execute('CREATE TABLE IF NOT EXISTS agent_requests (id TEXT PRIMARY KEY,payload TEXT NOT NULL,body TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS agent_assets (id TEXT PRIMARY KEY,body TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS agent_reports (id TEXT PRIMARY KEY,payload TEXT NOT NULL,event_key TEXT UNIQUE NOT NULL,body TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS agent_events (sequence INTEGER PRIMARY KEY AUTOINCREMENT,at TEXT NOT NULL,kind TEXT NOT NULL,subject TEXT NOT NULL,body TEXT NOT NULL)')
            for row in db.execute('SELECT body FROM agent_requests').fetchall():
                record=json.loads(row['body'])
                if record['status'] in ('queued','running'):
                    record.update(status='interrupted',error='Studio restarted. Completed editions remain saved; explicitly resume this request to continue.',updated=now())
                    db.execute('UPDATE agent_requests SET body=? WHERE id=?',(canonical(record),record['id']))
        if start:
            self.thread=threading.Thread(target=self.loop,name='muse-exchange',daemon=True);self.thread.start()

    def event(self,kind,subject,body):
        with self.store.connect() as db:db.execute('INSERT INTO agent_events(at,kind,subject,body) VALUES (?,?,?,?)',(now(),kind,subject,canonical(body)))

    def config(self):
        with self.store.connect() as db:return json.loads(db.execute('SELECT body FROM agent_settings WHERE id=1').fetchone()['body'])

    def get(self,key):
        with self.store.connect() as db:row=db.execute('SELECT body FROM agent_requests WHERE id=?',(key,)).fetchone()
        if not row:raise KeyError('Agent request not found.')
        return json.loads(row['body'])

    def put(self,record):
        record['updated']=now()
        with self.store.connect() as db:db.execute('UPDATE agent_requests SET body=? WHERE id=?',(canonical(record),record['id']))
        atomic_json(Path(record['exchangeRoot']),Path(record['exchangeRoot'])/'Status'/(record['id']+'.json'),self.status(record))

    @staticmethod
    def status(record):
        return dict(schemaVersion=1,requestId=record['id'],status=record['status'],progress=record.get('progress',0),
            message=record.get('error') or record.get('message',''),publicationAllowed=record['request']['kind']!='connection-test',
            publishing='Not scheduled or posted by this studio.',assets=record.get('assets',[]),archive=record.get('archive'),items=record['items'])

    def catalog(self):
        return dict(schemaVersion=1,application='starpower-content-studio',version=VERSION,requestKinds=['reading-week','connection-test'],
            readingTypes=TYPES,components=list(COMPONENTS),styles=STYLES,durations=list(DURATIONS),voices=list(VOICES),defaultVoice=default_voice(),
            timezone='America/Denver',slots=dict(morning='06:00',evening='18:00'),maxDays=7,maxAssets=14,
            newsPolicy='Advance weekly batches omit news. Use a single-day request near publication for current headlines.',
            publishing='Muse schedules/posts through separately authorized platform access; Reports record its acknowledgements only.')

    def prepare_exchange(self,folder=None):
        config=self.config();root=Path(folder or config['folder']).expanduser()
        if not root.is_absolute():raise ValueError('Choose an absolute path to a dedicated Tarot Exchange folder.')
        root=root.resolve()
        for name in ('studio-info.json','catalog.json'):
            existing=inside(root,root/name)
            if existing.is_file():
                identity=json.loads(existing.read_text(encoding='utf-8'))
                if identity.get('application')!='starpower-content-studio':
                    raise ValueError('This folder belongs to another studio. Choose a separate Tarot exchange; ZenWave metadata will not be changed.')
        if root in (ROOT.resolve(),DATA.resolve(),EXPORTS.resolve()) or root.is_relative_to(ROOT/'assets') or root.is_relative_to(ROOT/'frontend'):
            raise ValueError('Use a dedicated exchange folder, not the app, assets, data, or export root.')
        root.mkdir(parents=True,exist_ok=True)
        for name in ('Requests','Status','Ready','Reports','Examples'):inside(root,root/name).mkdir(exist_ok=True)
        atomic_json(root,root/'catalog.json',self.catalog())
        instructions=(ROOT/'resources/AgentInstructions.md').read_text(encoding='utf-8')
        target=inside(root,root/'AGENT-INSTRUCTIONS.md')
        if not target.exists() or target.read_text(encoding='utf-8')!=instructions:target.write_text(instructions,encoding='utf-8')
        example=root/'Examples/first-test.json'
        if not example.exists():atomic_json(root,example,dict(schemaVersion=1,kind='connection-test',requestId='first-test',brief='Verify the Tarot exchange. Do not post this test.',startDate=datetime.now(ZoneInfo('America/Denver')).date().isoformat()))
        atomic_json(root,root/'studio-info.json',dict(schemaVersion=1,application='starpower-content-studio',version=VERSION,catalogSHA256=checksum(root/'catalog.json')))
        return root

    def save(self,data):
        config=self.config()
        if set(data)-{'folder','enabled'}:raise ValueError('Choose only an exchange folder and inbox-watching preference.')
        if 'enabled' in data and type(data['enabled']) is not bool:raise ValueError('Inbox watching must be true or false.')
        folder=data.get('folder',config['folder'])
        if not isinstance(folder,str) or len(folder)>1000:raise ValueError('Choose an exchange folder path.')
        with self.guard:
            if folder!=config['folder']:
                if config['enabled']:raise Conflict('Pause inbox watching before choosing a different exchange folder.')
                with self.store.connect() as db:rows=db.execute('SELECT body FROM agent_requests').fetchall()
                if any(json.loads(r['body'])['status'] in ('queued','running') for r in rows):raise Conflict('Wait for active agent batches to finish before changing exchange folders.')
            root=self.prepare_exchange(folder);config.update(folder=str(root),enabled=data.get('enabled',config['enabled']))
            with self.store.connect() as db:db.execute('UPDATE agent_settings SET body=? WHERE id=1',(canonical(config),))
        return config

    @generation_action
    def submit(self,data,retry=False):
        request=validate_request(data);key=request['requestId'];payload=canonical(request)
        root=self.prepare_exchange()
        if request['timezone']!=self.planner.config()['timezone']:raise ValueError('Use the daily planner timezone for weekly agent requests.')
        with self.guard,self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE');row=db.execute('SELECT payload,body FROM agent_requests WHERE id=?',(key,)).fetchone()
            if row:
                if row['payload']!=payload:raise Conflict('This requestId already has different parameters. Use a new ID; its saved result will not be replaced.')
                record=json.loads(row['body'])
                if not retry or record['status'] not in ('failed','interrupted'):return record
                record.update(status='queued',error='',message='Resuming saved editions; completed videos are reused.')
                db.execute('UPDATE agent_requests SET body=? WHERE id=?',(canonical(record),key))
            else:
                record=dict(id=key,request=request,exchangeRoot=str(root),created=now(),updated=now(),status='queued',items=request_items(request),assets=[],progress=0,error='',message='Queued for local generation.')
                db.execute('INSERT INTO agent_requests VALUES (?,?,?)',(key,payload,canonical(record)))
        self.put(record);self.event('request-accepted',key,dict(retry=retry));self.pool.submit(self.work,key)
        return record

    def wait_job(self,key,record):
        deadline=time.monotonic()+900
        while time.monotonic()<deadline:
            job=self.store.get_job(key)
            if job['status']=='done':return job
            if job['status']=='failed':raise ValueError(job['error'])
            record['message']=job.get('message','Rendering');self.put(record);time.sleep(1)
        raise ValueError('Renderer did not finish within fifteen minutes. Saved work is retained; review before resuming.')

    def work(self,key):
        record=self.get(key);root=Path(record['exchangeRoot']);assets=[]
        try:
            record.update(status='running',error='',message='Generating dated readings locally.');self.put(record)
            for index,item in enumerate(record['items']):
                if record['request']['kind']=='connection-test':
                    if not item.get('draftId'):
                        draft=create_daily(item['settings']);draft.update(title='Tarot exchange connection test',archived=True)
                        draft=self.store.create(draft);item['draftId']=draft['id'];self.put(record)
                    draft=self.store.get(item['draftId'])
                    job=self.store.get_job(item['jobId']) if item.get('jobId') else None
                    if not job or job['status']=='failed':job=self.jobs.submit(draft,'export');item['jobId']=job['id'];self.put(record)
                    job=self.wait_job(job['id'],record)
                else:
                    # The planner's SQLite slot reservation is shared with the UI.
                    entry=self.planner.prepare(item['date'],item['edition'],retry=True,settings_override=item['settings'])
                    deadline=time.monotonic()+900
                    while entry['status'] in ('preparing','rendering') and time.monotonic()<deadline:
                        entry=self.planner.get_entry(entry['id'])
                        record['message']=f"{item['date']} · {item['edition']} · {entry['status']}";self.put(record);time.sleep(1)
                    if entry['status']!='ready':raise ValueError(entry.get('error') or 'Edition preparation timed out. Review and resume the saved request.')
                    item.update(draftId=entry['draft_id'],jobId=entry['job_id']);job=self.store.get_job(entry['job_id'])
                item['status']='ready';item['assetId']=job['id']
                asset=self.copy_asset(root,record,item,job);assets.append(asset)
                record.update(assets=assets,progress=round((index+1)/len(record['items'])*100));self.put(record)
            ready=dict(schemaVersion=1,requestId=key,publicationAllowed=record['request']['kind']!='connection-test',assets=assets,
                       publishing='Proposed times only. No platform schedules or posts have been created.')
            atomic_json(root,root/'Ready'/key/'request.json',record['request'])
            atomic_json(root,root/'Ready'/key/'ready.json',ready)
            archive=inside(root,root/'Ready'/(key+'.zip'));temporary=inside(root,archive.with_suffix('.zip.tmp'))
            with zipfile.ZipFile(temporary,'w',zipfile.ZIP_STORED) as bundle:
                for path in sorted((root/'Ready'/key).rglob('*')):
                    if path.is_file():inside(root,path);bundle.write(path,path.relative_to(root/'Ready'/key))
            temporary.replace(archive)
            with self.store.connect() as db:
                for asset in assets:db.execute('INSERT OR IGNORE INTO agent_assets VALUES (?,?)',(asset['id'],canonical(asset)))
            record.update(status='complete',progress=100,archive=archive.relative_to(root).as_posix(),message='Ready for Muse to retrieve. Nothing has been scheduled or posted.')
            self.put(record);self.event('request-complete',key,dict(assets=[a['id'] for a in assets]))
        except Exception as exc:
            logging.exception('Agent request failed: %s',key)
            from openai import OpenAIError
            message='OpenAI could not write this edition. Check the connection or use built-in writing.' if isinstance(exc,OpenAIError) else str(exc)
            record.update(status='failed',error=message[:700]);self.put(record);self.event('request-failed',key,dict(error=record['error']))

    def copy_asset(self,root,record,item,job):
        folder=inside(root,root/'Ready'/record['id']/(item['date']+'-'+item['edition']));folder.mkdir(parents=True,exist_ok=True)
        files={};source=EXPORTS/job['id']
        for name in MEDIA:
            if name not in job.get('files',[]):continue
            target=inside(root,folder/name);temporary=inside(root,target.with_name(name+'.tmp'))
            shutil.copyfile(source/name,temporary);temporary.replace(target)
            files[name]=dict(path=target.relative_to(root).as_posix(),sha256=checksum(target),bytes=target.stat().st_size)
        if 'reading.mp4' not in files:raise ValueError('The saved export has no ready MP4. Review the original export before retrying.')
        return dict(id=job['id'],readingId=job['draft_id'],revision=job['revision'],date=item['date'],edition=item['edition'],timezone=record['request']['timezone'],
                    proposedPublishAt=item['target'] if record['request']['kind']!='connection-test' else None,
                    publicationAllowed=record['request']['kind']!='connection-test',files=files)

    def report(self,data):
        allowed={'id','assetId','platform','accountId','postId','status','scheduledAt','publishedAt','url'}
        if not isinstance(data,dict) or set(data)-allowed or not valid_id(data.get('id')):raise ValueError('Use the documented publication-report fields and safe report ID.')
        for key in ('assetId','accountId','postId'):
            if not isinstance(data.get(key),str) or not 1<=len(data[key])<=200:raise ValueError('Publication reports need a known asset, account/Page ID, and real platform post ID.')
        if data.get('platform') not in ('facebook','instagram') or data.get('status') not in ('scheduled','published','failed'):raise ValueError('Report facebook/instagram and scheduled/published/failed.')
        for key in ('scheduledAt','publishedAt'):
            if data.get(key):
                value=datetime.fromisoformat(data[key].replace('Z','+00:00'))
                if value.tzinfo is None:raise ValueError('Publication times must include a timezone offset.')
        if data['status']=='scheduled' and not data.get('scheduledAt'):raise ValueError('A scheduled acknowledgement needs the actual scheduledAt time.')
        if data.get('url') and (not isinstance(data['url'],str) or len(data['url'])>2000 or urlsplit(data['url']).scheme!='https'):raise ValueError('Use an HTTPS platform post URL.')
        payload=canonical(data);event_key=hashlib.sha256(canonical({k:v for k,v in data.items() if k!='id'}).encode()).hexdigest()
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE');asset=db.execute('SELECT body FROM agent_assets WHERE id=?',(data['assetId'],)).fetchone()
            if not asset or not json.loads(asset['body'])['publicationAllowed']:raise ValueError('Report an existing production asset from a completed request. Connection tests cannot be posted.')
            completed=[json.loads(row['body']) for row in db.execute("SELECT body FROM agent_requests WHERE json_extract(body,'$.status')='complete'")]
            if not any(any(a['id']==data['assetId'] for a in r.get('assets',[])) for r in completed):raise ValueError('Wait until the production batch is complete before recording publication.')
            previous=db.execute('SELECT payload,body FROM agent_reports WHERE id=?',(data['id'],)).fetchone()
            if previous:
                if previous['payload']!=payload:raise Conflict('This report ID already has different details. Use a new event ID for a later update.')
                return json.loads(previous['body'])
            duplicate=db.execute('SELECT body FROM agent_reports WHERE event_key=?',(event_key,)).fetchone()
            if duplicate:return json.loads(duplicate['body'])
            report={**data,'receivedAt':now(),'source':'external-acknowledgement','independentlyVerified':False}
            db.execute('INSERT INTO agent_reports VALUES (?,?,?,?)',(data['id'],payload,event_key,canonical(report)))
        self.event('publication-reported',data['assetId'],report);return report

    def poll(self):
        from . import operations
        with operations.LOCK:
            if operations.installing:return
            return self._poll()

    def _poll(self):
        root=Path(self.config()['folder'])
        if not root.is_dir():return
        for folder in ('Requests','Reports'):
            directory=inside(root,root/folder)
            for path in sorted(directory.glob('*.json'))[:100]:
                if folder=='Reports' and path.name.endswith('.result.json'):continue
                key=path.stem if valid_id(path.stem) else 'rejected-'+hashlib.sha256(path.name.encode()).hexdigest()[:16]
                destination=root/('Status' if folder=='Requests' else 'Reports')/(key+('.json' if folder=='Requests' else '.result.json'))
                try:
                    inside(root,path)
                    if path.stat().st_size>MAX_JSON:raise ValueError('Exchange JSON files must be no larger than 100 KB.')
                    data=json.loads(path.read_text(encoding='utf-8-sig'))
                    if not isinstance(data,dict) or data.get('requestId' if folder=='Requests' else 'id')!=path.stem:raise ValueError('The filename must match its requestId/report id.')
                    if folder=='Requests':
                        record=self.submit(data)
                        if not destination.exists() and record['status'] in ('complete','failed','interrupted'):
                            atomic_json(root,destination,self.status(record))
                        continue  # Only the job writer owns live status; a poll must not overwrite newer progress.
                    value=dict(accepted=True,report=self.report(data))
                except Exception as exc:
                    # Never overwrite a valid completed status when a changed replay is rejected.
                    destination=destination.with_name(key+'.error.json') if folder=='Requests' and destination.exists() else destination
                    if path.name.endswith('.error.json'):continue
                    value=dict(status='error',message=str(exc)[:700])
                atomic_json(root,destination,value)

    def loop(self):
        while not self._stop.is_set():
            try:
                if self.config()['enabled']:self.poll()
            except Exception:logging.exception('Muse exchange polling failed')
            self._stop.wait(3)

    def snapshot(self):
        with self.store.connect() as db:
            requests=[json.loads(r['body']) for r in db.execute('SELECT body FROM agent_requests ORDER BY rowid DESC LIMIT 100')]
            reports=[json.loads(r['body']) for r in db.execute('SELECT body FROM agent_reports ORDER BY rowid DESC LIMIT 200')]
            assets=[json.loads(r['body']) for r in db.execute('SELECT body FROM agent_assets ORDER BY rowid DESC LIMIT 200')]
        return dict(settings=self.config(),requests=requests,reports=reports,assets=assets,
                    publishing='External acknowledgements only. Muse access and social publishing are not connected by this studio.')
