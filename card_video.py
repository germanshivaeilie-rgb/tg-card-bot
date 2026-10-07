"""
card_video.py — анимация открытия карточки (как на скрине):
рубашка карты -> частицы собираются в символ редкости -> переворот -> карта + название + редкость.

Нужно: pip install pillow numpy imageio-ffmpeg
"""
import math
import os
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import subprocess
import imageio_ffmpeg

VIDEO_W, VIDEO_H = 480, 640
VIDEO_FPS = 20
VIDEO_SECONDS = 2.6

CARD_CX, CARD_CY = 240, 255          # центр карты
BACK_W, BACK_H = 300, 440            # размер рубашки
FACE = 380                           # размер картинки карты


# ------------------------------------------------------------------ темы
# bg_in / bg_out — градиент фона, ray — цвет лучей, accent — основной цвет,
# symbol — символ на рубашке, decor — декор фона
THEMES = [
    ("скелет",   dict(bg_in=(95, 100, 105), bg_out=(10, 12, 16), ray=(230, 230, 220), accent=(240, 240, 230), symbol="skull",     decor="skulls")),
    ("демон",    dict(bg_in=(255, 70, 20),  bg_out=(40, 0, 0),   ray=(255, 120, 40), accent=(255, 150, 70),  symbol="pentagram", decor="flames")),
    ("призрач",  dict(bg_in=(120, 170, 220), bg_out=(10, 20, 40), ray=(200, 230, 255), accent=(235, 245, 255), symbol="ghost",     decor="ghosts")),
    ("тыквен",   dict(bg_in=(255, 130, 20), bg_out=(30, 8, 0),   ray=(255, 170, 60), accent=(255, 150, 30),  symbol="pumpkin",    decor="embers")),
    ("ведьм",    dict(bg_in=(150, 70, 220), bg_out=(18, 0, 35),  ray=(190, 120, 255), accent=(200, 140, 255), symbol="hat",       decor="stars")),
    ("вампир",   dict(bg_in=(190, 10, 40),  bg_out=(25, 0, 5),   ray=(255, 50, 80),  accent=(255, 70, 90),   symbol="drop",      decor="embers")),
    ("кошмар",   dict(bg_in=(170, 0, 120),  bg_out=(8, 0, 15),   ray=(255, 60, 200), accent=(255, 110, 220), symbol="skull",     decor="ghosts")),
    ("заражён",  dict(bg_in=(90, 190, 40),  bg_out=(5, 25, 5),   ray=(150, 255, 80), accent=(170, 255, 90),  symbol="biohazard", decor="bubbles")),
    ("токсич",   dict(bg_in=(200, 230, 20), bg_out=(20, 25, 0),  ray=(230, 255, 60), accent=(235, 255, 70),  symbol="radiation", decor="bubbles")),
    ("мутир",    dict(bg_in=(30, 220, 150), bg_out=(0, 25, 20),  ray=(80, 255, 200), accent=(100, 255, 210), symbol="biohazard", decor="bubbles")),
    ("ядерн",    dict(bg_in=(255, 190, 20), bg_out=(35, 12, 0),  ray=(255, 220, 60), accent=(255, 215, 50),  symbol="radiation", decor="embers")),
    ("критическ", dict(bg_in=(255, 60, 10), bg_out=(40, 0, 0),   ray=(255, 140, 30), accent=(255, 120, 40),  symbol="radiation", decor="flames")),
    ("отчужд",   dict(bg_in=(110, 40, 200), bg_out=(0, 0, 8),    ray=(220, 200, 255), accent=(230, 215, 255), symbol="void",      decor="stars")),
    ("бесконеч", dict(bg_in=(60, 200, 255), bg_out=(15, 0, 40),  ray=(255, 120, 255), accent=(170, 240, 255), symbol="void",      decor="stars")),
    ("специаль", dict(bg_in=(30, 200, 220), bg_out=(0, 18, 30),  ray=(120, 255, 255), accent=(140, 255, 255), symbol="star",      decor="stars")),
    ("секретн",  dict(bg_in=(30, 160, 70),  bg_out=(0, 18, 8),   ray=(100, 255, 140), accent=(120, 255, 150), symbol="star",      decor="embers")),
    ("легендар", dict(bg_in=(255, 190, 30), bg_out=(35, 18, 0),  ray=(255, 230, 100), accent=(255, 210, 70),  symbol="crown",     decor="stars")),
    ("эпическ",  dict(bg_in=(160, 60, 230), bg_out=(18, 0, 35),  ray=(210, 140, 255), accent=(210, 150, 255), symbol="gem",       decor="stars")),
    ("редк",     dict(bg_in=(50, 130, 255), bg_out=(0, 10, 35),  ray=(130, 190, 255), accent=(140, 200, 255), symbol="gem",       decor="stars")),
    ("обычн",    dict(bg_in=(130, 135, 145), bg_out=(15, 16, 20), ray=(210, 215, 225), accent=(220, 225, 235), symbol="gem",      decor="stars")),
]
DEFAULT_THEME = dict(bg_in=(110, 110, 125), bg_out=(10, 10, 16), ray=(210, 210, 230),
                     accent=(225, 225, 240), symbol="gem", decor="stars")


