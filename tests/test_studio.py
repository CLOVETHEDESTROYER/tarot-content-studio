import copy
import io
import json
import random
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from app import create_app
from studio.audio import timeline, srt, wave_info
from studio.config import ROOT
from studio.deck_catalog import deck_options
from studio.engine import create, deck, edit, redraw, settings
from studio.jobs import fingerprint
from studio.render import render_frame
from studio.store import Store, Conflict


class EngineTests(unittest.TestCase):
    def test_all_three_decks_are_complete_and_portable(self):
        self.assertTrue(all(d['ready'] for d in deck_options(ROOT)))
        for key in ('celebrity', 'esoteric-minimal', 'storybook-cartoon'):
            cards = deck(key)
            self.assertEqual(len(cards), 78)
            self.assertEqual(len({c.id for c in cards}), 78)
            self.assertTrue(all(c.image_path.is_relative_to(ROOT) and c.image_path.is_file() for c in cards))

    def test_saved_seed_recreates_cards_and_orientations(self):
        draft = create({})
        rng = random.Random(draft['seed'])
        selected = rng.sample(deck(draft['settings']['deck']), 3)
        expected = [(c.id, rng.choice(('Upright', 'Reversed'))) for c in selected]
        self.assertEqual(expected, [(c['id'], c['orientation']) for c in draft['cards']])

    def test_draws_have_no_duplicate_cards(self):
        for _ in range(30):
            draft = create({})
            self.assertEqual(len({c['id'] for c in draft['cards']}), 3)

    def test_minor_meanings_are_specific_to_the_card(self):
        from studio.engine import payload
        swords = next(c for c in deck('esoteric-minimal') if c.id == 'swords-03')
        cups = next(c for c in deck('esoteric-minimal') if c.id == 'cups-03')
        self.assertIn('heartache', payload(swords, 'Upright', 'esoteric-minimal', 0)['meaning'])
        self.assertIn('friendship', payload(cups, 'Upright', 'esoteric-minimal', 0)['meaning'])

    def test_redraw_preserves_other_card_and_script_edits(self):
        original = create({})
        original['sections'][0]['text'] = 'My edited opening.'
        original['sections'][2]['text'] = 'My edited second card.'
        changed = redraw(original, 0)
        self.assertNotEqual(changed['cards'][0]['id'], original['cards'][0]['id'])
        self.assertEqual(changed['cards'][1:], original['cards'][1:])
        self.assertEqual(changed['sections'][0], original['sections'][0])
        self.assertEqual(changed['sections'][2:], original['sections'][2:])
        self.assertEqual(len({c['id'] for c in changed['cards']}), 3)

    def test_orientation_changes_meaning_without_redrawing(self):
        original = create({})
        opposite = 'Upright' if original['cards'][0]['orientation'] == 'Reversed' else 'Reversed'
        changed = redraw(original, 0, opposite)
        self.assertEqual(original['cards'][0]['id'], changed['cards'][0]['id'])
        self.assertNotEqual(original['cards'][0]['meaning'], changed['cards'][0]['meaning'])

    def test_script_edits_cannot_replace_drawn_cards(self):
        original = create({})
        changed = edit(original, {'title': 'A new title', 'cards': []})
        self.assertEqual(changed['cards'], original['cards'])
        self.assertEqual(changed['title'], 'A new title')

    def test_invalid_script_order_and_empty_sections_are_rejected(self):
        original = create({})
        for sections in ([], original['sections'][::-1], [{**s, 'text':''} for s in original['sections']], [{**s, 'text':123} for s in original['sections']]):
            with self.assertRaises(ValueError):
                edit(original, {'sections': sections})

    def test_deck_changes_require_new_draw(self):
        original = create({})
        with self.assertRaises(ValueError):
            edit(original, {'settings':{**original['settings'],'deck':'celebrity'}})

    def test_invalid_settings_are_rejected(self):
        for bad in ({'deck':'../../secret'}, {'duration':True}, {'duration':1}, {'spread':'celtic'}, {'voice':'unknown'}, {'topic':''}, {'writer':'unknown'}):
            with self.assertRaises(ValueError): settings(bad)

    def test_fingerprint_tracks_media_changes_but_not_save_timestamp(self):
        original = create({})
        changed = copy.deepcopy(original); changed.update(revision=42,updated='tomorrow')
        self.assertEqual(fingerprint(original), fingerprint(changed))
        changed['sections'][0]['text'] += ' A new thought.'
        self.assertNotEqual(fingerprint(original), fingerprint(changed))


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'studio.sqlite3'
        self.store = Store(self.path)
    def tearDown(self): self.temp.cleanup()

    def test_reading_survives_restart_with_exact_draw(self):
        original = self.store.create(create({}))
        restored = Store(self.path).get(original['id'])
        self.assertEqual(original, restored)

    def test_archiving_a_test_draft_hides_it_without_deleting_saved_data(self):
        original = self.store.create(create({}))
        self.store.save({**original,'archived':True},1)
        self.assertEqual(self.store.list(),[])
        self.assertEqual(self.store.get(original['id'])['cards'],original['cards'])

    def test_stale_edits_cannot_overwrite_newer_revision(self):
        original = self.store.create(create({}))
        changed = edit(original, {'title':'A saved edit'})
        self.store.save(changed, 1)
        with self.assertRaises(Conflict): self.store.save(original, 1)
        self.assertEqual(self.store.get(original['id'])['title'], 'A saved edit')

    def test_restart_marks_interrupted_exports_and_keeps_completed_ones(self):
        for status in ('queued','running','done'):
            self.store.put_job(dict(id=status,draft_id='draft',created=status,status=status))
        self.store.recover()
        self.assertEqual(self.store.get_job('queued')['status'], 'failed')
        self.assertEqual(self.store.get_job('running')['status'], 'failed')
        self.assertEqual(self.store.get_job('done')['status'], 'done')

    def test_restart_rejects_invalid_completed_preview_durations(self):
        self.store.put_job(dict(id='invalid',draft_id='draft',created='today',status='done',duration=61710))
        self.store.recover()
        self.assertEqual(self.store.get_job('invalid')['status'],'failed')


