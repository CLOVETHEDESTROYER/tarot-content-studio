from __future__ import annotations

import copy
import json
import sqlite3
import threading
import time
import uuid
from contextlib import closing, contextmanager
from pathlib import Path
from ..deck_catalog import get_deck
from ..operations import generation_action


def initial_state():
    return {
        'running': False, 'paused': False, 'session': '', 'next_at': 0,
        'queue': [], 'carry': None, 'processing': None, 'display': None,
        'last_error': '', 'recent': {},
        'settings': {'interval': 270, 'approval': True, 'use_ai': True,
                     'use_voice': True, 'spread': 'three', 'presenter': 'Zenwave', 'deck': 'celebrity', 'reading_type':'tarot','reading_date':'','style':'esoteric-minimal','timezone':'America/Denver','voice':'openai-coral'},
    }


class LiveStudio:
    def __init__(self, path: Path, generate):
        self.path = path
        self.generate = generate
        self._thread = None
        self._thread_lock = threading.Lock()
        self._stop = threading.Event()
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(path)) as db:
            db.execute('CREATE TABLE IF NOT EXISTS studio (id INTEGER PRIMARY KEY, data TEXT NOT NULL)')
            db.execute('INSERT OR IGNORE INTO studio VALUES (1, ?)', (json.dumps(initial_state()),))
            db.commit()

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=15)
        try:
            db.execute('BEGIN IMMEDIATE')
            state = json.loads(db.execute('SELECT data FROM studio WHERE id=1').fetchone()[0])
            yield state
            db.execute('UPDATE studio SET data=? WHERE id=1', (json.dumps(state),))
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def snapshot(self, public=False):
        with closing(sqlite3.connect(self.path, timeout=15)) as db:
            state = json.loads(db.execute('SELECT data FROM studio WHERE id=1').fetchone()[0])
        state.pop('recent', None)
        if state['display']:
            state['display'].pop('audio_data', None)
        state['server_now'] = time.time()
        if public:
            state['queue'] = [{'viewer': item['viewer']} for item in state['queue'] if item['status'] == 'queued']
            state['carry'] = None
            state['last_error'] = ''
            if state['processing']:
                state['processing'] = {'started': state['processing']['started']}
        return state

    def settings(self, values):
        interval = int(values.get('interval', 270))
        if interval not in range(60, 301, 30):
            raise ValueError('Choose 1 to 5 minutes in 30-second steps.')
        if values.get('spread', 'three') not in ('one', 'three'):
            raise ValueError('LIVE supports one or three cards.')
        deck = values.get('deck', 'celebrity')
        if deck != 'celebrity':
            get_deck(__import__('studio.config',fromlist=['ROOT']).ROOT, deck)
        from ..daily import TYPES
        from ..daily_visuals import STYLES
        from ..engine import VOICES
        from zoneinfo import ZoneInfo
        from datetime import date
        if values.get('reading_type','tarot') not in TYPES:raise ValueError('Choose an available reading type.')
        if values.get('style','esoteric-minimal') not in STYLES:raise ValueError('Choose an available visual style.')
        if values.get('voice','openai-coral') not in VOICES:raise ValueError('Choose an available voice.')
        ZoneInfo(values.get('timezone','America/Denver'))
        if values.get('reading_date'):date.fromisoformat(values['reading_date'])
        with self.transaction() as state:
            state['settings'] = {
                'interval': interval, 'approval': bool(values.get('approval', True)),
                'use_ai': bool(values.get('use_ai', True)), 'use_voice': bool(values.get('use_voice', True)),
                'spread': values.get('spread', 'three'),
                'deck': deck,
                'reading_type':values.get('reading_type','tarot'),'reading_date':values.get('reading_date',''),
                'style':values.get('style','esoteric-minimal'),'timezone':values.get('timezone','America/Denver'),
                'voice':values.get('voice','openai-coral'),
                'presenter': str(values.get('presenter', 'Zenwave')).strip()[:60] or 'Zenwave',
            }
            if state['running'] and state['next_at']:
                # Preserve time since the last pull when the interval changes.
                previous = state.get('last_started', 0)
                if previous:
                    state['next_at'] = previous + interval

    def add(self, viewer, question, source='manual',reading_type=None,reading_date=None):
        viewer = str(viewer).strip().lstrip('@')[:64]
        question = str(question).strip()[:400]
        if not viewer or not question:
            raise ValueError('A viewer name and question are required.')
        from ..daily import TYPES
        from datetime import date
        if reading_type is not None and reading_type not in TYPES:raise ValueError('Choose an available reading type.')
        if reading_date:date.fromisoformat(reading_date)
        now = time.time()
        with self.transaction() as state:
            if source == 'tiktok' and not state['running']:
                raise ValueError('The live session is closed.')
            if len(state['queue']) >= 50:
                raise ValueError('Queue full. Finish or remove a request first.')
            waiting = [item['viewer'].casefold() for item in state['queue']]
            if state['processing']:
                waiting.append(state['processing']['request']['viewer'].casefold())
            if viewer.casefold() in waiting:
                raise ValueError('This viewer already has a waiting or active request.')
            if source == 'tiktok' and now - state['recent'].get(viewer.casefold(), 0) < 600:
                raise ValueError('This viewer can request again after 10 minutes.')
            item = {'id': uuid.uuid4().hex, 'viewer': viewer, 'question': question,
                    'source': source, 'created': now,'reading_type':reading_type or state['settings'].get('reading_type','tarot'),
                    'reading_date':reading_date or state['settings'].get('reading_date',''),
                    'status': 'pending' if state['settings']['approval'] else 'queued'}
            state['queue'].append(item)
            state['recent'] = {key: value for key, value in state['recent'].items() if now - value < 600}
            state['recent'][viewer.casefold()] = now
        return item

    def request_action(self, request_id, action):
        with self.transaction() as state:
            item = next((item for item in state['queue'] if item['id'] == request_id), None)
            if not item:
                raise ValueError('That request is no longer waiting.')
            if action == 'approve':
                item['status'] = 'queued'
            elif action == 'remove':
                state['queue'].remove(item)
            else:
                raise ValueError('Unknown request action.')

    @generation_action
    def start(self):
        with self.transaction() as state:
            if state['running']:
                return
            state['running'] = True
            state['paused'] = False
            state['session'] = uuid.uuid4().hex
            state['processing'] = None
            state['next_at'] = 0
            state['last_error'] = ''
            if state['carry']:
                item = state['carry']
                item['id'] = uuid.uuid4().hex
                # Carry-over is always first, even ahead of newly staged requests.
                state['queue'] = [item] + [q for q in state['queue'] if q['viewer'].casefold() != item['viewer'].casefold()]
                state['carry'] = None
        self.ensure_worker()

    def pause(self):
        with self.transaction() as state:
            if not state['running']:
                raise ValueError('Start the live session first.')
            state['paused'] = not state['paused']

    def end(self):
        with self.transaction() as state:
            if not state['running'] and not state['queue'] and not state['processing']:
                return
            candidate = state['queue'][-1] if state['queue'] else None
            if not candidate and state['processing']:
                candidate = state['processing']['request']
            if not candidate and state['display']:
                candidate = {'viewer': state['display']['viewer'], 'question': state['display']['question'],
                             'status': 'queued', 'source': 'carry', 'created': time.time(),'reading_type':state['display'].get('reading_type','tarot'),'reading_date':state['display'].get('reading_date','')}
            state['carry'] = copy.deepcopy(candidate)
            state['queue'] = []
            state['processing'] = None
            state['running'] = False
            state['paused'] = False
            state['session'] = uuid.uuid4().hex
            state['next_at'] = 0
            state['recent'] = {}

    @generation_action
    def claim(self, now=None):
        now = time.time() if now is None else now
        with self.transaction() as state:
            if not state['running'] or state['paused'] or state['processing'] or now < state['next_at']:
                return None
            # Strict arrival order: an unapproved first request holds later ones.
            if not state['queue'] or state['queue'][0]['status'] != 'queued':
                return None
            item = state['queue'].pop(0)
            job = {'request': item, 'session': state['session'], 'started': now,
                   'settings': copy.deepcopy(state['settings'])}
            state['processing'] = job
            state['last_started'] = now
            state['next_at'] = now + state['settings']['interval']
            return job

    def finish(self, job, result):
        with self.transaction() as state:
            if not state['running'] or state['session'] != job['session']:
                return
            state['display'] = {**result, 'id': job['request']['id'],
                                'viewer': job['request']['viewer'], 'question': job['request']['question']}
            state['processing'] = None
            state['last_error'] = result.get('warning', '')

    def audio(self, display_id):
        with closing(sqlite3.connect(self.path, timeout=15)) as db:
            state = json.loads(db.execute('SELECT data FROM studio WHERE id=1').fetchone()[0])
        display = state.get('display')
        return display.get('audio_data') if display and display['id'] == display_id else None

    def ensure_worker(self):
        with self._thread_lock:
            if self._thread and self._thread.is_alive():
                return
            self._thread = threading.Thread(target=self._work, name='tarot-live-worker', daemon=True)
            self._thread.start()

    def _work(self):
        while not self._stop.is_set():
            try:
                job = self.claim()
                if job:
                    try:
                        self.finish(job, self.generate(job))
                    except Exception as exc:
                        with self.transaction() as state:
                            if state['session'] == job['session']:
                                state['processing'] = None
                                state['queue'].insert(0, job['request'])
                                state['paused'] = True
                                state['last_error'] = f'Generation failed ({type(exc).__name__}). Paused; request kept for retry.'
            except sqlite3.Error:
                pass
            self._stop.wait(1)


