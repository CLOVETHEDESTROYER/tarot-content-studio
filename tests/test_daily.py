import copy
import json
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import MagicMock,patch
from zoneinfo import ZoneInfo
from studio.daily import create_daily,validate_daily_settings,write_daily
from studio.daily_context import edition_instant,western_context,chinese_context,numerology_context,parse_feed,saved_context
from studio.daily_visuals import gallery,visual_path
from studio.engine import edit,redraw,validate_sections
from studio.planner import DailyPlanner
from studio.store import Store
from studio.render import render_frame


class CalendarTests(unittest.TestCase):
 def test_denver_targets_follow_daylight_saving_time(self):
  before=edition_instant('2026-03-07','morning','America/Denver')
  after=edition_instant('2026-03-08','morning','America/Denver')
  self.assertEqual((after.astimezone(timezone.utc)-before.astimezone(timezone.utc)).total_seconds(),23*3600)
  before=edition_instant('2026-10-31','morning','America/Denver')
  after=edition_instant('2026-11-01','morning','America/Denver')
  self.assertEqual((after.astimezone(timezone.utc)-before.astimezone(timezone.utc)).total_seconds(),25*3600)
  self.assertEqual(edition_instant('2026-10-23','evening','America/Denver').hour,18)

 def test_chinese_year_changes_on_lunar_new_year(self):
  before=chinese_context('2026-02-16');after=chinese_context('2026-02-17')
  self.assertEqual(before['year_animal'],'Snake')
  self.assertEqual(after['year_animal'],'Horse')
  self.assertEqual(after['year_element'],'Fire')
  self.assertEqual((after['lunar_month'],after['lunar_day']),(1,1))

 def test_chinese_daily_cycle_changes_with_calendar_day(self):
  first=chinese_context('2026-10-23');second=chinese_context('2026-10-24')
  self.assertNotEqual(first['day_pillar'],second['day_pillar'])
  self.assertEqual(first['year_pillar'],second['year_pillar'])

 def test_numerology_is_reproducible_and_preserves_stated_master_numbers(self):
  self.assertEqual(numerology_context('2026-10-23')['steps'],[16,7])
  self.assertEqual(numerology_context('2026-09-19')['steps'],[29,11])
  self.assertEqual(numerology_context('2026-09-03')['number'],22)
  self.assertEqual(numerology_context('2029-09-29')['number'],33)

 def test_sky_matches_known_2024_solar_eclipse_alignment(self):
  sky=western_context(datetime(2024,4,8,18,17,tzinfo=timezone.utc))
  self.assertEqual(sky['moon_phase'],'New Moon')
  self.assertLess(sky['illumination'],1)
  delta=abs((sky['positions']['Moon']['longitude']-sky['positions']['Sun']['longitude']+180)%360-180)
  self.assertLess(delta,1)

 def test_missing_or_invalid_calendar_inputs_are_rejected(self):
  for day,slot,zone in [('2026-02-30','morning','America/Denver'),('2026-10-23','noon','UTC'),('2026-10-23','morning','bad-zone'),('2200-01-01','morning','UTC')]:
   with self.assertRaises(ValueError):edition_instant(day,slot,zone)


class NewsTests(unittest.TestCase):
 def test_only_timestamped_headlines_before_cutoff_and_within_36_hours(self):
  data=b'''<rss><channel>
   <item><title>Current &amp; sourced</title><link>https://example.org/current</link><pubDate>Fri, 23 Oct 2026 11:00:00 GMT</pubDate></item>
   <item><title>Future</title><link>https://example.org/future</link><pubDate>Fri, 23 Oct 2026 13:00:00 GMT</pubDate></item>
   <item><title>Stale</title><link>https://example.org/old</link><pubDate>Tue, 20 Oct 2026 12:00:00 GMT</pubDate></item>
   <item><title>No timestamp</title><link>https://example.org/none</link></item>
   </channel></rss>'''
  found=parse_feed(data,'Example publisher',datetime(2026,10,23,12,tzinfo=timezone.utc))
  self.assertEqual([h['title'] for h in found],['Current & sourced'])
  self.assertEqual(found[0]['publisher'],'Example publisher')

 def test_xml_entities_and_oversized_feeds_are_rejected(self):
  for data in (b'<!DOCTYPE rss [<!ENTITY x SYSTEM "file:///etc/passwd">]><rss/>',b'x'*1_000_001):
   with self.assertRaises(ValueError):parse_feed(data,'Test',datetime.now(timezone.utc))


class DailyFlowTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)
  self.patch=patch('studio.daily_context.DATA',self.path);self.patch.start()
 def tearDown(self):self.patch.stop();self.temp.cleanup()
 def make(self,kind='combined',**kwargs):
  return create_daily(dict(daily=True,reading_type=kind,date='2026-10-23',edition='morning',voice='silent',**kwargs))

 def test_each_flow_has_only_its_selected_reading_system(self):
  for kind in ('tarot','western','chinese','numerology'):
   reading=self.make(kind)
   self.assertEqual({c['kind'] for c in reading['cards']},{kind})
   validate_sections(reading['sections'])
   text=' '.join(s['text'] for s in reading['sections']).lower()
   self.assertNotIn('your question',text)

 def test_combined_flow_can_use_any_two_or_all_four_systems(self):
  reading=self.make(components=['western','numerology'])
  self.assertEqual({c['kind'] for c in reading['cards']},{'western','numerology'})
  self.assertEqual(len(self.make()['cards']),4)
  with self.assertRaises(ValueError):self.make(components=['tarot'])

 def test_long_two_system_editions_have_enough_spoken_content(self):
  reading=self.make(components=['tarot','western'],duration=90)
  self.assertGreaterEqual(sum(len(s['text'].split()) for s in reading['sections']),160)

 def test_same_daily_slot_has_stable_draw_and_evening_changes_the_frame(self):
  a=self.make();b=self.make()
  self.assertEqual(a['cards'],b['cards']);self.assertEqual(a['seed'],b['seed'])
  pm=create_daily({**a['settings'],'edition':'evening'})
  self.assertNotEqual(a['seed'],pm['seed'])
  self.assertEqual(a['context']['numerology'],pm['context']['numerology'])
  self.assertIn('reflect',pm['sections'][0]['text'].lower())
  self.assertNotEqual(a['context']['western']['positions']['Moon']['longitude'],pm['context']['western']['positions']['Moon']['longitude'])

 def test_rewriting_reuses_saved_context_and_cards(self):
  reading=self.make('western');before=copy.deepcopy(reading['context'])
  sections,source=write_daily(reading['cards'],reading['settings'],reading['context'])
  self.assertEqual(reading['context'],before)
  self.assertEqual([s['card_id'] for s in sections],[s['card_id'] for s in reading['sections']])

 def test_ai_writer_receives_selected_systems_and_enforces_news_attribution(self):
  reading=self.make('numerology');context=reading['context']
  used=dict(title='A sourced headline',publisher='UN News',url='https://example.org/used',published='2026-10-23T11:00:00+00:00')
  unused={**used,'title':'Unselected headline','url':'https://example.org/unused'}
  context['news'].update(enabled=True,headlines=[used,unused])
  config={**reading['settings'],'include_news':True,'news_selection':[0],'writer':'openai'}
  from studio.daily import cards_for
  cards=cards_for(config,context,reading['seed'])
  client=MagicMock();client.responses.create.return_value.output_text=json.dumps({**{'hook':'What needs attention on October 23?','closing':'A reflective sentence.'},**{f'card_{i}':'A reflective sentence.' for i in range(len(cards))}})
  with patch('studio.daily.api_client',return_value=client):sections,_=write_daily(cards,config,context)
  supplied=json.loads(client.responses.create.call_args.kwargs['input'])['context']
  self.assertNotIn('western',supplied);self.assertNotIn('chinese',supplied)
  self.assertEqual(supplied['news'],[used])
  self.assertIn('From UN News: A sourced headline',sections[-2]['text'])

 def test_calculated_cards_cannot_be_randomly_redrawn(self):
  with self.assertRaises(ValueError):redraw(self.make('numerology'),0)
  reading=self.make();changed=redraw(reading,0)
  self.assertNotEqual(reading['cards'][0]['id'],changed['cards'][0]['id'])
  self.assertEqual(reading['cards'][1:],changed['cards'][1:])
  self.assertEqual(reading['context'],changed['context'])

 def test_changing_date_requires_a_new_edition(self):
  reading=self.make()
  with self.assertRaises(ValueError):edit(reading,{'settings':{**reading['settings'],'date':'2026-10-24'}})
  changed=edit(reading,{'settings':{**reading['settings'],'voice':'windows'}})
  self.assertEqual(changed['cards'],reading['cards'])

 def test_context_snapshot_must_match_date_timezone_and_news_choice(self):
  reading=self.make()
  config=reading['settings'];key=reading['context']['id']
  self.assertEqual(saved_context(key,config)['id'],key)
  with self.assertRaises(ValueError):saved_context(key,{**config,'edition':'evening'})
  with self.assertRaises(ValueError):saved_context('../secret',config)

 def test_daily_frame_is_real_art_and_reproducible(self):
  reading=self.make('numerology',style='storybook-cartoon')
  manifest=dict(duration=5,sections=[dict(key='hook',start=0,end=5,card_id=None)],captions=[dict(start=0,end=5,text='A little space to reflect.')])
  a=render_frame(reading,manifest,1,360);b=render_frame(reading,manifest,1,360)
  self.assertEqual(a.size,(360,640));self.assertEqual(a.tobytes(),b.tobytes())


