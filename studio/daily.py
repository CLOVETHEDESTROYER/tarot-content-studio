import hashlib
import json
import os
import random
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from .config import api_client
from .daily_context import build_context,saved_context,edition_instant
from .daily_visuals import STYLES,SIGN_THEMES,ANIMAL_THEMES,NUMBER_THEMES,visual_card
from .platform_support import default_voice
from .voice_direction import presentation

TYPES={'tarot':'Tarot','western':'Western astrology','chinese':'Chinese astrology','numerology':'Numerology','combined':'Combined'}
COMPONENTS=('tarot','western','chinese','numerology')


def validate_daily_settings(data):
    from .engine import DURATIONS,VOICES
    from .deck_catalog import DECKS
    if not isinstance(data,dict):raise ValueError('Send daily reading settings.')
    kind=data.get('reading_type','combined')
    if kind not in TYPES:raise ValueError('Choose a daily reading type.')
    day=data.get('date',datetime.now(ZoneInfo('America/Denver')).date().isoformat())
    edition=data.get('edition','morning');zone=data.get('timezone','America/Denver')
    instant=edition_instant(day,edition,zone)
    style=data.get('style','esoteric-minimal')
    if style not in STYLES:raise ValueError('Choose Esoteric Minimal or Storybook Cartoon.')
    components=data.get('components',list(COMPONENTS)) if kind=='combined' else [kind]
    if not isinstance(components,list) or any(c not in COMPONENTS for c in components) or len(components)!=len(set(components)):
        raise ValueError('Choose available reading systems without duplicates.')
    if kind=='combined' and len(components)<2:raise ValueError('Combine at least two reading systems.')
    duration=data.get('duration',90 if kind=='combined' else 60)
    if type(duration) is not int or duration not in DURATIONS:raise ValueError('Choose a supported video length.')
    voice=data.get('voice',default_voice());writer=data.get('writer','local')
    if voice not in VOICES or writer not in ('local','openai'):raise ValueError('Choose an available voice and writer.')
    deck=data.get('deck','esoteric-minimal')
    if not isinstance(deck,str) or deck not in DECKS:raise ValueError('Choose an available tarot deck.')
    spread=data.get('spread','three' if kind=='tarot' else 'one')
    if spread not in ('one','three'):raise ValueError('Choose one or three tarot cards.')
    if kind=='combined':spread='one'
    include_news=data.get('include_news',False)
    if not isinstance(include_news,bool):raise ValueError('Choose whether to include current events.')
    selected=data.get('news_selection',[0])
    if not isinstance(selected,list) or len(selected)>3 or any(type(n) is not int or not 0<=n<6 for n in selected):
        raise ValueError('Choose up to three source headlines.')
    return dict(**presentation(data),daily=True,reading_type=kind,date=day,edition=edition,timezone=zone,style=style,
                components=[c for c in COMPONENTS if c in components],duration=duration,voice=voice,writer=writer,
                deck=deck,spread=spread,include_news=include_news,news_selection=sorted(set(selected)),
                topic=f"{TYPES[kind]} · {instant.strftime('%B %d, %Y')} · {'Morning perspective' if edition=='morning' else 'Evening reflection'}")


def cards_for(config,context,seed):
    from .engine import deck,payload
    cards=[];parts=config['components'];style=config['style']
    if 'tarot' in parts:
        rng=random.Random(seed)
        selected=rng.sample(deck(config['deck']),3 if config['reading_type']=='tarot' and config['spread']=='three' else 1)
        for i,card in enumerate(selected):
            result=payload(card,rng.choice(('Upright','Reversed')),config['deck'],i)
            result['kind']='tarot';result['position']=(['Focus','Notice','Next step'] if config['edition']=='morning' else ['Reflect','Release','Carry forward'])[i]
            cards.append(result)
    if 'western' in parts:
        sky=context['western'];sun=sky['positions']['Sun'];moon=sky['positions']['Moon']
        if config['reading_type']=='western':
            cards.append(visual_card('western',sun['sign'].lower(),'Sun in '+sun['sign'],SIGN_THEMES[sun['sign']],'Seasonal theme',style,'sun'))
        cards.append(visual_card('western',moon['sign'].lower(),'Moon in '+moon['sign'],SIGN_THEMES[moon['sign']],sky['moon_phase'],style,'moon'))
    if 'chinese' in parts:
        calendar=context['chinese']
        if config['reading_type']=='chinese':
            animal=calendar['year_animal'];element=calendar['year_element']
            cards.append(visual_card('chinese',animal.lower(),f'{element} {animal} year',ANIMAL_THEMES[animal],'Annual backdrop',style,'year'))
        animal=calendar['day_animal'];element=calendar['day_element']
        cards.append(visual_card('chinese',animal.lower(),f'{element} {animal} day',ANIMAL_THEMES[animal],'Daily stem–branch theme',style,'day'))
    if 'numerology' in parts:
        number=context['numerology']['number'];theme,am,pm=NUMBER_THEMES[number]
        cards.append(visual_card('numerology',str(number),f'{number} · {theme}',am if config['edition']=='morning' else pm,'Universal day number',style,'day'))
    if config['include_news']:
        headlines=context['news']['headlines']
        for i in config['news_selection']:
            if i<len(headlines):
                item=headlines[i]
                card=visual_card('world','world','World context',item['title'],item['publisher'],style,'headline-'+str(i))
                card['source']=item;cards.append(card)
    return cards


