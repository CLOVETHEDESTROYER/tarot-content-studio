import copy
import hashlib
import json
import logging
import math
import shutil
import threading
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from .audio import prepare_audio, timeline, srt
from .config import DATA, EXPORTS
from .render import render_frame, encode_video
from .store import now
from .operations import generation_action


def fingerprint(draft):
    content = {key: draft[key] for key in ('title', 'cards', 'sections', 'settings')}
    if draft.get('context'):content['daily_context']=draft['context']
    if draft['settings']['voice'] == 'windows':
        content['windows_speech_version'] = 2
    if draft['settings']['voice'].startswith('openai-'):
        content['cloud_alignment_version'] = 4
        from .voice_direction import PROMPT_VERSION
        content['voice_direction_version']=PROMPT_VERSION
    if draft['settings']['voice'] == 'macos':
        content['macos_speech_version'] = 1
    return hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class Jobs:
    def __init__(self, store):
        self.store = store
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='studio-render')
        self.locks = {}
        self.guard = threading.Lock()
        self.store.recover()

    @generation_action
    def submit(self, draft, kind):
        with self.guard:
            outstanding = [j for j in self.store.jobs() if j['status'] in ('queued', 'running')]
            existing = next((j for j in outstanding if j['fingerprint'] == fingerprint(draft) and j['kind'] == kind), None)
            if existing:
                return existing
            if len(outstanding) >= 10:
                raise ValueError('Ten renders are already queued. Let a render finish before adding another.')
            job = dict(id=uuid.uuid4().hex, draft_id=draft['id'], revision=draft['revision'], fingerprint=fingerprint(draft),
                       kind=kind, pipeline_version=3 if draft['settings'].get('daily') else 2, created=now(), status='queued', progress=0, message='Waiting for the renderer', error='')
            self.store.put_job(job)
            self.pool.submit(self.work, copy.deepcopy(draft), job)
            return copy.deepcopy(job)

    def prepared(self, draft, progress):
        key = fingerprint(draft)
        folder = DATA / 'prepared' / key
        folder.mkdir(parents=True, exist_ok=True)
        with self.guard:
            lock = self.locks.setdefault(key, threading.Lock())
        with lock:
            path = folder / 'manifest.json'
            if path.exists():
                existing = json.loads(path.read_text(encoding='utf-8'))
                if isinstance(existing.get('duration'), (int, float)) and math.isfinite(existing['duration']) and 1 <= existing['duration'] <= 600 and (folder / 'narration.wav').is_file():
                    return folder, existing
                path.unlink()
            progress(8, 'Creating narration and aligning captions')
            audio, events, duration, alignment, warning = prepare_audio(draft, folder)
            sections, captions = timeline(draft, events, duration)
            manifest = dict(key=key, duration=duration, sections=sections, captions=captions,
                            alignment=alignment, warning=warning, has_audio=draft['settings']['voice'] != 'silent')
            (folder / 'reading.json').write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding='utf-8')
            # The completion manifest is written last, so interrupted work is never reused.
            temporary = folder / 'manifest.tmp'
            temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
            temporary.replace(path)
            return folder, manifest

    def work(self, draft, job):
        def update(amount, message):
            job.update(status='running', progress=amount, message=message)
            self.store.put_job(job)
        try:
            update(2, 'Preparing your saved reading')
            folder, manifest = self.prepared(draft, update)
            job.update(preview_key=manifest['key'], duration=manifest['duration'], warning=manifest['warning'])
            if job['kind'] == 'export':
                destination = EXPORTS / job['id']
                destination.mkdir(parents=True, exist_ok=True)
                update(30, 'Rendering your portrait video')
                encode_video(draft, manifest, folder / 'narration.wav', destination / 'reading.mp4', update)
                update(96, 'Saving your cover, subtitles, and posting bundle')
                render_frame(draft, manifest, min(3, manifest['duration'] / 2)).save(destination / 'cover.jpg', quality=95)
                (destination / 'subtitles.srt').write_text(srt(manifest['captions']), encoding='utf-8')
                disclosure='For entertainment and reflection.'+(' Synthetic narration.' if draft['settings']['voice']!='silent' else '')
                tags='#StarPowerDaily #DailyReading' if draft['settings'].get('daily') else '#StarPowerTarot #TarotReading #DailyTarot'
                caption = draft['settings']['topic']+'\n\n'+draft['sections'][-1]['text']+'\n\n'+disclosure+'\n'+tags
                used_sources=[card['source'] for card in draft['cards'] if card.get('source')]
                if used_sources:caption+='\n\nWorld context:\n'+'\n'.join(f"{h['publisher']}: {h['title']}\n{h['url']}" for h in used_sources)
                names=['reading.mp4','cover.jpg','subtitles.srt','caption.txt','reading.json','timeline.json']
                if draft.get('context'):
                    context=draft['context']
                    (destination/'context.json').write_text(json.dumps(context,ensure_ascii=False,indent=2),encoding='utf-8')
                    sources=['Sky calculations: '+context['western']['source'],'Chinese calendar: '+context['chinese']['source'],
                             'Numerology: '+context['numerology']['calculation'],'Edition: '+context['publication_time']]
                    sources += [f"Used in reading: {h['publisher']} | {h['published']} | {h['title']} | {h['url']}" for h in used_sources]
                    (destination/'sources.txt').write_text('\n'.join(sources)+'\n',encoding='utf-8')
                    names+=['context.json','sources.txt']
                (destination / 'caption.txt').write_text(caption, encoding='utf-8')
                (destination / 'reading.json').write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding='utf-8')
                shutil.copyfile(folder / 'manifest.json', destination / 'timeline.json')
                with zipfile.ZipFile(destination / 'posting-bundle.zip', 'w', zipfile.ZIP_DEFLATED) as bundle:
                    for name in names:
                        bundle.write(destination / name, name)
                job['files'] = names+['posting-bundle.zip']
            job.update(status='done', progress=100, message='Video ready to download' if job['kind'] == 'export' else 'Preview ready', finished=now())
            self.store.put_job(job)
        except Exception as exc:
            logging.exception('Studio job failed: %s', job['id'])
            # Avoid returning API responses, request headers, or secrets to the browser.
            from openai import OpenAIError
            message = ('OpenAI could not complete this request. Check the connection and API credits, or choose built-in writing / the local system voice.'
                       if isinstance(exc, OpenAIError) else str(exc))
            job.update(status='failed', error=message[:800], message='Render could not finish', finished=now())
            self.store.put_job(job)