class VisualTests(unittest.TestCase):
 def test_both_collections_have_all_36_individual_cards(self):
  from PIL import Image
  import hashlib
  for style in ('esoteric-minimal','storybook-cartoon'):
   cards=gallery(style);self.assertEqual(len(cards),36)
   self.assertTrue(all(c['ready'] for c in cards))
   self.assertEqual({family:sum(c['family']==family for c in cards) for family in ('western','chinese','numerology')},{'western':12,'chinese':12,'numerology':12})
   hashes=[]
   for card in cards:
    path=visual_path(style,card['family'],card['key'])
    with Image.open(path) as image:self.assertEqual(image.size,(512,768))
    hashes.append(hashlib.sha256(path.read_bytes()).hexdigest())
   self.assertEqual(len(set(hashes)),36)

 def test_unknown_styles_and_visual_traversal_are_rejected(self):
  for args in [('bad','western','aries'),('esoteric-minimal','western','../secret'),('storybook-cartoon','unknown','7')]:
   with self.assertRaises(ValueError):visual_path(*args)


class PlannerTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.store=Store(Path(self.temp.name)/'db.sqlite3')
  self.jobs=MagicMock();self.planner=DailyPlanner(self.store,self.jobs,start=False)
 def tearDown(self):self.planner.pool.shutdown(wait=True);self.temp.cleanup()

 def test_defaults_are_denver_six_am_and_six_pm_and_no_publishing(self):
  slots=self.planner.upcoming(datetime(2026,10,23,10,tzinfo=timezone.utc),days=1)
  self.assertEqual([datetime.fromisoformat(s['target']).hour for s in slots],[6,18])
  self.assertFalse(self.planner.config()['enabled'])
  self.assertIn('not connected',self.planner.snapshot()['publishing'])

 def test_duplicate_prepare_calls_claim_only_one_edition(self):
  with patch.object(self.planner.pool,'submit') as submit:
   a=self.planner.prepare('2026-10-23','morning')
   b=self.planner.prepare('2026-10-23','morning')
   self.assertEqual(a['id'],b['id']);self.assertEqual(submit.call_count,1)

 def test_automatic_generation_uses_the_preparation_window(self):
  self.planner.save({'enabled':True})
  with patch.object(self.planner,'prepare') as prepare:
   self.planner.tick(datetime(2026,10,23,5,20,tzinfo=ZoneInfo('America/Denver')))
   prepare.assert_not_called()
   self.planner.tick(datetime(2026,10,23,5,31,tzinfo=ZoneInfo('America/Denver')))
   prepare.assert_called_once_with('2026-10-23','morning')

 def test_restart_preserves_settings_and_recovers_interrupted_preparation(self):
  self.planner.save({'morning_type':'numerology','evening_type':'western'})
  with patch.object(self.planner.pool,'submit'):entry=self.planner.prepare('2026-10-23','morning')
  next_planner=DailyPlanner(self.store,self.jobs,start=False)
  try:
   self.assertEqual(next_planner.config()['morning_type'],'numerology')
   self.assertEqual(next_planner.entries()[0]['status'],'failed')
  finally:next_planner.pool.shutdown(wait=True)

 def test_retry_keeps_the_existing_draft_type_when_planner_defaults_change(self):
  self.planner.save({'morning_type':'numerology'})
  with patch.object(self.planner.pool,'submit'):
   entry=self.planner.prepare('2026-10-23','morning')
   entry.update(status='failed',draft_id='existing-saved-draft');self.planner.put(entry)
   self.planner.save({'morning_type':'combined'})
   retried=self.planner.prepare('2026-10-23','morning',retry=True)
  self.assertEqual(retried['reading_type'],'numerology')
  self.assertEqual(retried['settings']['reading_type'],'numerology')


