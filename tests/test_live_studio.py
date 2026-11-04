import tempfile
import unittest
import hashlib
from pathlib import Path
from unittest.mock import patch
from werkzeug.security import generate_password_hash

from flask import Flask

from studio.live.live_routes import register_live_routes
from studio.live.live_studio import LiveStudio, TikTokChat


class StudioTests(unittest.TestCase):
    password_hash = generate_password_hash('test-password')

    def route_client(self):
        app = Flask(__name__, template_folder=str(Path(__file__).resolve().parents[1] / 'resources/live/templates'))
        app.config.update(TESTING=True, SECRET_KEY='test-session-key-at-least-thirty-two-characters',
                          LIVE_USERNAME='TestHost', LIVE_PASSWORD_HASH=self.password_hash,
                          LIVE_STUDIO_DB=str(self.path), LIVE_AUTH_DB=str(Path(self.temp.name) / 'auth.sqlite3'))
        register_live_routes(app, lambda job: {})
        client = app.test_client()
        with client.session_transaction() as session:
            session['live_host'] = hashlib.sha256(self.password_hash.encode()).hexdigest()
            session['live_csrf'] = 'test-csrf'
        client.environ_base['HTTP_X_LIVE_CSRF'] = 'test-csrf'
        return app, client

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'live.sqlite3'
        self.studio = LiveStudio(self.path, lambda job: {})
        self.studio.ensure_worker = lambda: None
        self.studio.settings({'interval': 270, 'approval': False, 'use_ai': False, 'use_voice': False})

    def tearDown(self):
        self.temp.cleanup()

    def test_fifo_and_cadence(self):
        self.studio.add('first', 'First question')
        self.studio.add('second', 'Second question')
        self.studio.start()
        job = self.studio.claim(1000)
        self.assertEqual(job['request']['viewer'], 'first')
        self.assertIsNone(self.studio.claim(2000))  # No overlapping generation.
        self.studio.finish(job, {'reading': 'Done'})
        self.assertIsNone(self.studio.claim(1269))
        self.assertEqual(self.studio.claim(1270)['request']['viewer'], 'second')

    def test_end_keeps_newest_and_persists_only_one_starter(self):
        for viewer in ('first', 'second', 'last'):
            self.studio.add(viewer, viewer + ' question')
        self.studio.start()
        self.studio.end()
        restored = LiveStudio(self.path, lambda job: {})
        restored.ensure_worker = lambda: None
        state = restored.snapshot()
        self.assertEqual(state['queue'], [])
        self.assertEqual(state['carry']['viewer'], 'last')
        restored.add('newcomer', 'A later question')
        restored.start()
        self.assertEqual([item['viewer'] for item in restored.snapshot()['queue']], ['last', 'newcomer'])

    def test_current_is_carried_when_nobody_waits(self):
        self.studio.add('current', 'My question')
        self.studio.start()
        job = self.studio.claim(1000)
        self.studio.finish(job, {'reading': 'Finished', 'cards': []})
        self.studio.end()
        self.assertEqual(self.studio.snapshot()['carry']['viewer'], 'current')
        self.assertEqual(self.studio.snapshot()['display']['reading'], 'Finished')

    def test_late_result_cannot_replace_new_session(self):
        self.studio.add('old', 'Old question')
        self.studio.start()
        job = self.studio.claim(1000)
        self.studio.end()
        self.studio.start()
        self.studio.finish(job, {'reading': 'Late result'})
        self.assertIsNone(self.studio.snapshot()['display'])

    def test_pending_carry_still_needs_approval(self):
        self.studio.settings({'interval': 240, 'approval': True})
        item = self.studio.add('viewer', 'Question')
        self.studio.end()
        self.studio.start()
        self.assertIsNone(self.studio.claim(1000))
        item = self.studio.snapshot()['queue'][0]
        self.studio.request_action(item['id'], 'approve')
        self.assertIsNotNone(self.studio.claim(1000))

    def test_pause_and_interval_validation(self):
        self.studio.add('viewer', 'Question')
        self.studio.start()
        self.studio.pause()
        self.assertIsNone(self.studio.claim(1000))
        self.studio.pause()
        self.assertIsNotNone(self.studio.claim(1000))
        for interval in (10, 59, 61, 179, 301):
            with self.subTest(invalid_interval=interval), self.assertRaises(ValueError):
                self.studio.settings({'interval': interval})

    def test_supported_minute_spacing(self):
        for interval in range(60, 301, 30):
            with self.subTest(interval=interval):
                engine = LiveStudio(Path(self.temp.name) / f'interval-{interval}.sqlite3', lambda job: {})
                engine.ensure_worker = lambda: None
                engine.settings({'interval': interval, 'approval': False})
                engine.add('first', 'First question')
                engine.add('second', 'Second question')
                engine.start()
                job = engine.claim(1000)
                engine.finish(job, {'reading': 'Done'})
                self.assertIsNone(engine.claim(1000 + interval - 1))
                self.assertIsNotNone(engine.claim(1000 + interval))

    def test_interval_change_uses_previous_pull_start(self):
        self.studio.add('first', 'First question')
        self.studio.add('second', 'Second question')
        self.studio.start()
        job = self.studio.claim(1000)
        self.studio.finish(job, {'reading': 'Done'})
        values = self.studio.snapshot()['settings']
        values['interval'] = 90
        self.studio.settings(values)
        self.assertEqual(self.studio.snapshot()['next_at'], 1090)
        self.assertIsNone(self.studio.claim(1089))
        self.assertIsNotNone(self.studio.claim(1090))

    def test_chat_commands_duplicate_and_closed_session(self):
        chat = TikTokChat(self.studio)
        self.assertFalse(chat.ingest('viewer', '!tarot My question'))
        self.studio.start()
        self.assertFalse(chat.ingest('viewer', 'hello everyone'))
        self.assertTrue(chat.ingest('viewer', '!tarot My question'))
        self.assertFalse(chat.ingest('viewer', '!reading Duplicate'))
        self.assertTrue(chat.ingest('another', '!reading'))
        self.assertEqual(len(self.studio.snapshot()['queue']), 2)

    def test_installed_tiktok_comment_schema(self):
        try:
            from TikTokLive.events import CommentEvent
            from TikTokLive.events.proto_events import ExtendedUser
        except ImportError:
            self.skipTest('Optional TikTok connector is not installed.')
        self.studio.start()
        chat = TikTokChat(self.studio)
        event = CommentEvent(user=ExtendedUser(display_id='schema_viewer', nickname='Viewer'), content='!tarot My question')
        self.assertTrue(chat.ingest_event(event))
        self.assertEqual(self.studio.snapshot()['queue'][0]['viewer'], 'schema_viewer')
        self.assertFalse(chat.ingest_event(CommentEvent()))

    def test_public_state_omits_unapproved_questions_and_audio(self):
        self.studio.settings({'interval': 300, 'approval': True})
        self.studio.add('secret', 'Private pending question')
        public = self.studio.snapshot(public=True)
        self.assertEqual(public['queue'], [])
        self.assertIsNone(public['carry'])

    def test_tiktok_live_end_keeps_one_and_is_idempotent(self):
        self.studio.start()
        chat = TikTokChat(self.studio)
        chat.ingest('first', '!tarot Question one')
        chat.ingest('last', '!tarot Question two')
        chat.live_ended()
        self.studio.end()
        state = self.studio.snapshot()
        self.assertFalse(state['running'])
        self.assertEqual(state['queue'], [])
        self.assertEqual(state['carry']['viewer'], 'last')

    def test_local_routes_and_json_only(self):
        app, client = self.route_client()
        with patch.dict('os.environ', {'LIVE_STUDIO_DB': str(self.path)}), patch.object(LiveStudio, 'ensure_worker'):
            self.assertEqual(client.get('/api/live/state').status_code, 200)
            self.assertEqual(client.post('/api/live/start').status_code, 415)
            self.assertEqual(client.post('/api/live/start', json={}, headers={'Origin': 'https://elsewhere.example'}).status_code, 403)
            self.assertEqual(client.get('/api/live/state', environ_overrides={'REMOTE_ADDR': '192.0.2.1'}).status_code, 403)
            with patch.dict('os.environ', {'VERCEL': '1'}):
                self.assertEqual(client.get('/api/live/state').status_code, 503)

    def test_audio_is_separate_from_state(self):
        self.studio.add('viewer', 'Question')
        self.studio.start()
        job = self.studio.claim(1000)
        self.studio.finish(job, {'reading': 'Done', 'audio_data': 'data:audio/mpeg;base64,SUQzdGVzdA==', 'has_audio': True})
        self.assertNotIn('audio_data', self.studio.snapshot(public=True)['display'])
        app, client = self.route_client()
        with patch.dict('os.environ', {'LIVE_STUDIO_DB': str(self.path)}), patch.object(LiveStudio, 'ensure_worker'):
            response = client.get('/api/live/audio/' + job['request']['id'])
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, b'ID3test')
            with self.studio.transaction() as state:
                state['display']['audio_data'] = 'data:audio/wav;base64,UklGRg=='
            response = client.get('/api/live/audio/' + job['request']['id'])
            self.assertEqual(response.mimetype, 'audio/wav')
            self.assertEqual(response.data, b'RIFF')


if __name__ == '__main__':
    unittest.main()