class TikTokChat:
    def __init__(self, studio):
        self.studio = studio
        self.status = {'connected': False, 'handle': '', 'message': 'Not connected', 'received': 0, 'accepted': 0}
        self._stop = threading.Event()
        self._thread = None
        self._loop = None
        self._client = None

    def ingest(self, viewer, comment):
        self.status['received'] += 1
        parts = str(comment).strip().split(maxsplit=1)
        commands={'!tarot':'tarot','!reading':None,'!western':'western','!astrology':'western','!chinese':'chinese','!numerology':'numerology','!combined':'combined'}
        if not parts or parts[0].lower() not in commands:
            return False
        question = parts[1] if len(parts) > 1 else 'What energy should I focus on today?'
        try:
            self.studio.add(viewer, question, 'tiktok',reading_type=commands[parts[0].lower()])
            self.status['accepted'] += 1
            return True
        except ValueError:
            return False

    def ingest_event(self, event):
        user = getattr(event, 'user', None)
        if user is None:
            return False
        viewer = (getattr(user, 'unique_id', None) or getattr(user, 'display_id', None)
                  or getattr(user, 'nickname', None) or str(getattr(user, 'id', '')))
        return self.ingest(viewer, event.comment)

    def connect(self, handle):
        import re
        handle = str(handle).strip().lstrip('@')
        if not re.fullmatch(r'[A-Za-z0-9_.]{1,64}', handle):
            raise ValueError('Enter a TikTok handle without a URL.')
        try:
            import TikTokLive  # noqa: F401
        except ImportError:
            raise ValueError('Install the connector: python -m pip install -r requirements-live.txt')
        if self._thread and self._thread.is_alive():
            raise ValueError('Disconnect the existing chat connection first.')
        self._stop.clear()
        self.status.update(handle=handle, message='Connecting...', connected=False)
        self._thread = threading.Thread(target=self._run, daemon=True, name='tiktok-chat')
        self._thread.start()

    def disconnect(self):
        self._stop.set()
        if self._loop and self._client and self._loop.is_running():
            import asyncio
            asyncio.run_coroutine_threadsafe(self._client.disconnect(), self._loop)
        self.status.update(connected=False, message='Disconnected')

    def live_ended(self):
        self.studio.end()
        self._stop.set()
        self.status.update(connected=False, message='LIVE ended. One starter saved; other queued requests cleared.')

    def _run(self):
        import asyncio
        from TikTokLive import TikTokLiveClient
        from TikTokLive.events import CommentEvent, ConnectEvent, DisconnectEvent, LiveEndEvent

        async def listen():
            self._loop = asyncio.get_running_loop()
            while not self._stop.is_set():
                client = TikTokLiveClient(unique_id='@' + self.status['handle'])
                self._client = client

                @client.on(ConnectEvent)
                async def connected(event):
                    self.status.update(connected=True, message='Listening for tarot, astrology and numerology requests')

                @client.on(DisconnectEvent)
                async def disconnected(event):
                    self.status.update(connected=False)

                @client.on(LiveEndEvent)
                async def live_end(event):
                    self.live_ended()
                    await client.disconnect()

                @client.on(CommentEvent)
                async def comment(event):
                    self.ingest_event(event)

                try:
                    await client.connect()
                except Exception as exc:
                    self.status.update(connected=False, message=f'{type(exc).__name__}: check the handle and that the account is LIVE. Retrying in 15 seconds.')
                finally:
                    try:
                        await client.disconnect(close_client=True)
                    except Exception:
                        pass
                    if not self._stop.is_set():
                        self.status['connected'] = False
                        for _ in range(15):
                            if self._stop.is_set():
                                break
                            await asyncio.sleep(1)
            if not self.status['message'].startswith('LIVE ended.'):
                self.status.update(connected=False, message='Disconnected')

        asyncio.run(listen())