def _plain(s):
    return "".join(ch for ch in s if ch.isalnum() or ch in " -").strip()


def _theme(rarity_label):
    low = _plain(rarity_label).lower()
    for key, th in THEMES:
        if key in low:
            return th
    return DEFAULT_THEME


def _font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        try:
            return ImageFont.truetype("DejaVuSans.ttf", size)
        except Exception:
            return ImageFont.load_default()


def _ease(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


# ------------------------------------------------------------------ символы
def _symbol(kind, S, col):
    """Рисует символ на прозрачном квадрате S×S."""
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = S / 2
    r = S * 0.42
    fill = col + (255,)
    dark = (8, 8, 12, 255)

    if kind == "skull":
        d.ellipse((c - .85 * r, c - r, c + .85 * r, c + .3 * r), fill=fill)
        d.rounded_rectangle((c - .5 * r, c - .1 * r, c + .5 * r, c + .9 * r), radius=8, fill=fill)
        for sx in (-1, 1):
            d.ellipse((c + sx * .35 * r - .22 * r, c - .35 * r, c + sx * .35 * r + .22 * r, c + .09 * r), fill=dark)
        d.polygon([(c, c + .02 * r), (c - .1 * r, c + .3 * r), (c + .1 * r, c + .3 * r)], fill=dark)
        for i in range(-2, 3):
            x = c + i * .2 * r
            d.line((x, c + .55 * r, x, c + .9 * r), fill=dark, width=3)
    elif kind == "pentagram":
        d.ellipse((c - r, c - r, c + r, c + r), outline=fill, width=6)
        pts = [(c + .95 * r * math.cos(math.radians(-90 + 72 * k)),
                c + .95 * r * math.sin(math.radians(-90 + 72 * k))) for k in range(5)]
        for i in range(5):
            d.line((pts[i], pts[(i + 2) % 5]), fill=fill, width=6)
    elif kind == "ghost":
        d.ellipse((c - .6 * r, c - r, c + .6 * r, c + .2 * r), fill=fill)
        pts = [(c - .6 * r, c)]
        steps = 6
        for i in range(steps + 1):
            x = c - .6 * r + (1.2 * r) * i / steps
            y = c + (.95 * r if i % 2 == 0 else .6 * r)
            pts.append((x, y))
        pts.append((c + .6 * r, c))
        d.polygon(pts, fill=fill)
        for sx in (-1, 1):
            d.ellipse((c + sx * .25 * r - .1 * r, c - .4 * r, c + sx * .25 * r + .1 * r, c - .1 * r), fill=dark)
        d.ellipse((c - .12 * r, c, c + .12 * r, c + .3 * r), fill=dark)
    elif kind == "pumpkin":
        d.ellipse((c - .95 * r, c - .6 * r, c + .95 * r, c + .85 * r), fill=fill)
        d.ellipse((c - .5 * r, c - .6 * r, c + .5 * r, c + .85 * r), outline=dark, width=3)
        d.rectangle((c - .08 * r, c - .95 * r, c + .1 * r, c - .55 * r), fill=(60, 130, 40, 255))
        for sx in (-1, 1):
            d.polygon([(c + sx * .45 * r, c - .25 * r), (c + sx * .2 * r, c + .1 * r),
                       (c + sx * .7 * r, c + .1 * r)], fill=dark)
        d.polygon([(c - .5 * r, c + .3 * r), (c - .25 * r, c + .55 * r), (c, c + .35 * r),
                   (c + .25 * r, c + .55 * r), (c + .5 * r, c + .3 * r), (c + .3 * r, c + .7 * r),
                   (c - .3 * r, c + .7 * r)], fill=dark)
    elif kind == "radiation":
        d.ellipse((c - r, c - r, c + r, c + r), outline=fill, width=5)
        for a0 in (-120, 0, 120):
            d.pieslice((c - .9 * r, c - .9 * r, c + .9 * r, c + .9 * r), a0, a0 + 60, fill=fill)
        d.ellipse((c - .3 * r, c - .3 * r, c + .3 * r, c + .3 * r), fill=dark)
        d.ellipse((c - .18 * r, c - .18 * r, c + .18 * r, c + .18 * r), fill=fill)
    elif kind == "biohazard":
        for k in range(3):
            a = math.radians(-90 + 120 * k)
            x, y = c + .42 * r * math.cos(a), c + .42 * r * math.sin(a)
            d.ellipse((x - .5 * r, y - .5 * r, x + .5 * r, y + .5 * r), outline=fill, width=8)
        d.ellipse((c - .2 * r, c - .2 * r, c + .2 * r, c + .2 * r), fill=fill)
        d.ellipse((c - .08 * r, c - .08 * r, c + .08 * r, c + .08 * r), fill=dark)
    elif kind == "star":
        pts = []
        for k in range(10):
            rr = r if k % 2 == 0 else r * .42
            a = math.radians(-90 + 36 * k)
            pts.append((c + rr * math.cos(a), c + rr * math.sin(a)))
        d.polygon(pts, fill=fill)
    elif kind == "crown":
        d.polygon([(c - r, c + .6 * r), (c - r, c - .5 * r), (c - .5 * r, c + .1 * r), (c, c - .8 * r),
                   (c + .5 * r, c + .1 * r), (c + r, c - .5 * r), (c + r, c + .6 * r)], fill=fill)
        d.line((c - r, c + .4 * r, c + r, c + .4 * r), fill=dark, width=4)
        for x in (-.55, 0, .55):
            d.ellipse((c + x * r - .09 * r, c + .55 * r - .09 * r, c + x * r + .09 * r, c + .55 * r + .09 * r), fill=dark)
    elif kind == "hat":
        d.polygon([(c + .1 * r, c - r), (c - .5 * r, c + .5 * r), (c + .5 * r, c + .5 * r)], fill=fill)
        d.ellipse((c - r, c + .35 * r, c + r, c + .75 * r), fill=fill)
        d.rectangle((c - .45 * r, c + .25 * r, c + .45 * r, c + .45 * r), fill=dark)
    elif kind == "drop":
        d.polygon([(c, c - r), (c - .62 * r, c + .15 * r), (c + .62 * r, c + .15 * r)], fill=fill)
        d.ellipse((c - .62 * r, c - .2 * r, c + .62 * r, c + .95 * r), fill=fill)
        d.ellipse((c - .35 * r, c + .1 * r, c - .15 * r, c + .4 * r), fill=dark)
    elif kind == "void":
        for k in range(4):
            rr = r * (1 - .24 * k)
            d.ellipse((c - rr, c - rr, c + rr, c + rr), outline=fill, width=5)
        d.ellipse((c - .12 * r, c - .12 * r, c + .12 * r, c + .12 * r), fill=fill)
    else:  # gem
        d.polygon([(c - r, c - .2 * r), (c - .55 * r, c - .8 * r), (c + .55 * r, c - .8 * r),
                   (c + r, c - .2 * r), (c, c + .95 * r)], fill=fill)
        d.line((c - r, c - .2 * r, c + r, c - .2 * r), fill=dark, width=3)
        d.line((c - .55 * r, c - .8 * r, c - .25 * r, c - .2 * r, c, c + .95 * r), fill=dark, width=3)
        d.line((c + .55 * r, c - .8 * r, c + .25 * r, c - .2 * r, c, c + .95 * r), fill=dark, width=3)
    return img


def _card_back(col):
    """Тёмная рубашка с рамками, как на скрине."""
    img = Image.new("RGBA", (BACK_W, BACK_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, BACK_W - 1, BACK_H - 1), radius=22, fill=(14, 14, 18, 255),
                        outline=col + (255,), width=4)
    for i in range(1, 7):
        m = 8 + i * 8
        d.rounded_rectangle((m, m, BACK_W - m, BACK_H - m), radius=max(4, 20 - i * 2),
                            outline=(70 + i * 12, 70 + i * 12, 78 + i * 12, 255), width=1)
    return img


def _card_face(path, col):
    try:
        art = Image.open(path).convert("RGB")
    except Exception:
        art = Image.new("RGB", (FACE, FACE), (40, 40, 50))
    w, h = art.size
    s = min(w, h)
    art = art.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s)).resize((FACE, FACE), Image.LANCZOS)
    B = 5
    T = FACE + 2 * B
    out = Image.new("RGBA", (T, T), (0, 0, 0, 0))
    ImageDraw.Draw(out).rounded_rectangle((0, 0, T - 1, T - 1), radius=32, fill=col + (255,))
    mask = Image.new("L", (FACE, FACE), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, FACE - 1, FACE - 1), radius=28, fill=255)
    out.paste(art, (B, B), mask)
    return out


