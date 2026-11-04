"""Bundled reading backdrops shared by export, preview and broadcast."""
from functools import lru_cache
from PIL import Image,ImageOps,ImageDraw
from .config import ASSETS

BACKGROUNDS={'solid':'Classic evergreen','celestial':'Celestial Atlas','garden':'Moonlit Garden',
             'aurora':'Aurora Mountains','dawn':'Storybook Dawn'}


def selected(data):
    value=data.get('background','solid')
    if not isinstance(value,str) or value not in BACKGROUNDS:raise ValueError('Choose an available reading background.')
    return value


def options():
    return [dict(id=key,label=label,thumbnail=f'/api/backgrounds/{key}?thumbnail=1',
                 image=f'/api/backgrounds/{key}') for key,label in BACKGROUNDS.items()]


def image_path(key,thumbnail=False):
    selected(dict(background=key))
    return ASSETS/'backgrounds'/(key+('-thumb' if thumbnail or key=='solid' else '')+'.jpg')


def register_routes(app):
    from flask import request,send_file,abort
    @app.get('/api/backgrounds/<key>')
    def reading_background(key):
        try:path=image_path(key,request.args.get('thumbnail')=='1')
        except ValueError:abort(404)
        return send_file(path,mimetype='image/jpeg',max_age=86400)


@lru_cache(maxsize=5)
def canvas(key):
    selected(dict(background=key))
    if key=='solid':return Image.new('RGB',(1080,1920),'#0b1d15')
    with Image.open(image_path(key)) as source:
        art=ImageOps.fit(source.convert('RGB'),(1080,1920),method=Image.Resampling.LANCZOS).convert('RGBA')
    shade=Image.new('RGBA',art.size,(3,13,12,25))
    draw=ImageDraw.Draw(shade)
    # Quiet reading zones preserve cream type while keeping the scenic edges.
    for box in ((105,265,975,495),(105,1300,975,1570),(105,1695,975,1830)):
        draw.rounded_rectangle(box,radius=32,fill=(3,13,12,115))
    return Image.alpha_composite(art,shade).convert('RGB')