class DailyRouteTests(unittest.TestCase):
 def setUp(self):
  from app import create_app
  self.temp=tempfile.TemporaryDirectory();self.patch=patch('studio.daily_context.DATA',Path(self.temp.name));self.patch.start()
  self.store=Store(Path(self.temp.name)/'routes.sqlite3');self.app=create_app(self.store,run_jobs=False)
  self.client=self.app.test_client();self.headers={'X-Studio-Token':self.client.get('/api/config').json['token']}
 def tearDown(self):self.patch.stop();self.temp.cleanup()

 def test_review_generate_rewrite_and_reopen_daily_reading(self):
  settings=dict(daily=True,reading_type='western',date='2026-10-23',edition='evening',voice='silent')
  response=self.client.post('/api/daily/context',json=settings,headers=self.headers);self.assertEqual(response.status_code,200)
  context=response.json
  response=self.client.post('/api/readings',json={**settings,'context_id':context['id']},headers=self.headers);self.assertEqual(response.status_code,201)
  original=response.json;key=original['id']
  rewritten=self.client.post('/api/readings/'+key+'/rewrite',json={'revision':1},headers=self.headers)
  self.assertEqual(rewritten.status_code,200);self.assertEqual(rewritten.json['context'],context)
  self.assertEqual(self.client.get('/api/readings/'+key).json['cards'],original['cards'])
  self.assertEqual(self.client.get('/api/poster/'+key).status_code,200)

 def test_gallery_artwork_and_invalid_daily_requests(self):
  cards=self.client.get('/api/daily/cards?style=storybook-cartoon').json['cards'];self.assertEqual(len(cards),36)
  with self.client.get(cards[0]['image_url']) as response:self.assertEqual(response.mimetype,'image/png')
  self.assertEqual(self.client.post('/api/daily/context',json={'date':'invalid'},headers=self.headers).status_code,400)
  self.assertEqual(self.client.post('/api/readings',json={'daily':True,'reading_type':'combined','components':['tarot']},headers=self.headers).status_code,400)


if __name__=='__main__':unittest.main()