class TimingAndRenderingTests(unittest.TestCase):
    def test_transcription_alignment_handles_curly_apostrophes_and_spoken_numbers(self):
        from studio.audio import align_transcribed_words
        text='Moon reflection feels gentle.\n\nToday\u2019s Metal Horse offers reflection.\n\nUniversal day 7 invites reflection.\n\nCarry this reflection forward.'
        spoken="Moon reflection feels gentle Today's Metal Horse offers reflection Universal day seven invites reflection Carry this reflection forward".split()
        events=align_transcribed_words(text,[dict(word=word,start=i*.5) for i,word in enumerate(spoken)],10)
        self.assertEqual([e['position'] for e in events], [m.start() for m in __import__('re').finditer(r'\S+',text)])
        self.assertEqual(next(e['start'] for e in events if e['text']=='Today\u2019s'),2)
        self.assertEqual(next(e['start'] for e in events if e['text']=='7'),5.5)
        draft={'sections':[dict(key=str(i),card_id=None,text=part) for i,part in enumerate(text.split('\n\n'))]}
        sections,captions=timeline(draft,events,10)
        self.assertTrue(all(s['start']<s['end'] for s in sections))
        self.assertEqual(sections[-1]['start'],7)

    def test_optional_cloud_narration_has_a_hard_deadline(self):
        import subprocess
        from studio.audio import openai_speech
        with tempfile.TemporaryDirectory() as temp, patch('studio.audio.subprocess.run',side_effect=subprocess.TimeoutExpired('speech worker',180)) as run:
            with self.assertRaisesRegex(ValueError,'within three minutes'):
                openai_speech('A short reading.','coral',Path(temp))
            self.assertEqual(run.call_args.kwargs['timeout'],180)

    def test_captions_follow_real_word_start_times_and_section_boundaries(self):
        draft={'sections':[dict(key='hook',card_id=None,text='One two three four five six seven eight nine'),dict(key='closing',card_id=None,text='The ending')]}
        text='One two three four five six seven eight nine\n\nThe ending'
        import re
        events=[dict(position=m.start(),start=i*.5) for i,m in enumerate(re.finditer(r'\S+',text))]
        sections,captions=timeline(draft,events,6)
        self.assertEqual(sections[1]['start'],4.5)
        self.assertEqual(captions[0]['start'],0)
        self.assertEqual(captions[0]['end'],3.5)
        self.assertEqual(captions[1]['start'],3.5)
        self.assertEqual(captions[-1]['end'],6)
        self.assertIn('00:00:03,500',srt(captions))

    def test_timestamps_outside_audio_or_out_of_order_cannot_be_exported(self):
        draft={'sections':[dict(key='hook',text='A short reading')]}
        for events in ([dict(position=0,start=8)], [dict(position=0,start=2),dict(position=3,start=1)]):
            with self.assertRaises(ValueError):timeline(draft,events,5)

    def test_silent_audio_is_rejected_for_narrated_exports(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'silent.wav'
            with wave.open(str(path),'wb') as audio:
                audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(24000);audio.writeframes(b'\0\0'*24000)
            with self.assertRaises(ValueError): wave_info(path)
            self.assertEqual(wave_info(path,require_voice=False),1)

    def test_streamed_wav_placeholder_length_uses_actual_samples(self):
        import struct
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'streamed.wav'
            with wave.open(str(path),'wb') as audio:
                audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(24000)
                audio.writeframes(struct.pack('<h',1000)*24000)
            content=bytearray(path.read_bytes())
            struct.pack_into('<I',content,4,0xffffffff)
            struct.pack_into('<I',content,40,0xffffffff)
            path.write_bytes(content)
            self.assertEqual(wave_info(path),1)

    def test_oversized_timeline_is_rejected_before_starting_encoder(self):
        from studio.render import encode_video
        with self.assertRaises(ValueError):
            encode_video({}, {'duration':61710},None,None,lambda *args:None)

    def test_frame_is_reproducible_and_changes_with_caption(self):
        draft=create({})
        manifest=dict(duration=10,sections=[dict(key='hook',card_id=None,start=0,end=10)],
                      captions=[dict(start=0,end=5,text='The first caption.'),dict(start=5,end=10,text='A different caption.')])
        first=render_frame(draft,manifest,2,360)
        same=render_frame(draft,manifest,2,360)
        later=render_frame(draft,manifest,7,360)
        self.assertEqual(first.size,(360,640))
        self.assertEqual(first.tobytes(),same.tobytes())
        self.assertNotEqual(first.tobytes(),later.tobytes())


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.store=Store(Path(self.temp.name)/'test.sqlite3')
        self.app=create_app(self.store,run_jobs=False)
        self.client=self.app.test_client()
        config=self.client.get('/api/config').json
        self.headers={'X-Studio-Token':config['token']}
        self.original=self.client.post('/api/readings',json={},headers=self.headers).json
    def tearDown(self): self.temp.cleanup()

    def test_production_frontend_and_local_assets_load(self):
        for url in ('/','/assets/glyph-gold.png',self.original['cards'][0]['image_url']):
            with self.client.get(url) as response:
                self.assertEqual(response.status_code,200)

    def test_saves_and_redraws_use_revision_checks(self):
        key=self.original['id']
        saved=self.client.put('/api/readings/'+key,json={'revision':1,'title':'My saved story'},headers=self.headers)
        self.assertEqual(saved.status_code,200)
        self.assertEqual(saved.json['revision'],2)
        stale=self.client.post('/api/readings/'+key+'/redraw',json={'revision':1,'index':0},headers=self.headers)
        self.assertEqual(stale.status_code,409)
        current=self.client.post('/api/readings/'+key+'/redraw',json={'revision':2,'index':0},headers=self.headers)
        self.assertEqual(current.status_code,200)
        self.assertEqual(current.json['title'],'My saved story')

    def test_cross_origin_requests_and_missing_token_are_rejected(self):
        self.assertEqual(self.client.post('/api/readings',json={}).status_code,403)
        self.assertEqual(self.client.post('/api/readings',json={},headers={**self.headers,'Origin':'https://untrusted.example'}).status_code,403)

    def test_remote_access_and_untrusted_host_are_rejected(self):
        self.assertEqual(self.client.get('/api/config',environ_base={'REMOTE_ADDR':'10.1.2.3'}).status_code,403)
        self.assertEqual(self.client.get('/api/config',headers={'Host':'untrusted.example'}).status_code,403)

    def test_malformed_input_and_invalid_cards_fail_cleanly(self):
        self.assertEqual(self.client.post('/api/readings',json=[],headers=self.headers).status_code,400)
        self.assertEqual(self.client.get('/api/artwork/esoteric-minimal/nope').status_code,404)
        self.assertEqual(self.client.get('/api/previews/not-a-key/audio').status_code,404)
        self.assertEqual(self.client.post('/api/readings/'+self.original['id']+'/export',json={'revision':1},headers=self.headers).status_code,503)

    def test_missing_readings_and_exports_return_json_errors(self):
        response=self.client.get('/api/readings/missing')
        self.assertEqual(response.status_code,404)
        self.assertIn('error',response.json)
        self.assertEqual(self.client.get('/api/exports/missing/reading.mp4').status_code,404)


if __name__=='__main__':unittest.main()
