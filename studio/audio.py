import hashlib
import json
import math
import os
import re
import subprocess
import sys
import wave
import unicodedata
from difflib import SequenceMatcher
from array import array
from pathlib import Path
from .config import ROOT, api_client

HIDDEN = {'creationflags': subprocess.CREATE_NO_WINDOW} if sys.platform == 'win32' else {}


def ffmpeg():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def run_ffmpeg(args, timeout=120):
    result = subprocess.run([ffmpeg(), '-hide_banner', '-loglevel', 'error', '-nostdin', '-y', *map(str, args)],
                            capture_output=True, timeout=timeout, **HIDDEN)
    if result.returncode:
        raise ValueError('Video/audio processing failed: ' + result.stderr.decode('utf-8', 'replace')[-700:])


def wave_info(path, require_voice=True):
    with wave.open(str(path), 'rb') as audio:
        if audio.getsampwidth() != 2:
            raise ValueError('Narration must be 16-bit PCM.')
        frames = audio.readframes(audio.getnframes())
        # Streamed WAVs may use 0xFFFFFFFF as the declared data length. The
        # bytes actually received, not that placeholder header, are authoritative.
        duration = len(frames) / (audio.getframerate() * audio.getnchannels() * audio.getsampwidth())
        samples = array('h', frames)
    if not .5 <= duration <= 600:
        raise ValueError('Narration must contain between half a second and ten minutes of actual audio.')
    if require_voice and (not samples or max(map(abs, samples)) < 128):
        raise ValueError('Narration was silent. Choose another voice and try again.')
    return duration


def script_text(draft):
    return '\n\n'.join(s['text'].strip() for s in draft['sections'])


def windows_speech(text, folder):
    if sys.platform != 'win32':
        raise ValueError('Windows voice is available on Windows. Select an OpenAI voice or captions only.')
    input_path, output, marks = folder / 'speech.txt', folder / 'raw.wav', folder / 'words.json'
    input_path.write_text(text, encoding='utf-8')
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                             '-File', str(ROOT / 'scripts' / 'speak.ps1'), '-InputFile', str(input_path),
                             '-OutputFile', str(output), '-TimingFile', str(marks)],
                            capture_output=True, timeout=120, **HIDDEN)
    if result.returncode:
        raise ValueError('Windows narration could not start. ' + result.stderr.decode('utf-8', 'replace')[-400:])
    events = json.loads(marks.read_text(encoding='utf-8-sig'))
    if not events:
        raise ValueError('Windows voice returned no speech timing. Please try again.')
    return output, events, 'Word timing from Windows speech'


def macos_speech(draft, folder):
    """Render each section with macOS say; align sections to measured audio.

    Native say doesn't expose word timestamps. Caption word times are estimated
    inside each section; card transitions use that section's actual audio length.
    """
    if sys.platform != 'darwin':
        raise ValueError('macOS voice is available on a Mac. Choose a local voice for this computer or captions only.')
    raw=folder/'raw.wav';events=[];elapsed=0;offset=0;gap=.20
    with wave.open(str(raw),'wb') as combined:
        combined.setnchannels(1);combined.setsampwidth(2);combined.setframerate(24000)
        for index,section in enumerate(draft['sections']):
            text=section['text'].strip();source=folder/f'mac-section-{index}.txt'
            aiff=folder/f'mac-section-{index}.aiff';pcm=folder/f'mac-section-{index}.wav'
            source.write_text(text,encoding='utf-8')
            try:
                result=subprocess.run(['/usr/bin/say','-f',str(source),'-o',str(aiff)],capture_output=True,timeout=60)
            except subprocess.TimeoutExpired:
                raise ValueError('macOS narration took too long. Try a shorter section or another voice.')
            if result.returncode:
                raise ValueError('macOS narration could not start. Check the system spoken-content voice or choose captions only.')
            run_ffmpeg(['-i',aiff,'-ac','1','-ar','24000','-c:a','pcm_s16le',pcm])
            duration=wave_info(pcm)
            tokens=list(re.finditer(r'\S+',text));span=max(.01,duration-.12)
            events.extend(dict(position=offset+m.start(),length=len(m.group()),text=m.group(),start=elapsed+i/max(1,len(tokens))*span) for i,m in enumerate(tokens))
            with wave.open(str(pcm),'rb') as audio:combined.writeframes(audio.readframes(audio.getnframes()))
            if index<len(draft['sections'])-1:combined.writeframes(b'\0\0'*round(24000*gap))
            elapsed+=duration+gap;offset+=len(text)+2
    return raw,events,'macOS speech · measured section timing, estimated word timing'


