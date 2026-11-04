"""Short, cached voice auditions; never generate a full reading to compare voices."""
import hashlib
import json
import os
import re
import threading
import uuid
from .config import DATA,api_client
from .voice_direction import presentation,speech_options,PROMPT_VERSION
from .audio import wave_info

SAMPLE_TEXT="Before you rush into the next thing, notice the choice in front of you. A clearer question can change the whole conversation. What will you do differently today?"
LOCK=threading.Lock()


def sample_path(key):
    if not isinstance(key,str) or not re.fullmatch('[a-f0-9]{64}',key):raise ValueError('Unknown voice sample.')
    return DATA/'voice-samples'/(key+'.wav')


def create_sample(data):
    if not isinstance(data,dict) or set(data)-{'voice','voice_style','voice_energy'}:raise ValueError('Choose a voice and delivery for the sample.')
    selected=data.get('voice','')
    if not isinstance(selected,str) or not selected.startswith('openai-'):raise ValueError('Choose an OpenAI voice to audition.')
    delivery=presentation(data)
    options=speech_options(os.getenv('OPENAI_TTS_MODEL','gpt-4o-mini-tts'),selected.removeprefix('openai-'),delivery['voice_style'],delivery['voice_energy'])
    key=hashlib.sha256(json.dumps(dict(options=options,text=SAMPLE_TEXT,version=PROMPT_VERSION),sort_keys=True).encode()).hexdigest()
    path=sample_path(key);cached=path.is_file()
    if not cached:
        if not LOCK.acquire(blocking=False):raise ValueError('Another voice sample is being prepared. Try again in a moment.')
        try:
            if not path.is_file():
                response=api_client().with_options(timeout=60,max_retries=0).audio.speech.create(input=SAMPLE_TEXT,**options)
                path.parent.mkdir(parents=True,exist_ok=True)
                temporary=path.with_name(key+'.'+uuid.uuid4().hex+'.tmp')
                try:
                    temporary.write_bytes(response.content);wave_info(temporary);temporary.replace(path)
                finally:temporary.unlink(missing_ok=True)
        finally:LOCK.release()
    return dict(url=f'/api/voice/samples/{key}.wav',cached=cached,voice=selected,**presentation(data),disclosure='AI-generated voice sample')
