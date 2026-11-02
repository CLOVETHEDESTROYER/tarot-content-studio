from .config import ASSETS
from .daily_context import SIGNS, ANIMALS

STYLES = ('esoteric-minimal','storybook-cartoon')
NUMBERS = (1,2,3,4,5,6,7,8,9,11,22,33)
SIGN_THEMES = {
 'Aries':'initiative, courage, and taking one considered first step',
 'Taurus':'steadiness, everyday comforts, and tending what sustains you',
 'Gemini':'curiosity, conversation, and checking a new perspective',
 'Cancer':'care, belonging, and protecting time for emotional rest',
 'Leo':'creative confidence, generosity, and making room for joy',
 'Virgo':'discernment, useful routines, and improving one small detail',
 'Libra':'balance, cooperation, and listening before deciding',
 'Scorpio':'honesty, depth, and releasing an exhausted pattern',
 'Sagittarius':'perspective, discovery, and exploring a wider possibility',
 'Capricorn':'patience, responsibility, and a practical long term step',
 'Aquarius':'fresh thinking, community, and reconsidering an old assumption',
 'Pisces':'imagination, compassion, and space to listen inwardly',
}
ANIMAL_THEMES = {
 'Rat':'resourcefulness and noticing a useful small opening', 'Ox':'steady effort and honoring your commitments',
 'Tiger':'courage guided by care rather than impulse', 'Rabbit':'diplomacy and a gentler route through tension',
 'Dragon':'creative ambition grounded in a realistic next step', 'Snake':'thoughtful observation before revealing your plan',
 'Horse':'independence balanced with a clear direction', 'Goat':'care, imagination, and support from trusted people',
 'Monkey':'adaptability and finding a fresh way around a problem', 'Rooster':'attention to detail and honest communication',
 'Dog':'loyalty, fairness, and dependable everyday actions', 'Pig':'generosity balanced with sensible boundaries',
}
NUMBER_THEMES = {
 1:('Initiative','begin one useful thing','notice where you acted on your own priorities'),
 2:('Connection','listen carefully and make room for cooperation','reflect on the balance between giving and receiving'),
 3:('Expression','give a creative idea a small tangible form','name something you enjoyed or expressed honestly'),
 4:('Foundation','strengthen one routine that supports you','recognize the quiet work that made your day steadier'),
 5:('Change','leave room for a sensible adjustment','release the plan that needed to change'),
 6:('Care','offer support while respecting your own limits','notice where care helped and where you need rest'),
 7:('Reflection','pause long enough to ask a better question','make space to digest what you learned'),
 8:('Stewardship','use your time and resources with intention','review where your effort went without judging yourself'),
 9:('Completion','finish or release one small unfinished task','acknowledge what is ready to end'),
 11:('Inspiration','record an insight before rushing to act on it','separate a useful intuition from an untested assumption'),
 22:('Building','translate a bigger idea into one practical step','notice the small foundations beneath a larger goal'),
 33:('Compassion','let care include yourself as well as other people','let kindness and realistic boundaries coexist'),
}


def visual_path(style,family,key):
    if style not in STYLES:raise ValueError('Unknown daily illustration style.')
    allowed={'western':{s.lower() for s in SIGNS},'chinese':{a.lower() for a in ANIMALS},
             'numerology':{str(n) for n in NUMBERS},'world':{'world'}}
    if family not in allowed or key not in allowed[family]:raise ValueError('Unknown daily visual card.')
    if family=='world':return ASSETS/'cards'/'variants'/style/'21.png'
    return ASSETS/'daily'/style/family/(key+'.png')


def gallery(style):
    result=[]
    for family,values in (('western',SIGNS),('chinese',ANIMALS),('numerology',NUMBERS)):
        for value in values:
            key=str(value).lower()
            name=str(value) if family!='numerology' else f'{value} · {NUMBER_THEMES[value][0]}'
            result.append(dict(id=family+'-'+key,family=family,key=key,name=name,style=style,
                               image_url=f'/api/daily/artwork/{style}/{family}/{key}',ready=visual_path(style,family,key).is_file()))
    return result


def visual_card(kind,key,name,meaning,position,style,role):
    return dict(id=kind+'-'+role+'-'+str(key),name=name,meaning=meaning,position=position,
                orientation={'western':'Western astrology','chinese':'Chinese calendar','numerology':'Universal day','world':'Source context'}[kind],
                kind=kind,celebrity=None,artwork=dict(style=style,family=kind,key=str(key)),
                image_url=f'/api/daily/artwork/{style}/{kind}/{key}')
