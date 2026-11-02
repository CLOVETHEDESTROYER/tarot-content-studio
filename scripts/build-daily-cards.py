"""Extract generated illustration atlases and typeset accurate card identities."""
import json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageOps

ROOT=Path(__file__).resolve().parent.parent
BASE=ROOT/'assets'/'daily'
NUMBER_NAMES={'1':'INITIATIVE','2':'CONNECTION','3':'EXPRESSION','4':'FOUNDATION','5':'CHANGE','6':'CARE',
              '7':'REFLECTION','8':'STEWARDSHIP','9':'COMPLETION','11':'INSPIRATION','22':'BUILDING','33':'COMPASSION'}


def font(size,style,bold=False):
    candidates=[Path('C:/Windows/Fonts/segoeuib.ttf' if bold else 'C:/Windows/Fonts/georgia.ttf'),ROOT/'assets/fonts/Cinzel.ttf']
    for path in candidates:
        if path.is_file():return ImageFont.truetype(str(path),size)
    return ImageFont.load_default(size=size)


def main():
    records=json.loads((BASE/'prompts.json').read_text(encoding='utf-8'))
    catalog=[]
    for record in records:
        style,family=record['style'],record['family']
        with Image.open(BASE/record['source']) as atlas:
            if abs(atlas.width/atlas.height-2/3)>.03:raise ValueError('Atlas must use a portrait 2x2 layout: '+record['source'])
            for index,(key,label,subject) in enumerate(record['cards']):
                x,y=index%2,index//2
                rectangle=(round(x*atlas.width/2),round(y*atlas.height/2),round((x+1)*atlas.width/2),round((y+1)*atlas.height/2))
                card=atlas.crop(rectangle).convert('RGB')
                if card.size!=(512,768):card=card.resize((512,768),Image.Resampling.LANCZOS)
                draw=ImageDraw.Draw(card)
                minimal=style=='esoteric-minimal';ink='#e4bc72' if minimal else '#182919';paper='#090a07' if minimal else '#ffe39a'
                title=(key+' · '+NUMBER_NAMES[key]) if family=='numerology' else label.upper()
                draw.rounded_rectangle((20,704,492,750),radius=3,fill=paper)
                size=26
                while font(size,style,not minimal).getlength(title)>450:size-=1
                draw.text((256,727),title,fill=ink,font=font(size,style,not minimal),anchor='mm')
                if family=='numerology':
                    draw.ellipse((207,18,305,116),fill=paper,outline=ink,width=2)
                    draw.text((256,66),key,fill=ink,font=font(61,style,not minimal),anchor='mm')
                folder=BASE/style/family;folder.mkdir(parents=True,exist_ok=True)
                output=folder/(key+'.png');card.save(output,optimize=True)
                catalog.append(dict(style=style,family=family,key=key,name=label,subject=subject,
                                    file=str(output.relative_to(BASE)).replace('\\','/'),source=record['source'],source_rectangle=rectangle))
    (BASE/'catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf-8')
    for style in ('esoteric-minimal','storybook-cartoon'):
        selected=[c for c in catalog if c['style']==style]
        sheet=Image.new('RGB',(1080,1692),'#f2f4f5');draw=ImageDraw.Draw(sheet)
        for i,entry in enumerate(selected):
            with Image.open(BASE/entry['file']) as original:
                thumbnail=ImageOps.contain(original,(160,240),Image.Resampling.LANCZOS)
            x,y=(i%6)*180+10,(i//6)*282+10;sheet.paste(thumbnail,(x,y))
            draw.text((x+80,y+255),entry['name'],fill='#294a35',font=font(13,style),anchor='mm')
        sheet.save(BASE/(style+'-collection.jpg'),quality=92)
    print(f'Built {len(catalog)} production cards from {len(records)} generated atlases.')


if __name__=='__main__':main()
