import json
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from app import create_app
from studio.audio import macos_speech,wave_info,timeline
from studio.daily import validate_daily_settings
from studio.engine import settings
from studio.platform_support import default_voice,voice_capabilities
from studio.planner import DailyPlanner
from studio.store import Store


class PlatformTests(unittest.TestCase):
    def test_platform_defaults_cover_mac_windows_and_other_hosts(self):
        for host,voice in [('darwin','macos'),('win32','windows'),('linux','silent')]:
            with self.subTest(host=host),patch('studio.platform_support.sys.platform',host):
                self.assertEqual(default_voice(),voice)
                self.assertEqual(settings({})['voice'],voice)
                self.assertEqual(validate_daily_settings({'date':'2026-11-02'})['voice'],voice)
                self.assertEqual(voice_capabilities()['default_voice'],voice)

    def test_mac_config_exposes_free_local_voice_to_fresh_frontend(self):
        with tempfile.TemporaryDirectory() as temp,patch('studio.platform_support.sys.platform','darwin'):
            store=Store(Path(temp)/'test.sqlite3')
            client=create_app(store,run_jobs=False).test_client()
            config=client.get('/api/config').json
            self.assertTrue(config['macos']);self.assertFalse(config['windows'])
            self.assertEqual(config['default_voice'],'macos')

    def test_say_audio_keeps_measured_section_boundaries_and_character_offsets(self):
        draft={'sections':[{'key':'hook','card_id':None,'text':'A gentle beginning.'},
                           {'key':'closing','card_id':None,'text':'Take this insight forward.'}]}
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);durations=iter((1,2))
            def convert(args,**kwargs):
                seconds=next(durations)
                with wave.open(str(args[-1]),'wb') as output:
                    output.setnchannels(1);output.setsampwidth(2);output.setframerate(24000)
                    output.writeframes(b'\xe8\x03'*24000*seconds)
            with patch('studio.audio.sys.platform','darwin'),patch('studio.audio.subprocess.run',return_value=SimpleNamespace(returncode=0)) as say,patch('studio.audio.run_ffmpeg',side_effect=convert):
                raw,events,alignment=macos_speech(draft,folder)
            self.assertEqual(say.call_count,2)
            self.assertEqual(say.call_args.args[0][0],'/usr/bin/say')
            self.assertAlmostEqual(wave_info(raw),3.2)
            boundary=next(e for e in events if e['text']=='Take')
            self.assertAlmostEqual(boundary['start'],1.2)
            self.assertEqual(boundary['position'],len(draft['sections'][0]['text'])+2)
            sections,captions=timeline(draft,events,3.2)
            self.assertAlmostEqual(sections[1]['start'],1.2)
            self.assertTrue(all(c['start']<c['end'] for c in captions))
            self.assertIn('estimated word timing',alignment)

    def test_macos_voice_is_rejected_on_other_platforms(self):
        with patch('studio.audio.sys.platform','linux'):
            with self.assertRaisesRegex(ValueError,'available on a Mac'):macos_speech({},Path('.'))

    def test_native_voice_failure_does_not_create_a_silent_export(self):
        with tempfile.TemporaryDirectory() as temp,patch('studio.audio.sys.platform','darwin'),patch('studio.audio.subprocess.run',return_value=SimpleNamespace(returncode=1)):
            with self.assertRaisesRegex(ValueError,'could not start'):
                macos_speech({'sections':[{'text':'A brief reflection.'}]},Path(temp))


if __name__=='__main__':unittest.main()
