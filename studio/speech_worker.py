"""Isolated, time-bounded optional cloud narration for the local render queue."""
import json
import sys
from pathlib import Path
from .audio import openai_speech_request


def main():
    folder=Path(sys.argv[1]);voice=sys.argv[2]
    from .voice_direction import OPENAI_VOICES
    if voice not in OPENAI_VOICES:raise ValueError('Unknown studio voice.')
    text=(folder/'speech.txt').read_text(encoding='utf-8')
    path=folder/'speech-direction.json'
    delivery=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    _,events,alignment=openai_speech_request(text,voice,folder,**delivery)
    temporary=folder/'raw-marks.tmp'
    temporary.write_text(json.dumps(dict(events=events,alignment=alignment)),encoding='utf-8')
    temporary.replace(folder/'raw-marks.json')


if __name__=='__main__':
    try:main()
    except Exception:sys.exit(1)
