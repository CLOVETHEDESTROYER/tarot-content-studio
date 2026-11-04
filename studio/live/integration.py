"""Mount the complete live workflow on the existing desktop engine."""
import base64
import json
import os
import re
import secrets
import sqlite3
from contextlib import closing
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from flask import abort,send_from_directory
from jinja2 import ChoiceLoader,FileSystemLoader
from ..config import ROOT,DATA,api_client
from ..daily import create_daily,TYPES
from ..store import now
from .. import operations


def generate_live(job,store=None):
    from .library import draw_cards,ai_reading,local_interpretation
    from .live_audio import synthesize_live_narration
    settings=job['settings'];item=job['request'];kind=item.get('reading_type') or settings.get('reading_type','tarot')
    day=item.get('reading_date') or settings.get('reading_date') or datetime.now(ZoneInfo(settings.get('timezone','America/Denver'))).date().isoformat()
    question=item['question'];warning='';draft=None;source='Built-in live reading'
    if kind=='tarot':
        cards=draw_cards(settings['spread'],settings.get('deck','celebrity'))
        spread='One Card' if settings['spread']=='one' else 'Past / Present / Future'
        reading=None
        if settings['use_ai']:
            try:reading=ai_reading(question,spread,cards)
            except Exception:warning='AI unavailable. Built-in interpretation used.'
        if reading:source='OpenAI live reading'
        else:reading=local_interpretation(question,spread,cards)
    else:
        edition='evening' if datetime.now(ZoneInfo(settings.get('timezone','America/Denver'))).hour>=12 else 'morning'
        config=dict(reading_type=kind,date=day,edition=edition,timezone=settings.get('timezone','America/Denver'),
            style=settings.get('style','esoteric-minimal'),deck=settings.get('deck','celebrity'),duration=90,
            spread=settings['spread'],voice='silent',writer='openai' if settings['use_ai'] else 'local',include_news=False)
        try:draft=create_daily(config,focus=question)
        except Exception:
            if not settings['use_ai']:raise
            config['writer']='local';draft=create_daily(config,focus=question);warning='AI unavailable. Built-in date-based reading used.'
        cards=draft['cards'];reading='\n\n'.join(s['text'] for s in draft['sections']);source=draft['writing_source']
    voice=settings.get('voice','openai-coral');audio=None
    if settings['use_voice'] and voice!='silent':
        try:
            if voice.startswith('openai-'):
                audio=synthesize_live_narration(api_client(),reading,model=os.getenv('OPENAI_TTS_MODEL','gpt-4o-mini-tts'),voice=voice.removeprefix('openai-'))
            else:
                from ..audio import windows_speech,macos_speech
                with tempfile.TemporaryDirectory() as tmp:
                    folder=Path(tmp)
                    raw,_,_=windows_speech(reading,folder) if voice=='windows' else macos_speech({'sections':[{'text':reading}]},folder)
                    audio='data:audio/wav;base64,'+base64.b64encode(raw.read_bytes()).decode('ascii')
        except Exception:warning+=' Narration unavailable; captions remain available.'
    if store:
        if draft is None:
            import uuid
            sentences=[s.strip() for s in re.split(r'(?<=[.!?])\s+|\n+',reading) if s.strip()]
            count=len(cards)+2;sections=[]
            for index in range(count):
                chunk=' '.join(sentences[round(index*len(sentences)/count):round((index+1)*len(sentences)/count)]) or 'Take a breath.'
                card=cards[index-1] if 0<index<count-1 else None
                sections.append(dict(key='hook' if index==0 else 'closing' if index==count-1 else f'card-{index-1}',
                    label=card['name'] if card else 'Opening' if index==0 else 'Closing',card_id=card['id'] if card else None,text=chunk))
            draft=dict(id=uuid.uuid4().hex,title=f"Live · {item['viewer']} · {day}",cards=cards,
                sections=sections,
                settings=dict(topic=question[:300],deck=settings.get('deck','celebrity'),spread=settings['spread'],duration=90,
                              voice=voice if settings['use_voice'] else 'silent',writer='local'),writing_source=source)
        draft['settings']['voice']=voice if settings['use_voice'] else 'silent'
        draft['title']=f"Live {TYPES[kind]} · @{item['viewer']} · {day}"
        draft['live']=dict(viewer=item['viewer'],question=question,request_id=item['id'],date=day,reading_type=kind)
        saved=store.create(draft)
    return dict(cards=cards,reading=reading,reading_source=source,audio_data=audio,has_audio=bool(audio),warning=warning.strip(),
                reading_type=kind,reading_label=TYPES[kind],reading_date=day,context=draft.get('context') if draft else None,
                reading_id=saved['id'] if store else None)


def register(app,store,run_gateway=False):
    from .library import app as library
    from .live_routes import register_live_routes
    resources=ROOT/'resources/live'
    app.jinja_loader=ChoiceLoader([app.jinja_loader,FileSystemLoader(str(resources/'templates'))])
    folder=store.path.parent
    # Import the previous local live queue once, using a consistent read-only snapshot.
    # Never alter its database or silently resume a broadcast in a new application.
    legacy=folder.parent.parent/'tarot-reading-generator/data/live-studio.sqlite3'
    target=folder/'live-studio.sqlite3'
    if not target.exists() and legacy.is_file():
        with closing(sqlite3.connect(legacy.resolve().as_uri()+'?mode=ro',uri=True)) as source:
            value=json.loads(source.execute('SELECT data FROM studio WHERE id=1').fetchone()[0])
            if not isinstance(value.get('queue'),list):raise ValueError('Previous live queue is not readable.')
            with closing(sqlite3.connect(target)) as destination:source.backup(destination)
        from .live_studio import LiveStudio
        imported=LiveStudio(target,None)
        with imported.transaction() as state:
            if state.get('processing'):state['queue'].insert(0,state['processing']['request'])
            state.update(processing=None,running=False,paused=False,next_at=0,last_error='Previous Live Studio imported. Review the saved queue before starting.')
        (folder/'live-import.json').write_text(json.dumps(dict(source=str(legacy),importedAt=now(),broadcastStarted=False)),encoding='utf-8')
    secret=folder/'live-session.key'
    if not secret.exists():
        try:
            with secret.open('x',encoding='utf-8') as output:output.write(secrets.token_urlsafe(48))
        except FileExistsError:pass
    app.config.update(SECRET_KEY=os.getenv('LIVE_SESSION_SECRET') or secret.read_text().strip(),
        LIVE_DESKTOP=True,LIVE_PUBLIC=False,LIVE_STUDIO_DB=str(folder/'live-studio.sqlite3'),
        LIVE_AUTH_DB=str(folder/'live-auth.sqlite3'),LIVE_DATA_DIR=str(folder))
    app.register_blueprint(library)
    @app.get('/static/<path:name>')
    def live_static(name):return send_from_directory(resources/'static',name)
    register_live_routes(app,lambda job:generate_live(job,store))
    if run_gateway:
        import threading
        from waitress import create_server
        from .gateway import create_gateway
        port=int(os.getenv('STUDIO_BROADCAST_PORT',str(int(os.getenv('STUDIO_PORT','5057'))+100)))
        server=create_server(create_gateway(folder),host='127.0.0.1',port=port,threads=4)
        threading.Thread(target=server.run,name='read-only-broadcast',daemon=True).start()
        app.extensions['broadcast_gateway_server']=server
        app.config['BROADCAST_GATEWAY_URL']=f'http://127.0.0.1:{port}'
