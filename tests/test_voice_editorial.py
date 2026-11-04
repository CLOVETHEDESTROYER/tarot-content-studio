import copy
import io
import json
import tempfile
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock,patch
from studio.voice_direction import OPENAI_VOICES,presentation,direction,speech_options
from studio.voice_samples import create_sample,sample_path
from studio.daily import create_daily,write_daily
from studio.engine import settings
from studio.jobs import fingerprint
from studio.agent_jobs import validate_request


def audio_bytes():
    output=io.BytesIO()
    with wave.open(output,'wb') as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(24000)
        wav.writeframes(b'\x00\x10\x00\xf0'*36000)
    return output.getvalue()


class VoiceEditorialTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.data=patch('studio.daily_context.DATA',self.root);self.data.start()
    def tearDown(self):self.data.stop();self.temp.cleanup()

    def test_all_voices_and_delivery_settings_validate_and_change_audio_identity(self):
        for voice in OPENAI_VOICES:self.assertEqual(settings({'voice':'openai-'+voice})['voice'],'openai-'+voice)
        for key,value in (('voice_style','robot'),('voice_energy','extreme')):
            with self.assertRaises(ValueError):settings({key:value})
        reading=create_daily(dict(date='2026-11-05',reading_type='western',voice='openai-marin',writer='local'))
        changed=copy.deepcopy(reading);changed['settings']['voice_style']='uplifting'
        self.assertNotEqual(fingerprint(reading),fingerprint(changed))
        self.assertIn('pitch',direction('uplifting','high'))

    def test_style_prompt_is_separate_from_spoken_text_and_legacy_models_are_supported(self):
        directed=speech_options('gpt-4o-mini-tts','cedar','mystical','expressive')
        self.assertIn('instructions',directed);self.assertNotIn('input',directed)
        self.assertNotIn('instructions',speech_options('tts-1','nova'))
        with self.assertRaises(ValueError):speech_options('tts-1','marin')

    def test_sample_cache_tracks_voice_and_direction_without_repeated_api_charges(self):
        client=MagicMock();client.with_options.return_value.audio.speech.create.return_value.content=audio_bytes()
        with patch('studio.voice_samples.DATA',self.root),patch('studio.voice_samples.api_client',return_value=client):
            first=create_sample(dict(voice='openai-marin',voice_style='uplifting',voice_energy='high'))
            again=create_sample(dict(voice='openai-marin',voice_style='uplifting',voice_energy='high'))
            changed=create_sample(dict(voice='openai-marin',voice_style='grounded'))
            self.assertFalse(first['cached']);self.assertTrue(again['cached'])
            self.assertEqual(first['url'],again['url']);self.assertNotEqual(first['url'],changed['url'])
            self.assertEqual(client.with_options.return_value.audio.speech.create.call_count,2)
            self.assertIn('instructions',client.with_options.return_value.audio.speech.create.call_args.kwargs)
            with self.assertRaises(ValueError):create_sample(dict(voice='windows'))
            with self.assertRaises(ValueError):sample_path('../private')

    def test_export_speech_requests_include_actual_delivery_instructions(self):
        from studio.audio import openai_speech_request
        client=MagicMock();client.with_options.return_value.audio.speech.create.return_value.content=audio_bytes()
        client.with_options.return_value.audio.transcriptions.create.return_value.words=[SimpleNamespace(word='A',start=0),SimpleNamespace(word='reading',start=.3)]
        with patch('studio.audio.api_client',return_value=client):
            openai_speech_request('A reading','cedar',self.root,'uplifting','high')
        args=client.with_options.return_value.audio.speech.create.call_args.kwargs
        self.assertEqual(args['input'],'A reading');self.assertIn('enthusiastic',args['instructions']);self.assertEqual(args['voice'],'cedar')

    def test_every_day_has_a_dated_brief_and_the_correct_changing_facts(self):
        for kind in ('western','chinese','numerology','combined'):
            first=create_daily(dict(date='2026-11-05',reading_type=kind,voice='silent',writer='local'))
            second=create_daily(dict(date='2026-11-06',reading_type=kind,voice='silent',writer='local'))
            for reading in (first,second):
                brief=reading['editorial_brief'];self.assertEqual(brief['target_date'],reading['settings']['date'])
                self.assertIn('2026',reading['sections'][0]['text']);self.assertNotIn('Good morning',reading['sections'][0]['text'])
                self.assertTrue(brief['fact_anchors'])
            self.assertNotEqual(first['sections'],second['sections'])
            self.assertNotEqual(first['editorial_brief']['everyday_situation'],second['editorial_brief']['everyday_situation'])

    def test_fast_cloud_narration_does_not_leave_a_long_silent_tail(self):
        from studio.audio import prepare_audio
        reading=create_daily(dict(date='2026-11-05',reading_type='numerology',voice='openai-marin',writer='local',duration=60))
        raw=self.root/'raw.wav';raw.write_bytes(audio_bytes())
        events=[dict(start=0,position=0,length=1,text='A')]
        with patch('studio.audio.openai_speech',return_value=(raw,events,'Test')),patch('studio.audio.wave_info',return_value=1.5),patch('studio.audio.run_ffmpeg') as encode:
            _,_,duration,_,_=prepare_audio(reading,self.root)
        self.assertLess(duration,10)
        args=encode.call_args.args[0];self.assertIn('atempo=0.95000000,apad',args)

    def test_ai_writer_gets_publication_date_facts_and_specific_editorial_direction(self):
        reading=create_daily(dict(date='2027-02-15',reading_type='chinese',voice='silent',writer='local'))
        client=MagicMock();client.responses.create.return_value.output_text=json.dumps({s['key'].replace('-','_'):('What needs a clearer question on February 15?' if i==0 else 'A concrete spoken sentence.') for i,s in enumerate(reading['sections'])})
        with patch('studio.daily.api_client',return_value=client):write_daily(reading['cards'],{**reading['settings'],'writer':'openai'},reading['context'])
        args=client.responses.create.call_args.kwargs;payload=json.loads(args['input'])
        self.assertEqual(payload['editorial_brief']['target_date'],'2027-02-15')
        self.assertIn(reading['context']['chinese']['day_animal'],payload['editorial_brief']['fact_anchors'][0]['fact'])
        self.assertIn('not the whole reading',args['instructions']);self.assertIn('publication date',args['instructions'])
        self.assertNotIn('western',payload['context'])

    def test_long_or_undated_scripts_are_revised_once_then_rejected_if_still_invalid(self):
        reading=create_daily(dict(date='2026-11-05',reading_type='numerology',voice='silent',writer='local'))
        client=MagicMock();bad=dict(hook='November 5: '+('word '*200),card_0='One thought.',closing='One action.')
        good=dict(hook='What needs your attention on November 5?',card_0='A concrete spoken sentence.',closing='Ask one clear question.')
        client.responses.create.side_effect=[SimpleNamespace(output_text=json.dumps(x)) for x in (bad,good)]
        with patch('studio.daily.api_client',return_value=client):
            result,_=write_daily(reading['cards'],{**reading['settings'],'writer':'openai'},reading['context'])
        self.assertEqual(result[0]['text'],good['hook']);self.assertEqual(client.responses.create.call_count,2)
        self.assertIn('required_corrections',json.loads(client.responses.create.call_args.kwargs['input']))
        client.responses.create.side_effect=None;client.responses.create.return_value.output_text=json.dumps(bad)
        with patch('studio.daily.api_client',return_value=client),self.assertRaisesRegex(ValueError,'length checks'):
            write_daily(reading['cards'],{**reading['settings'],'writer':'openai'},reading['context'])

    def test_date_must_appear_in_opening_and_each_section_has_a_budget(self):
        from studio.editorial import section_plan,script_issues
        plan=section_plan([dict(label=x) for x in ('Opening','Moon','Closing')],120)
        self.assertEqual(sum(s['target_words'] for s in plan),120)
        self.assertTrue(script_issues(['November 6: a question.','A thought.','An action.'],plan,120,'2026-11-05'))
        self.assertFalse(script_issues(['What can shift on November 5?','A thought.','An action.'],plan,120,'2026-11-05'))

    def test_legacy_muse_request_identity_is_preserved_and_optional_delivery_propagates(self):
        value=dict(schemaVersion=1,kind='reading-week',requestId='voice-week',brief='Readings',startDate='2026-11-05',days=1)
        old=validate_request(value);self.assertNotIn('voice_style',old);self.assertNotIn('voice_energy',old)
        enhanced=validate_request({**value,'voice':'openai-cedar','voice_style':'mystical','voice_energy':'high'})
        self.assertEqual(enhanced['voice_style'],'mystical')
        from studio.agent_jobs import request_items
        self.assertTrue(all(i['settings']['voice_energy']=='high' for i in request_items(enhanced)))


if __name__=='__main__':unittest.main()
