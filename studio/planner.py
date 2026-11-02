"""Persistent local AM/PM production queue; no social account publishing."""
import copy
import hashlib
import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date,datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from .daily import TYPES,COMPONENTS,validate_daily_settings
from .daily_context import edition_instant
from .store import now
from .platform_support import default_voice

DEFAULTS=dict(enabled=False,timezone='America/Denver',morning_type='combined',evening_type='combined',
              style='esoteric-minimal',deck='esoteric-minimal',voice=default_voice(),writer='local',include_news=False,
              components=list(COMPONENTS),lead_minutes=30)


class DailyPlanner:
    def __init__(self,store,jobs,start=False):
        self.store=store;self.jobs=jobs
        self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='daily-editions')
        self._stop=threading.Event();self.thread=None
        with store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS planner_settings (id INTEGER PRIMARY KEY, body TEXT NOT NULL)')
            db.execute('INSERT OR IGNORE INTO planner_settings VALUES (1,?)',(json.dumps(DEFAULTS),))
            db.execute('CREATE TABLE IF NOT EXISTS editions (id TEXT PRIMARY KEY,target TEXT NOT NULL,body TEXT NOT NULL)')
            for row in db.execute('SELECT id,body FROM editions').fetchall():
                entry=json.loads(row['body'])
                if entry['status']=='preparing':
                    entry.update(status='failed',error='Studio restarted during preparation. Prepare this edition again to retry.')
                    db.execute('UPDATE editions SET body=? WHERE id=?',(json.dumps(entry),entry['id']))
        if start:self.start()

    def config(self):
        with self.store.connect() as db:return json.loads(db.execute('SELECT body FROM planner_settings WHERE id=1').fetchone()['body'])

    def save(self,data):
        current=self.config();incoming={k:v for k,v in data.items() if k in DEFAULTS}
        result={**current,**incoming}
        if type(result['enabled']) is not bool:raise ValueError('Choose whether automatic preparation is enabled.')
        if result['morning_type'] not in TYPES or result['evening_type'] not in TYPES:raise ValueError('Choose a reading type for each edition.')
        for edition in ('morning','evening'):
            validate_daily_settings({**result,'reading_type':result[edition+'_type'],'edition':edition})
        result['lead_minutes']=30
        with self.store.connect() as db:db.execute('UPDATE planner_settings SET body=? WHERE id=1',(json.dumps(result),))
        return result

    def entries(self):
        with self.store.connect() as db:rows=db.execute('SELECT body FROM editions ORDER BY target DESC LIMIT 120').fetchall()
        entries=[json.loads(r['body']) for r in rows]
        for entry in entries:
            if entry.get('job_id') and entry['status']=='rendering':
                job=self.store.get_job(entry['job_id'])
                if job['status']=='done':entry.update(status='ready',error='',finished=job.get('finished'))
                elif job['status']=='failed':entry.update(status='failed',error=job['error'])
                entry['progress']=job['progress']
                if entry['status']!='rendering':self.put(entry)
        return entries

    def put(self,entry):
        with self.store.connect() as db:db.execute('INSERT OR REPLACE INTO editions VALUES (?,?,?)',(entry['id'],entry['target'],json.dumps(entry)))
        return entry

    def upcoming(self,current=None,days=7):
        config=self.config();current=(current or datetime.now(timezone.utc)).astimezone(ZoneInfo(config['timezone']))
        existing={entry['id']:entry for entry in self.entries()}
        result=[]
        for offset in range(days):
            day=(current.date()+timedelta(days=offset)).isoformat()
            for edition in ('morning','evening'):
                target=edition_instant(day,edition,config['timezone'])
                key=self.key(day,edition,config['timezone'])
                base=dict(id=key,date=day,edition=edition,timezone=config['timezone'],target=target.isoformat(),
                          reading_type=config[edition+'_type'],status='past' if target<current else 'planned',error='')
                result.append(existing.get(key,base))
        return result

    @staticmethod
    def key(day,edition,zone):return hashlib.sha256(f'{day}|{edition}|{zone}'.encode()).hexdigest()[:24]

    def prepare(self,day,edition,retry=False):
        config=self.config();target=edition_instant(day,edition,config['timezone']);key=self.key(day,edition,config['timezone'])
        kind=config[edition+'_type']
        settings=validate_daily_settings({**config,'date':day,'edition':edition,'reading_type':kind,
                                         'duration':90 if kind=='combined' else 45 if kind=='numerology' else 60})
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            previous=db.execute('SELECT body FROM editions WHERE id=?',(key,)).fetchone()
            entry=json.loads(previous['body']) if previous else None
            if entry and (entry['status']!='failed' or not retry):return entry
            if entry and entry.get('draft_id'):
                settings=entry['settings'];kind=entry['reading_type']
            entry={**(entry or {}),'id':key,'date':day,'edition':edition,'timezone':config['timezone'],
                   'target':target.isoformat(),'reading_type':kind,'status':'preparing','settings':settings,
                   'created':entry['created'] if entry else now(),'error':''}
            db.execute('INSERT OR REPLACE INTO editions VALUES (?,?,?)',(key,entry['target'],json.dumps(entry)))
        self.pool.submit(self.work,copy.deepcopy(entry))
        return entry

    def work(self,entry):
        try:
            if entry.get('draft_id'):
                draft=self.store.get(entry['draft_id'])
            else:
                from .daily import create_daily
                draft=self.store.create(create_daily(entry['settings']))
                entry['draft_id']=draft['id'];self.put(entry)
            job=self.jobs.submit(draft,'export')
            entry.update(status='rendering',job_id=job['id'],progress=job['progress'])
            self.put(entry)
        except Exception as exc:
            from openai import OpenAIError
            message='OpenAI could not prepare this edition. Check the connection or use built-in writing / Windows voice.' if isinstance(exc,OpenAIError) else str(exc)
            entry.update(status='failed',error=message[:500]);self.put(entry)

    def tick(self,current=None):
        config=self.config()
        if not config['enabled']:return
        current=current or datetime.now(timezone.utc)
        for entry in self.upcoming(current,days=1):
            seconds=(datetime.fromisoformat(entry['target'])-current).total_seconds()
            if entry['status']=='planned' and 0<=seconds<=config['lead_minutes']*60:
                self.prepare(entry['date'],entry['edition'])

    def start(self):
        if self.thread and self.thread.is_alive():return
        def loop():
            while not self._stop.is_set():
                try:self.tick()
                except Exception:logging.exception('Daily preparation clock failed')
                self._stop.wait(20)
        self.thread=threading.Thread(target=loop,name='daily-clock',daemon=True);self.thread.start()

    def snapshot(self):
        return dict(settings=self.config(),upcoming=self.upcoming(),history=self.entries(),
                    publishing='Local preparation only. Facebook publishing is not connected.',server_now=now())
