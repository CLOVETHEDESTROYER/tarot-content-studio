import copy
import json
import tempfile
import unittest
import uuid
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from studio.agent_jobs import AgentJobs,canonical,checksum,inside,request_items,validate_request
from studio.planner import DailyPlanner
from studio.store import Store,Conflict


def request(key='week-one',**changes):
    return dict(schemaVersion=1,kind='reading-week',requestId=key,brief='Collective readings for the week.',startDate='2026-11-04',days=1,
                editions=['morning','evening'],morningType='numerology',eveningType='tarot',voice='silent',writer='local',duration=30,**changes)


class RequestValidationTests(unittest.TestCase):
    def test_seven_days_produce_exactly_fourteen_calendar_slots_and_dst_offsets(self):
        value=request();value.update(days=7,startDate='2026-10-29')
        items=request_items(validate_request(value))
        self.assertEqual(len(items),14)
        self.assertEqual(items[0]['target'],'2026-10-29T06:00:00-06:00')
        self.assertEqual(items[-1]['target'],'2026-11-04T18:00:00-07:00')
        self.assertEqual(len({(s['date'],s['edition']) for s in items}),14)

    def test_rejects_arbitrary_fields_bad_ids_counts_and_future_news(self):
        for changes in ({'command':'run shell'},{'requestId':'../escape'},{'requestId':'CON'},{'days':8},{'days':True},{'days':7,'includeNews':True},{'editions':['morning','morning']},{'morningType':'unknown'}):
            value=request();value.update(changes)
            with self.subTest(changes=changes),self.assertRaises((ValueError,TypeError)):validate_request(value)


class AgentHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.folder=Path(self.temp.name)
        self.store=Store(self.folder/'data.sqlite3');self.jobs_count=0
        self.patches=[patch('studio.daily_context.DATA',self.folder/'data'),patch('studio.agent_jobs.DATA',self.folder/'data'),
                      patch('studio.agent_jobs.EXPORTS',self.folder/'exports'),patch('studio.agent_jobs.time.sleep',return_value=None)]
        for p in self.patches:p.start()
        self.jobs=SimpleNamespace(submit=self.render)
        self.planner=DailyPlanner(self.store,self.jobs,start=False)
        self.inline=patch.object(self.planner.pool,'submit',side_effect=lambda fn,*args:fn(*args));self.inline.start()
        self.agent=AgentJobs(self.store,self.planner,self.jobs,start=False)
        self.queue=patch.object(self.agent.pool,'submit');self.queued=self.queue.start()
        self.agent.save({'folder':str(self.folder/'exchange'),'enabled':False})

    def tearDown(self):
        self.queue.stop();self.inline.stop();self.agent.pool.shutdown(wait=True);self.planner.pool.shutdown(wait=True)
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()

    def render(self,draft,kind):
        self.jobs_count+=1;key=uuid.uuid4().hex;folder=self.folder/'exports'/key;folder.mkdir(parents=True)
        names=['reading.mp4','caption.txt','reading.json','context.json','sources.txt']
        for name in names:(folder/name).write_bytes((name+' '+draft['id']).encode())
        job=dict(id=key,kind=kind,draft_id=draft['id'],revision=draft['revision'],created='now',status='done',progress=100,files=names)
        self.store.put_job(job);return job

    def complete(self,data=None):
        value=data or request();self.agent.submit(value);self.agent.work(value['requestId']);return self.agent.get(value['requestId'])

    def test_metadata_and_examples_are_prepared_without_submitting_jobs(self):
        root=self.folder/'exchange'
        self.assertEqual(self.queued.call_count,0)
        for name in ('Requests','Status','Ready','Reports','Examples'):self.assertTrue((root/name).is_dir())
        info=json.loads((root/'studio-info.json').read_text())
        self.assertEqual(info['catalogSHA256'],checksum(root/'catalog.json'))
        self.assertFalse(self.agent.config()['enabled'])

    def test_zenwave_exchange_is_rejected_without_changing_its_files(self):
        root=self.folder/'zenwave';root.mkdir();sentinel='{"schemaVersion":1,"manifestations":[]}'
        (root/'catalog.json').write_text(sentinel)
        with self.assertRaisesRegex(ValueError,'another studio'):self.agent.prepare_exchange(str(root))
        self.assertEqual((root/'catalog.json').read_text(),sentinel)
        self.assertFalse((root/'AGENT-INSTRUCTIONS.md').exists())

    def test_request_replay_is_idempotent_and_changed_payload_is_rejected(self):
        self.agent.submit(request());self.agent.submit(request())
        self.assertEqual(self.queued.call_count,1)
        changed=request();changed['brief']='Different request'
        with self.assertRaises(Conflict):self.agent.submit(changed)

    def test_complete_handoff_has_relative_paths_checksums_and_no_publication_claim(self):
        record=self.complete();self.assertEqual(record['status'],'complete')
        self.assertEqual(len(record['assets']),2);self.assertEqual(self.jobs_count,2)
        root=Path(record['exchangeRoot'])
        self.assertTrue((root/record['archive']).is_file())
        for asset in record['assets']:
            for file in asset['files'].values():self.assertEqual(file['sha256'],checksum(root/file['path']))
        self.assertIn('Nothing has been scheduled',record['message'])
        self.assertFalse(self.agent.snapshot()['reports'])

    def test_different_request_for_same_slots_reuses_completed_videos(self):
        first=self.complete();second=self.complete(request('week-replay'))
        self.assertEqual(self.jobs_count,2)
        self.assertEqual([a['id'] for a in first['assets']],[a['id'] for a in second['assets']])

    def test_three_daily_series_keep_separate_media_and_replay_without_regenerating(self):
        value=request('three-series',readingTypes=['western','chinese','numerology'])
        value.update(days=7,editions=['morning'])
        record=self.complete(value)
        self.assertEqual(record['status'],'complete',record.get('error'))
        self.assertEqual(len(record['assets']),21);self.assertEqual(self.jobs_count,21)
        paths=[a['files']['reading.mp4']['path'] for a in record['assets']]
        self.assertEqual(len(set(paths)),21)
        self.assertEqual({a['readingType'] for a in record['assets']},{'western','chinese','numerology'})
        self.assertTrue(all((Path(record['exchangeRoot'])/p).is_file() for p in paths))
        replay={**value,'requestId':'three-series-again'}
        self.complete(replay);self.assertEqual(self.jobs_count,21)

    def test_same_slot_with_changed_settings_is_not_overwritten(self):
        self.complete();changed=request('new-style');changed['style']='storybook-cartoon'
        with self.assertLogs(level='ERROR'):second=self.complete(changed)
        self.assertEqual(second['status'],'failed');self.assertIn('different saved edition',second['error'])
        self.assertEqual(self.jobs_count,2)

    def test_repeated_completed_request_does_not_recreate_removed_media(self):
        record=self.complete();count=self.jobs_count
        video=Path(record['exchangeRoot'])/record['assets'][0]['files']['reading.mp4']['path'];video.unlink()
        self.agent.submit(request());self.assertEqual(self.jobs_count,count);self.assertFalse(video.exists())

    def test_reports_need_real_identifiers_known_asset_and_are_idempotent(self):
        record=self.complete();asset=record['assets'][0]
        report=dict(id='post-scheduled',assetId=asset['id'],platform='facebook',accountId='qa-page',postId='actual-returned-id',status='scheduled',scheduledAt=asset['proposedPublishAt'])
        one=self.agent.report(report);two=self.agent.report(report)
        self.assertEqual(one,two);self.assertFalse(one['independentlyVerified'])
        self.assertEqual(len(self.agent.snapshot()['reports']),1)
        with self.assertRaises(Conflict):self.agent.report({**report,'status':'published'})
        with self.assertRaises(ValueError):self.agent.report({**report,'id':'unknown','assetId':'unknown'})

    def test_connection_test_does_not_claim_calendar_slot_or_accept_publication(self):
        data=request('first-test');data['kind']='connection-test'
        record=self.complete(data);self.assertEqual(len(record['assets']),1)
        self.assertFalse(record['assets'][0]['publicationAllowed']);self.assertFalse(self.planner.entries())
        with self.assertRaises(ValueError):self.agent.report(dict(id='bad-test-post',assetId=record['assets'][0]['id'],platform='facebook',accountId='page',postId='post',status='published'))

    def test_restart_interrupts_work_and_only_explicit_resume_requeues(self):
        self.agent.submit(request());record=self.agent.get('week-one');record['status']='running';self.agent.put(record)
        recovered=AgentJobs(self.store,self.planner,self.jobs,start=False)
        try:
            with patch.object(recovered.pool,'submit') as queue:
                self.assertEqual(recovered.get('week-one')['status'],'interrupted')
                recovered.submit(request());self.assertEqual(queue.call_count,0)
                recovered.submit(request(),retry=True);self.assertEqual(queue.call_count,1)
        finally:recovered.pool.shutdown(wait=True)

    def test_folder_replay_keeps_valid_ready_status_when_payload_changes(self):
        record=self.complete();root=Path(record['exchangeRoot']);data=request();data['brief']='changed brief'
        (root/'Requests/week-one.json').write_text(json.dumps(data))
        self.agent.poll()
        self.assertEqual(json.loads((root/'Status/week-one.json').read_text())['status'],'complete')
        self.assertEqual(json.loads((root/'Status/week-one.error.json').read_text())['status'],'error')

    def test_exchange_file_cannot_escape_selected_root(self):
        with self.assertRaises(ValueError):inside(self.folder/'exchange',self.folder/'private.txt')


if __name__=='__main__':unittest.main()
