"""Validate LIVE narration before publishing it to the broadcast."""
import base64
import io
import sys
import wave
from array import array


def validate_narration(data, text):
    with wave.open(io.BytesIO(data), 'rb') as audio:
        if audio.getsampwidth() != 2 or audio.getcomptype() != 'NONE':
            raise ValueError('Narration must contain 16-bit PCM audio.')
        frames = audio.readframes(audio.getnframes())
        duration = len(frames) / (audio.getframerate() * audio.getnchannels() * 2)
    if duration < max(2, len(text.split()) * .1):
        raise ValueError('Narration is too short for the reading.')
    samples = array('h', frames)
    if sys.byteorder != 'little':
        samples.byteswap()
    audible = sum(abs(sample) > 64 for sample in samples)
    if not samples or max(map(abs, samples)) < 128 or audible / len(samples) < .002:
        raise ValueError('Narration is silent or nearly silent.')
    return duration


def synthesize_live_narration(client, text, model='gpt-4o-mini-tts', voice='coral'):
    if client is None:
        return None
    text = text.strip()[:3500]
    if not text:
        raise ValueError('A reading is required for narration.')
    error = None
    for attempt_model, attempt_voice in ((model, voice), ('tts-1', 'nova')):
        try:
            response = client.with_options(timeout=60, max_retries=0).audio.speech.create(
                model=attempt_model, voice=attempt_voice, input=text, response_format='wav',
            )
            data = response.read()
            validate_narration(data, text)
            return 'data:audio/wav;base64,' + base64.b64encode(data).decode('ascii')
        except Exception as exc:
            error = exc
    raise ValueError('Narration failed validation after two attempts.') from error