def openai_speech(text, voice, folder):
    # A network stream can keep a read timeout alive indefinitely. Bound the
    # whole optional cloud operation so it cannot stall the local render queue.
    (folder / 'speech.txt').write_text(text, encoding='utf-8')
    try:
        result = subprocess.run([sys.executable, '-m', 'studio.speech_worker', str(folder), voice],
                                cwd=ROOT, capture_output=True, timeout=180, **HIDDEN)
    except subprocess.TimeoutExpired:
        raise ValueError('OpenAI narration did not finish within three minutes. Retry or choose the local system voice.')
    if result.returncode:
        raise ValueError('OpenAI narration could not finish. Retry, check the connection and API credits, or choose the local system voice.')
    saved = json.loads((folder / 'raw-marks.json').read_text(encoding='utf-8'))
    return folder / 'raw.wav', saved['events'], saved['alignment']


def openai_speech_request(text, voice, folder):
    client = api_client().with_options(max_retries=0)
    output = folder / 'raw.wav'
    if not output.is_file():
        temporary = folder / 'raw.tmp'
        response = client.audio.speech.create(
            model=os.getenv('OPENAI_TTS_MODEL', 'gpt-4o-mini-tts'),
            voice=voice, input=text, response_format='wav',
        )
        temporary.write_bytes(response.content)
        temporary.replace(output)
    wave_info(output)
    # Align to the actual generated speech, rather than guessing subtitle intervals.
    with output.open('rb') as source:
        transcript = client.audio.transcriptions.create(model='whisper-1', file=source,
                                                        response_format='verbose_json', timestamp_granularities=['word'])
    words = transcript.words or []
    if not words:
        raise ValueError('Speech alignment returned no timestamps. Retry narration or choose the local system voice.')
    events = align_transcribed_words(text,[dict(word=w.word,start=w.start) for w in words],wave_info(output))
    return output, events, 'Word timing from speech transcription · token alignment'


def align_transcribed_words(text, words, duration):
    """Align the whole token sequence, preserving script character offsets.

    Greedy substring search can jump to a repeated word much later in the
    script after an apostrophe or spoken-number mismatch. Sequence alignment
    anchors matching runs and interpolates only the small gaps between them.
    """
    numbers=('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty twentyone twentytwo twentythree twentyfour twentyfive twentysix twentyseven twentyeight twentynine thirty thirtyone thirtytwo thirtythree').split()
    def normalized(value):
        value=''.join(c for c in unicodedata.normalize('NFKD',value.casefold()) if c.isalnum())
        return numbers[int(value)] if value.isdigit() and int(value)<len(numbers) else value
    tokens=list(re.finditer(r'\S+',text))
    spoken=[word for word in words if normalized(word['word'])]
    if not tokens or not spoken:raise ValueError('Speech alignment returned no usable words. Retry narration.')
    if any(not isinstance(w['start'],(int,float)) or not math.isfinite(w['start']) or not 0<=w['start']<duration for w in spoken):
        raise ValueError('Speech alignment returned invalid timestamps. Retry narration.')
    matches=SequenceMatcher(None,[normalized(t.group()) for t in tokens],[normalized(w['word']) for w in spoken],autojunk=False).get_matching_blocks()
    times=[None]*len(tokens)
    for block in matches:
        for offset in range(block.size):times[block.a+offset]=spoken[block.b+offset]['start']
    if sum(t is not None for t in times)/len(times)<.65:
        raise ValueError('Speech transcription did not match the saved script closely enough. Retry narration or choose the local system voice.')
    anchors=[(-1,0)]+[(i,t) for i,t in enumerate(times) if t is not None]+[(len(times),duration)]
    for (left,start),(right,end) in zip(anchors,anchors[1:]):
        if end<start:raise ValueError('Speech timestamps are out of order. Retry narration.')
        for index in range(left+1,right):times[index]=start+(end-start)*(index-left)/(right-left)
    return [dict(position=token.start(),length=len(token.group()),start=times[i],text=token.group()) for i,token in enumerate(tokens)]


