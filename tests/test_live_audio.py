import base64
import io
import unittest
import wave
from array import array
from unittest.mock import MagicMock

from studio.live.live_audio import synthesize_live_narration, validate_narration


def wav(seconds=3, amplitude=2000):
    output = io.BytesIO()
    with wave.open(output, 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(24000)
        audio.writeframes(array('h', [amplitude, -amplitude] * int(12000 * seconds)).tobytes())
    return output.getvalue()


class NarrationTests(unittest.TestCase):
    def test_valid_audio(self):
        self.assertEqual(validate_narration(wav(), 'A short reading'), 3)

    def test_rejects_silent_short_and_malformed_audio(self):
        for data in (wav(amplitude=0), wav(amplitude=1), wav(seconds=.36), b'broken'):
            with self.subTest(length=len(data)), self.assertRaises((ValueError, wave.Error, EOFError)):
                validate_narration(data, 'A short reading')

    def test_retries_invalid_clip_and_returns_wav(self):
        client = MagicMock()
        first, second = MagicMock(), MagicMock()
        first.read.return_value = wav(amplitude=0)
        second.read.return_value = wav()
        create = client.with_options.return_value.audio.speech.create
        create.side_effect = [first, second]
        result = synthesize_live_narration(client, 'A short reading')
        self.assertTrue(result.startswith('data:audio/wav;base64,'))
        self.assertEqual(base64.b64decode(result.split(',')[1]), wav())
        self.assertEqual(create.call_count, 2)
        self.assertEqual(create.call_args.kwargs['model'], 'gpt-4o-mini-tts')
        self.assertIn('instructions',create.call_args.kwargs)

    def test_failed_retry_is_not_published(self):
        client = MagicMock()
        client.with_options.return_value.audio.speech.create.return_value.read.return_value = wav(amplitude=0)
        with self.assertRaises(ValueError):
            synthesize_live_narration(client, 'A short reading')

    def test_missing_client(self):
        self.assertIsNone(synthesize_live_narration(None, 'A short reading'))
