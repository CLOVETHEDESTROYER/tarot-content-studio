"""One composition function for browser frames, covers, and exported video."""
import math
import subprocess
from functools import lru_cache
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps
from .audio import ffmpeg, HIDDEN
from .config import ASSETS
from .engine import deck

WIDTH, HEIGHT = 1080, 1920
BG, GOLD, CREAM = '#0b1d15', '#d6b66f', '#fff3db'


@lru_cache(maxsize=30)
def font(size, serif=False):
    choices = ([Path('C:/Windows/Fonts/georgia.ttf')] if serif else [Path('C:/Windows/Fonts/segoeui.ttf')])
    choices += ([Path('/System/Library/Fonts/Supplemental/Georgia.ttf')] if serif else [Path('/System/Library/Fonts/Helvetica.ttc')])
    choices += [ASSETS / 'fonts' / 'Cinzel.ttf', Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')]
    for path in choices:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default(size=size)


def lines(text, face, max_width):
    output, current = [], ''
    for word in text.split():
        trial = (current + ' ' + word).strip()
        if face.getlength(trial) > max_width and current:
            output.append(current); current = word
        else:
            current = trial
    if current:
        output.append(current)
    return output


def centered(draw, text, y, size, color=CREAM, serif=False, max_width=840, max_lines=4):
    while size >= 20:
        face = font(size, serif)
        wrapped = lines(text, face, max_width)
        if len(wrapped) <= max_lines and all(face.getlength(line) <= max_width for line in wrapped):
            break
        size -= 2
    for line in wrapped:
        draw.text((WIDTH / 2, y), line, font=face, fill=color, anchor='mt')
        y += size * 1.17
    return y


def star(draw, x, y, size, color=GOLD):
    draw.line((x-size, y, x+size, y), fill=color, width=2)
    draw.line((x, y-size*1.5, x, y+size*1.5), fill=color, width=2)
    for dx, dy in ((-1,-1),(1,-1)):
        draw.line((x+dx*size*.6,y+dy*size*.6,x-dx*size*.6,y-dy*size*.6), fill=color, width=2)


@lru_cache(maxsize=20)
def backdrop(title, has_audio=True, label='T A R O T', date_line=''):
    image = Image.new('RGB', (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)
    draw.rectangle((32,32,1047,1887), outline='#365039', width=2)
    star(draw, 540, 100, 23)
    centered(draw, 'StarPower', 145, 44, GOLD, True)
    centered(draw, label, 205, 23, GOLD)
    if date_line:centered(draw,date_line,252,22,'#b9c7b6')
    centered(draw, title, 305 if date_line else 280, 67 if date_line else 77, serif=True, max_width=760, max_lines=3)
    draw.line((170,1655,485,1655), fill='#6c643d', width=2)
    draw.line((595,1655,910,1655), fill='#6c643d', width=2)
    star(draw,540,1655,15)
    centered(draw, 'A LITTLE STAR POWER. A LITTLE PERSPECTIVE.', 1730, 21, GOLD)
    footer = 'Entertainment & reflection' + (' · Synthetic narration' if has_audio else '')
    centered(draw, footer, 1775, 21, '#a6b4a6')
    return image


@lru_cache(maxsize=32)
def artwork(deck_key, card_id, orientation):
    card = next(c for c in deck(deck_key) if c.id == card_id)
    with Image.open(card.image_path) as original:
        art = ImageOps.contain(original.convert('RGB'), (480, 720), Image.Resampling.LANCZOS)
    if orientation == 'Reversed':
        art = art.rotate(180)
    return art


def render_frame(draft, manifest, t, width=WIDTH):
    t = max(0, min(float(t), manifest['duration'] - .001))
    config=draft['settings'];daily=config.get('daily',False)
    date_line=''
    if daily:
        from .daily_context import edition_instant
        moment=edition_instant(config['date'],config['edition'],config['timezone'])
        date_line=moment.strftime('%B %d, %Y · %I %p %Z').replace(' 0',' ')
    image = backdrop(draft['title'],config['voice']!='silent',draft.get('reading_label','Daily reading').upper() if daily else 'T A R O T',date_line).copy()
    draw = ImageDraw.Draw(image)
    section = next((s for s in manifest['sections'] if s['start'] <= t < s['end']), manifest['sections'][-1])
    card = next((c for c in draft['cards'] if c['id'] == section.get('card_id')), draft['cards'][0] if section['key'] == 'hook' else draft['cards'][-1])
    art = daily_artwork(card['artwork']['style'],card['artwork']['family'],card['artwork']['key']) if card.get('artwork') else artwork(config['deck'],card['id'],card['orientation'])
    elapsed = t - section['start']
    scale = 1 if section['key'] in ('hook', 'closing') else min(1, max(.04, elapsed / .55))
    shown = art if scale == 1 else art.resize((max(1, round(art.width * scale)), art.height), Image.Resampling.BICUBIC)
    x, y = round((WIDTH - shown.width) / 2), 555 + (720 - art.height) // 2
    draw.rounded_rectangle((x-8,y-8,x+shown.width+7,y+shown.height+7), radius=14, outline=GOLD, width=3)
    image.paste(shown, (x,y))
    centered(draw, card['name'], 1320, 36, GOLD, True, max_lines=1)
    centered(draw, card['orientation'] + ' · ' + card['position'], 1370, 23, '#c0cdbd')
    caption = next((c for c in manifest['captions'] if c['start'] <= t < c['end']), None)
    if caption:
        centered(draw, caption['text'], 1410, 48, serif=True, max_width=760, max_lines=2)
    else:
        centered(draw, 'Take a breath. Make room for perspective.', 1410, 43, serif=True, max_width=760, max_lines=2)
    if width != WIDTH:
        image = image.resize((width, round(width * HEIGHT / WIDTH)), Image.Resampling.LANCZOS)
    return image


@lru_cache(maxsize=72)
def daily_artwork(style,family,key):
    from .daily_visuals import visual_path
    with Image.open(visual_path(style,family,key)) as original:
        return ImageOps.contain(original.convert('RGB'),(480,720),Image.Resampling.LANCZOS)


def encode_video(draft, manifest, audio_path, output, progress, width=1080):
    if not isinstance(manifest['duration'], (int, float)) or not math.isfinite(manifest['duration']) or not 1 <= manifest['duration'] <= 600:
        raise ValueError('Video duration must be between one second and ten minutes. Rebuild the preview.')
    height = width * 16 // 9
    input_fps = 15
    total = math.ceil(manifest['duration'] * input_fps)
    command = [ffmpeg(), '-hide_banner', '-loglevel', 'error', '-nostdin', '-y',
               '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{width}x{height}', '-r', str(input_fps), '-i', '-',
               '-i', str(audio_path), '-map', '0:v:0', '-map', '1:a:0',
               '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21', '-pix_fmt', 'yuv420p', '-r', '30',
               '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-movflags', '+faststart',
               '-t', str(manifest['duration']), str(output)]
    error_path = output.with_suffix('.encoder.log')
    with error_path.open('wb') as error:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=error, **HIDDEN)
        try:
            for index in range(total):
                process.stdin.write(render_frame(draft, manifest, index / input_fps, width).tobytes())
                if index % input_fps == 0:
                    progress(30 + round(index / total * 65), f'Rendering video · {round(index / total * 100)}%')
            process.stdin.close()
            code = process.wait(timeout=120)
            if code:
                raise ValueError('Video encoding failed. ' + error_path.read_text(errors='replace')[-700:])
        except Exception:
            process.kill(); process.wait()
            raise
    if error_path.stat().st_size == 0:
        error_path.unlink()