def prepare_audio(draft, folder):
    text = script_text(draft)
    voice = draft['settings']['voice']
    target = draft['settings']['duration']
    warning = ''
    if voice == 'silent':
        output = folder / 'narration.wav'
        with wave.open(str(output), 'wb') as audio:
            audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(24000)
            audio.writeframes(b'\x00\x00' * (24000 * target))
        tokens = list(re.finditer(r'\S+', text))
        events = [dict(position=m.start(), length=len(m.group()), start=i / max(1, len(tokens)) * (target - 1), text=m.group())
                  for i, m in enumerate(tokens)]
        return output, events, target, 'Timed captions · no narration', warning
    marks = folder / 'raw-marks.json'
    if marks.is_file() and (folder / 'raw.wav').is_file():
        saved = json.loads(marks.read_text(encoding='utf-8'))
        raw, events, alignment = folder / 'raw.wav', saved['events'], saved['alignment']
    else:
        if voice == 'windows':raw, events, alignment = windows_speech(text, folder)
        elif voice == 'macos':raw, events, alignment = macos_speech(draft, folder)
        else:raw, events, alignment = openai_speech(text, voice.split('-', 1)[1], folder)
        marks.write_text(json.dumps(dict(events=events,alignment=alignment)), encoding='utf-8')
    duration = wave_info(raw)
    rate = duration / (target - 1)
    # Keep a natural speaking rate; extend the video rather than truncating words.
    actual_rate = max(.75, min(1.45, rate))
    actual = max(target, math.ceil(duration / actual_rate + .5))
    if rate > 1.45:
        warning = f'This script needs {actual} seconds at a clear speaking pace. Shorten it to reach {target} seconds.'
    output = folder / 'narration.wav'
    run_ffmpeg(['-i', raw, '-af', f'atempo={actual_rate:.8f},apad', '-t', actual,
                '-ac', '1', '-ar', '24000', '-c:a', 'pcm_s16le', output])
    wave_info(output)
    events = [{**event, 'start': event['start'] / actual_rate} for event in events]
    return output, events, actual, alignment, warning


def timeline(draft, events, duration):
    if not events or any(not isinstance(e.get('start'), (int,float)) or not math.isfinite(e['start']) or not 0 <= e['start'] < duration for e in events):
        raise ValueError('Speech timestamps fall outside the audio. Rebuild narration before exporting.')
    if any(a['start'] > b['start'] for a,b in zip(events, events[1:])):
        raise ValueError('Speech timestamps are out of order. Rebuild narration before exporting.')
    offsets, offset = [], 0
    for section in draft['sections']:
        offsets.append(offset)
        offset += len(section['text'].strip()) + 2
    sections = []
    for i, section in enumerate(draft['sections']):
        first = next((e['start'] for e in events if e['position'] >= offsets[i]), duration - 1)
        sections.append({**section, 'start': 0 if i == 0 else first})
    for i, section in enumerate(sections):
        section['end'] = sections[i + 1]['start'] if i + 1 < len(sections) else duration
    if any(s['start']>=s['end'] for s in sections):
        raise ValueError('Speech alignment collapsed a reading section. Rebuild narration or choose the local system voice.')
    captions = []
    for section, offset in zip(sections, offsets):
        matches = list(re.finditer(r'\S+', section['text']))
        for i in range(0, len(matches), 7):
            group = matches[i:i + 7]
            char_start = offset + group[0].start()
            char_end = offset + group[-1].end()
            start = next((e['start'] for e in events if e['position'] >= char_start), section['start'])
            end = next((e['start'] for e in events if e['position'] >= char_end), section['end'])
            end = min(section['end'], max(start + .1, end))
            captions.append(dict(start=round(start, 3), end=round(end, 3),
                                 text=section['text'][group[0].start():group[-1].end()]))
    return sections, captions


def srt(captions):
    def stamp(value):
        ms = round(value * 1000)
        return f'{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}'
    return '\n\n'.join(f"{i + 1}\n{stamp(c['start'])} --> {stamp(c['end'])}\n{c['text']}" for i, c in enumerate(captions)) + '\n'