# ------------------------------------------------------------------ фон
def _make_bg_tools():
    ys, xs = np.mgrid[0:VIDEO_H, 0:VIDEO_W].astype(np.float32)
    dx, dy = xs - CARD_CX, ys - CARD_CY
    dist = np.sqrt(dx * dx + dy * dy) / 480.0
    ang = np.arctan2(dy, dx)
    return np.clip(dist, 0, 1), ang


def _bg_frame(th, dist, ang, t, strength):
    a = np.array(th["bg_in"], np.float32)
    b = np.array(th["bg_out"], np.float32)
    base = a[None, None, :] * (1 - dist[..., None]) + b[None, None, :] * dist[..., None]
    base = base * 0.55 + b[None, None, :] * 0.45
    rays = (0.5 + 0.5 * np.sin(ang * 14 + t * 2.2)) ** 5 * np.exp(-dist * 1.8) * strength
    base += np.array(th["ray"], np.float32)[None, None, :] * rays[..., None] * 0.6
    return Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), "RGB").convert("RGBA")


def _decor(kind, d, items, t, col, deco_sym):
    for (x, y, s, ph) in items:
        if kind == "stars":
            tw = 0.5 + 0.5 * math.sin(t * 8 + ph)
            r = 1 + s * 2.2 * tw
            c = col + (int(80 + 150 * tw),)
            d.line((x - r, y, x + r, y), fill=c, width=1)
            d.line((x, y - r, x, y + r), fill=c, width=1)
        elif kind == "embers":
            yy = (y - t * 110 * (0.5 + s * .4)) % VIDEO_H
            d.ellipse((x - s, yy - s, x + s, yy + s), fill=col + (170,))
        elif kind == "bubbles":
            yy = (y - t * 70 * (0.4 + s * .3)) % VIDEO_H
            r = 4 + s * 7
            d.ellipse((x - r, yy - r, x + r, yy + r), outline=col + (150,), width=2)
        elif kind == "ghosts":
            yy = y + math.sin(t * 4 + ph) * 8
            d.ellipse((x - 10, yy - 12, x + 10, yy + 8), fill=col + (60,))
            d.rectangle((x - 10, yy - 2, x + 10, yy + 12), fill=col + (60,))
        elif kind == "skulls":
            yy = y + math.sin(t * 3 + ph) * 3
            d.line((x - 10 * s, yy, x + 10 * s, yy - 6), fill=col + (110,), width=3)