def local_daily_sections(cards,config,context):
    from .editorial import brief
    edit=brief(config,context);pm=config['edition']=='evening'
    hook=(f"Before tomorrow, reflect on {edit['everyday_situation']}. " if pm else f"What would change if you handled {edit['everyday_situation']} differently? ")
    hook+=f"For {edit['weekday']}, {edit['date_spoken']}, here's the thread to follow."
    short=config['duration']<=45
    if short:hook=f"{edit['weekday']}, {edit['date_spoken']}: rethink {edit['everyday_situation']}."
    if short and pm:hook+=' Time to reflect.'
    result=[dict(key='hook',label='Opening',card_id=None,text=hook)]
    for i,card in enumerate(cards):
        kind=card.get('kind','tarot')
        if kind=='tarot':
            text=f"{card['name']}{' reversed' if card['orientation']=='Reversed' else ''} puts {card['meaning']} at the center of the choice. What's the habit behind your first response?"
        elif kind=='western':
            if 'moon' in card['id']:
                sky=context['western'];text=f"The Moon is in {sky['positions']['Moon']['sign']} during a {sky['moon_phase'].lower()}. That brings {card['meaning']} into the symbolic reading."
                if sky['aspects']:
                    a=sky['aspects'][0];text+=f" {a['first']} and {a['second']} form a {a['aspect']} in this snapshot. Think about the difference between a quick reaction and a considered response."
            else:text=f"{card['name']} supplies the seasonal backdrop: {card['meaning']}. The useful test is how you put that quality into an ordinary decision."
        elif kind=='chinese':
            c=context['chinese']
            text=(f"The {c['year_element']} {c['year_animal']} year is the backdrop, not a verdict about your day. " if 'year' in card['id'] else f"Today is a {c['day_polarity']} {c['day_element']} {c['day_animal']} day in the Chinese calendar. ")
            text+=f"Its symbolic theme is {card['meaning']}. Where would a deliberate response serve you better than repeating yesterday's approach?"
        elif kind=='numerology':
            n=context['numerology'];text=f"This exact date adds to {n['digit_sum']} and reduces to {n['number']}. For {NUMBER_THEMES[n['number']][0].lower()}, the practical invitation is {card['meaning']}. Give that idea a real appointment in your day."
        else:text=f"From {card['source']['publisher']}: {card['source']['title']} Consider what this verified context asks you to pay attention to; the reading does not predict the event."
        if short and kind!='world':
            if kind=='western' and 'moon' in card['id']:text=f"{context['western']['moon_phase']} Moon in {context['western']['positions']['Moon']['sign']}: consider {card['meaning'].split(',')[0]}."
            elif kind=='numerology':text=f"The date adds to {context['numerology']['digit_sum']}, then reduces to {context['numerology']['number']}: {NUMBER_THEMES[context['numerology']['number']][0].lower()}."
            else:text=f"{card['name']}{' reversed' if card['orientation']=='Reversed' else ''}: consider {card['meaning'].split(',')[0]}."
        result.append(dict(key=f'card-{i}',label=card['name'],card_id=card['id'],text=text))
    closing=("Look back without inventing a perfect ending. " if pm else "Here's the payoff: ")+edit['practical_action']
    closing+=' What will you do differently with that insight?'
    if short:closing=edit['practical_action']+' Where will you start?'
    result.append(dict(key='closing',label='Closing',card_id=None,text=closing))
    target=round((config['duration']-2)*2.1)
    extras=[
        f"Try it with {edit['everyday_situation']}: distinguish what actually needs an answer from what merely feels urgent.",
        "Picture the next conversation or task where this would matter. Choose the words or the first step now, while the idea is clear.",
        "A useful reading leaves you with a choice you can recognize in the moment. The symbol is a prompt; your circumstances and judgment still matter.",
        "When you review this later, ask what changed because of your response, rather than whether every symbol matched an event. That is a more useful test."]
    for i,addition in enumerate(extras):
        if sum(len(s['text'].split()) for s in result)<target:
            section=result[1+i%max(1,len(cards))] if cards else result[-1]
            section['text']+=' '+addition
    return result


