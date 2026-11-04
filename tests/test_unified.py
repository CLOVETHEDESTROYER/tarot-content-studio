import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit
from app import create_app
from studio.store import Store
from studio.daily_context import build_context
from studio.live.integration import generate_live
from studio.live.live_studio import LiveStudio,TikTokChat
from studio.live.gateway import create_gateway
from studio.agent_jobs import validate_request,request_items
from studio.planner import DailyPlanner


class UnifiedTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.store=Store(self.root/'studio.sqlite3');self.app=create_app(self.store,run_jobs=False)
        self.client=self.app.test_client()
    def tearDown(self):self.temp.cleanup()

    def live_csrf(self):
        response=self.client.get('/live');self.assertEqual(response.status_code,200,response.data[:300])
        return re.search(rb'name="live-csrf" content="([^"]+)"',response.data)[1].decode()

    def test_both_implementations_share_one_server_and_artwork(self):
        self.assertEqual(self.client.get('/').status_code,200)
        self.live_csrf()
        self.assertEqual(self.client.get('/card-library').status_code,200)
        self.assertEqual(self.client.get('/api/deck').status_code,200)
        token=self.client.get('/api/config').json['token']
        result=self.client.post('/api/deal',json=dict(spread='celtic',use_ai=False,use_voice=False),headers={'X-Studio-Token':token})
        self.assertEqual(result.status_code,200,result.data[:300]);self.assertEqual(len(result.json['cards']),10)
        image=result.json['cards'][0]['image_url'];self.assertEqual(self.client.get(image).status_code,200)

    def test_live_mutations_require_live_csrf_and_origin(self):
        csrf=self.live_csrf()
        self.assertEqual(self.client.post('/api/live/request',json=dict(viewer='one',question='Focus?')).status_code,403)
        response=self.client.post('/api/live/request',json=dict(viewer='one',question='Focus?',reading_type='western'),headers={'X-Live-CSRF':csrf})
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(self.client.get('/api/live/state').json['queue'][0]['reading_type'],'western')
        self.assertEqual(self.client.post('/api/live/request',json={},headers={'X-Live-CSRF':csrf,'Origin':'https://elsewhere.example'}).status_code,403)

    def test_date_readings_use_shared_facts_artwork_and_library(self):
        for kind in ('western','chinese','numerology','combined','tarot'):
            job=dict(request=dict(id=kind,viewer='viewer',question='What should I focus on?',reading_type=kind,reading_date='2026-11-04'),
                     settings=dict(spread='one',deck='esoteric-minimal',use_ai=False,use_voice=False,reading_type='tarot',style='storybook-cartoon',timezone='America/Denver'))
            result=generate_live(job,self.store)
            self.assertEqual(result['reading_type'],kind);self.assertEqual(result['reading_date'],'2026-11-04')
            self.assertTrue(result['reading']);self.assertTrue(result['cards']);self.assertFalse(result['has_audio'])
            saved=self.store.get(result['reading_id']);self.assertEqual(saved['live']['reading_type'],kind)
            for card in result['cards']:self.assertEqual(self.client.get(card['image_url']).status_code,200)
            if kind!='tarot':self.assertEqual(saved['context']['date'],'2026-11-04')

    def test_read_only_gateway_keeps_editor_and_host_private(self):
        self.live_csrf();state=self.client.get('/api/live/state').json
        ticket_url=state['overlay_url'];gateway=create_gateway(self.root);gateway.testing=True;client=gateway.test_client()
        remote={'REMOTE_ADDR':'192.0.2.1','wsgi.url_scheme':'https'}
        self.assertEqual(client.get('/api/live/state?public=1',environ_overrides=remote).status_code,401)
        query=urlsplit(ticket_url).query
        self.assertEqual(client.get('/api/live/state?public=1&'+query,environ_overrides=remote).status_code,200)
        for path in ('/','/live','/live/login','/api/config','/api/agent','/api/readings','/api/live/state'):
            self.assertEqual(client.get(path,environ_overrides=remote).status_code,404,path)
        self.assertEqual(client.post('/api/live/start',json={},environ_overrides=remote).status_code,404)
        self.assertEqual(client.get('/api/daily/artwork/esoteric-minimal/western/aries',environ_overrides=remote).status_code,200)
        csrf=self.live_csrf();self.client.post('/api/live/rotate-overlay',json={},headers={'X-Live-CSRF':csrf})
        self.assertEqual(client.get('/api/live/state?public=1&'+query,environ_overrides=remote).status_code,401)

    def test_chat_commands_keep_request_type_and_approval(self):
        engine=self.app.extensions['live_bootstrap']();chat=TikTokChat(engine)
        with patch.object(engine,'ensure_worker'):engine.start()
        for viewer,command,kind in [('a','!western','western'),('b','!chinese','chinese'),('c','!numerology','numerology'),('d','!tarot','tarot')]:
            self.assertTrue(chat.ingest(viewer,command+' My focus today?'))
        self.assertEqual([r['reading_type'] for r in engine.snapshot()['queue']],['western','chinese','numerology','tarot'])
        self.assertTrue(all(r['status']=='pending' for r in engine.snapshot()['queue']))
        self.assertIsNone(engine.claim());engine.end()

    def test_weekly_three_series_have_unique_reservations(self):
        request=validate_request(dict(schemaVersion=1,kind='reading-week',requestId='three-series',brief='Three readings each day',startDate='2026-11-04',days=7,editions=['morning'],readingTypes=['western','chinese','numerology'],writer='local',voice='silent'))
        items=request_items(request);self.assertEqual(len(items),21)
        planner=DailyPlanner(self.store,None,start=False)
        try:
            with patch.object(planner.pool,'submit') as submit:
                entries=[planner.prepare(i['date'],i['edition'],settings_override=i['settings']) for i in items]
                self.assertEqual(len({e['id'] for e in entries}),21)
                for item in items:planner.prepare(item['date'],item['edition'],settings_override=item['settings'])
                self.assertEqual(submit.call_count,21)
        finally:planner.pool.shutdown(wait=True)


if __name__=='__main__':unittest.main()