def _draw_ground(kind, base, t, th, skull_img):
    d = ImageDraw.Draw(base, "RGBA")
    col = th["accent"]
    if kind == "flames":
        for i in range(0, VIDEO_W + 30, 30):
            h = 50 + 35 * math.sin(t * 9 + i * .31) + 20 * math.sin(t * 15 + i)
            d.polygon([(i - 18, VIDEO_H), (i, VIDEO_H - h), (i + 18, VIDEO_H)], fill=col + (200,))
            d.polygon([(i - 9, VIDEO_H), (i, VIDEO_H - h * .6), (i + 9, VIDEO_H)], fill=(255, 220, 120, 220))
    elif kind == "skulls":
        base.alpha_composite(skull_img, (8, VIDEO_H - 60))
        base.alpha_composite(skull_img, (VIDEO_W - 58, VIDEO_H - 60))


# ------------------------------------------------------------------ главная функция
def render_card_video(card_file, out_path, name, rarity_label, font_path=None):
    th = _theme(rarity_label)
    col = th["accent"]
    seed = sum(ord(ch) for ch in name) % 100000
    rnd = random.Random(seed)

    total = int(VIDEO_SECONDS * VIDEO_FPS)
    dist, ang = _make_bg_tools()

    back_base = _card_back(col)
    sym_size = 190
    symbol = _symbol(th["symbol"], sym_size, col)
    skull_small = _symbol("skull", 48, th["accent"])
    face = _card_face(card_file, col)

    items = [(rnd.uniform(0, VIDEO_W), rnd.uniform(0, VIDEO_H), rnd.uniform(.5, 1.6), rnd.uniform(0, 6.28))
             for _ in range(26)]
    particles = []
    for _ in range(70):
        a = rnd.uniform(0, 6.28)
        r0 = rnd.uniform(200, 420)
        ta = rnd.uniform(0, 6.28)
        tr = rnd.uniform(0, sym_size * .38)
        particles.append(dict(
            a=a, r0=r0, tx=CARD_CX + math.cos(ta) * tr, ty=CARD_CY + math.sin(ta) * tr,
            delay=rnd.uniform(0, .35), size=rnd.uniform(1.5, 3.8)))

    f_name = _font(font_path, 38)
    f_rar = _font(font_path, 26)
    title = name
    while f_name.getlength(title) > VIDEO_W - 30 and f_name.size > 18:
        f_name = _font(font_path, f_name.size - 2)
    rar_text = _plain(rarity_label)

    tmp = out_path + ".tmp.mp4"
    proc = subprocess.Popen(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{VIDEO_W}x{VIDEO_H}",
         "-r", str(VIDEO_FPS), "-i", "-",
         "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "24",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-f", "mp4", tmp],
        stdin=subprocess.PIPE)
    try:
        for fi in range(total):
            t = fi / (total - 1)
            sec = fi / VIDEO_FPS
            base = _bg_frame(th, dist, ang, sec, 0.6 + 0.6 * _ease(t / 0.5))
            d = ImageDraw.Draw(base, "RGBA")
            _decor(th["decor"], d, items, sec, col, None)
            _draw_ground(th["decor"], base, sec, th, skull_small)
            d = ImageDraw.Draw(base, "RGBA")

            # --- карта
            flip_p = _ease((t - 0.60) / 0.18)
            if t < 0.60:
                layer = back_base.copy()
                sa = _ease(t / 0.5)
                sym = symbol.copy()
                sym.putalpha(sym.getchannel("A").point(lambda v: int(v * sa)))
                layer.alpha_composite(sym, ((BACK_W - sym_size) // 2, (BACK_H - sym_size) // 2))
                intro = 0.85 + 0.15 * _ease(t / 0.12)
                shake = 1.0 + 0.012 * math.sin(sec * 30) * _ease((t - .45) / .15)
                s_y = intro * shake
                w = int(BACK_W * s_y)
                h = int(BACK_H * s_y)
                layer = layer.resize((w, h), Image.LANCZOS)
            else:
                sx = abs(math.cos(math.pi * flip_p))
                if flip_p < 0.5:
                    layer = back_base.resize((max(2, int(BACK_W * sx)), BACK_H), Image.LANCZOS)
                else:
                    layer = face.resize((max(2, int(face.width * sx)), face.height), Image.LANCZOS)
            lw, lh = layer.size
            base.alpha_composite(layer, (CARD_CX - lw // 2, CARD_CY - lh // 2))

            # --- частицы (до переворота)
            if t < 0.62:
                pr = (t / 0.5)
                for p in particles:
                    k = _ease(pr * 1.25 - p["delay"])
                    rr = p["r0"] * (1 - k)
                    ang_p = p["a"] + (1 - k) * 2.4
                    x = p["tx"] * k + (CARD_CX + math.cos(ang_p) * rr) * (1 - k)
                    y = p["ty"] * k + (CARD_CY + math.sin(ang_p) * rr) * (1 - k)
                    s = p["size"]
                    d.ellipse((x - s, y - s, x + s, y + s), fill=col + (int(220 * (1 - _ease((t - .5) / .12))),))

            # --- вспышка при перевороте
            flash = max(0.0, 1 - abs(t - 0.66) / 0.07) * 0.55
            if flash > 0:
                base.alpha_composite(Image.new("RGBA", base.size, (255, 255, 255, int(255 * flash))))

            # --- текст
            ta = _ease((t - 0.80) / 0.12)
            if ta > 0:
                txt = Image.new("RGBA", base.size, (0, 0, 0, 0))
                td = ImageDraw.Draw(txt)
                ny = 505 - int(12 * (1 - ta))
                td.text((VIDEO_W // 2, ny), title, font=f_name, fill=(255, 255, 255, int(255 * ta)),
                        anchor="mm", stroke_width=2, stroke_fill=(0, 0, 0, int(200 * ta)))
                td.text((VIDEO_W // 2, ny + 50), rar_text, font=f_rar, fill=col + (int(255 * ta),),
                        anchor="mm", stroke_width=2, stroke_fill=(0, 0, 0, int(200 * ta)))
                base.alpha_composite(txt)

            proc.stdin.write(np.ascontiguousarray(np.asarray(base.convert("RGB"))).tobytes())
        proc.stdin.close()
        if proc.wait() != 0:
            raise RuntimeError("ffmpeg завершился с ошибкой")
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
        raise
    os.replace(tmp, out_path)
    return out_path


if __name__ == "__main__":
    import sys
    f = sys.argv[1] if len(sys.argv) > 1 else "test.png"
    render_card_video(f, "test_out.mp4", "Пожиратель тыкв", sys.argv[2] if len(sys.argv) > 2 else "💀 Скелетная", None)
    print("ok")