def write_daily(cards,config,context,focus=None):
    from .engine import validate_sections
    from .editorial import brief,daily_instructions,section_plan,script_issues
    sections=local_daily_sections(cards,config,context)
    if config['writer']=='local':
        if focus:sections[0]['text']+=f' Hold your question in mind: {focus[:400]} Let these date-based themes offer a little perspective.'
        return sections,'Built-in daily writing'
    count=len(sections);source_words=sum(len(card['source']['title'].split())+4 for card in cards if card.get('source'))
    budget=max(45,round((config['duration']-2)*2.1)-source_words)
    selected_context={key:context[key] for key in ('date','edition','timezone','publication_time')}
    selected_context.update({key:context[key] for key in config['components'] if key!='tarot'})
    selected_context['news']=[card['source'] for card in cards if card.get('source')]
    plan=section_plan(sections,budget)
    keys=[s['key'].replace('-','_') for s in sections]
    fields={key:dict(type='string',description=f"{item['role']} Aim for {item['target_words']} words.",
        pattern=r'^(?:\S+\s+){0,'+str(item['max_words']-1)+r'}\S+\s*$') for key,item in zip(keys,plan)}
    schema=dict(type='object',properties=fields,required=keys,additionalProperties=False)
    payload=dict(date=config['date'],timezone=config['timezone'],cards=cards,viewer_focus=focus,
        editorial_brief=brief(config,context),context=selected_context,section_plan=plan)
    instructions=daily_instructions(config,context,count,budget,focus)+(
        ' Follow section_plan word limits individually. The TOTAL budget covers the entire video, not each section. '
        'Keep the opening to a hook and date only. Use month name and digits for the day, for example November 5. '
        'Return only the requested keyed sections; never repeat a complete reading in each section.')
    client=api_client()
    for attempt in range(2):
        response=client.responses.create(model=os.getenv('OPENAI_READING_MODEL','gpt-4.1-mini'),
            instructions=instructions,input=json.dumps(payload,ensure_ascii=False),
            text={'format':{'type':'json_schema','name':'daily_reading','strict':True,'schema':schema}},
            max_output_tokens=min(2400,max(600,round(budget*2.4)+200)))
        try:
            parsed=json.loads(response.output_text)
            generated=[parsed[key] for key in keys]
        except (ValueError,KeyError,TypeError):generated=[]
        issues=script_issues(generated,plan,budget,config['date'])
        if not issues:break
        payload.update(draft_to_revise=generated,required_corrections=issues)
    else:raise ValueError('The daily writer could not meet the date and length checks. Your saved reading is safe; try writing again or use built-in writing.')
    for section,text in zip(sections,generated):
        section['text']=text.strip()
        card=next((c for c in cards if c['id']==section['card_id']),None)
        if card and card.get('source'):
            section['text']=f"From {card['source']['publisher']}: {card['source']['title']} {section['text']}"
    validate_sections(sections)
    return sections,'OpenAI daily writing'


def create_daily(data,focus=None):
    config=validate_daily_settings(data)
    context=saved_context(data['context_id'],config) if data.get('context_id') else build_context(config)
    identity={k:config[k] for k in ('date','edition','timezone','reading_type','components','deck','spread')}
    seed=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
    cards=cards_for(config,context,seed)
    sections,source=write_daily(cards,config,context,focus=focus)
    day=datetime.fromisoformat(config['date']).strftime('%B %d')
    title=f"{day} · {'Morning perspective' if config['edition']=='morning' else 'Evening reflection'}"
    from .editorial import brief
    return dict(editorial_brief=brief(config,context),id=uuid.uuid4().hex,seed=seed,settings=config,title=title,cards=cards,sections=sections,
                writing_source=source,context=context,reading_label=TYPES[config['reading_type']])
