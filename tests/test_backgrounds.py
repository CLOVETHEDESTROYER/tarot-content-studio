import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
from PIL import Image
from app import create_app
from studio.backgrounds import BACKGROUNDS,canvas,image_path,selected
from studio.engine import create,edit
from studio.daily import create_daily
from studio.jobs import fingerprint
from studio.store import Store
from studio.agent_jobs import validate_request,request_items
from studio.render import render_frame


class BackgroundTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.folder=Path(self.temp.name)
        self.context=patch('studio.daily_context.DATA',self.folder);self.context.start()
        self.store=Store(self.folder/'studio.sqlite3');self.app=create_app(self.store,run_jobs=False)
        self.client=self.app.test_client()
    def tearDown(self):self.context.stop();self.temp.cleanup()

    def test_all_bundled_backgrounds_have_real_art_and_thumbnails(self):
        for key in BACKGROUNDS:
            with Image.open(image_path(key,True)) as im:self.assertEqual(im.size,(180,320))
            self.assertEqual(canvas(key).size,(1080,1920))
            if key!='solid':
                with Image.open(image_path(key)) as im:self.assertGreater(im.height,1500)
        with self.assertRaises(ValueError):selected(dict(background='../private'))

    def test_changing_background_preserves_cards_and_script_but_changes_render_and_cache(self):
        reading=create_daily(dict(date='2026-11-05',reading_type='combined',voice='silent',writer='local'))
        original=copy.deepcopy(reading);changed=edit(reading,dict(settings={**reading['settings'],'background':'garden'}))
        self.assertEqual(changed['cards'],original['cards']);self.assertEqual(changed['sections'],original['sections'])
        self.assertEqual(changed['context'],original['context']);self.assertNotEqual(fingerprint(original),fingerprint(changed))
        manifest=dict(duration=1,sections=[dict(key='hook',start=0,end=1,card_id=None)],captions=[])
        a=render_frame(original,manifest,0,360);b=render_frame(changed,manifest,0,360)
        self.assertNotEqual(a.tobytes(),b.tobytes())
        self.assertEqual(b.tobytes(),render_frame(changed,manifest,0,360).tobytes())

    def test_poster_preview_is_immediate_and_does_not_save_unsaved_changes(self):
        reading=self.store.create(create(dict(voice='silent',writer='local')))
        url='/api/poster/'+reading['id']
        solid=self.client.get(url);illustrated=self.client.get(url+'?background=aurora')
        self.assertEqual(illustrated.status_code,200);self.assertNotEqual(solid.data,illustrated.data)
        self.assertEqual(self.store.get(reading['id']),reading)
        self.assertEqual(self.client.get(url+'?background=unknown').status_code,400)
        for bg in self.client.get('/api/config').json['backgrounds']:
            response=self.client.get(bg['thumbnail']);self.assertEqual(response.status_code,200);response.close()
        self.assertEqual(self.client.get('/api/backgrounds/unknown').status_code,404)

    def test_muse_background_is_optional_preserving_old_payloads_and_new_settings(self):
        value=dict(schemaVersion=1,kind='reading-week',requestId='background-week',brief='Daily series',startDate='2026-11-05',days=1)
        self.assertNotIn('background',validate_request(value))
        enhanced=validate_request({**value,'background':'dawn'})
        self.assertTrue(all(i['settings']['background']=='dawn' for i in request_items(enhanced)))
        with self.assertRaises(ValueError):validate_request({**value,'background':'unknown'})

    def test_live_background_is_saved_and_gateway_serves_only_known_art(self):
        from studio.live.live_studio import LiveStudio
        from studio.live.gateway import create_gateway
        live=LiveStudio(self.folder/'live-studio.sqlite3',None)
        live.settings(dict(background='celestial',use_ai=False,use_voice=False))
        self.assertEqual(live.snapshot(public=True)['settings']['background'],'celestial')
        (self.folder/'live-session.key').write_text('test-background-secret')
        gateway=create_gateway(self.folder).test_client()
        response=gateway.get('/api/backgrounds/celestial');self.assertEqual(response.status_code,200);response.close()
        self.assertEqual(gateway.get('/api/backgrounds/private').status_code,404)
        self.assertEqual(gateway.post('/api/backgrounds/celestial').status_code,404)
        self.assertEqual(gateway.get('/api/config').status_code,404)

    def test_old_planner_slots_reuse_their_classic_background_without_conflicts(self):
        from studio.planner import DailyPlanner
        planner=DailyPlanner(self.store,MagicMock())
        planner.pool.shutdown();planner.pool=MagicMock()
        entry=planner.prepare('2026-11-05','morning')
        entry['settings'].pop('background');planner.put(entry)
        reused=planner.prepare('2026-11-05','morning',settings_override=entry['settings'])
        self.assertEqual(reused['id'],entry['id']);self.assertEqual(planner.pool.submit.call_count,1)
        with self.assertRaisesRegex(ValueError,'different saved edition'):
            planner.prepare('2026-11-05','morning',settings_override={**entry['settings'],'background':'garden'})


if __name__=='__main__':unittest.main()
