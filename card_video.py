"""
card_video.py — детальная анимация открытия карточки (3 секунды).

Сцена фона зависит от редкости (кладбище / ад / токсичный город / космос / королевская),
рубашка карты с орнаментом, вращающимся медальоном и символом редкости,
частицы -> переворот со вспышкой -> карта, название и редкость.

Нужно: pillow, numpy, imageio-ffmpeg
"""
import math
import os
import random
import subprocess

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont
import imageio_ffmpeg

VIDEO_W, VIDEO_H = 480, 640
VIDEO_FPS = 20
VIDEO_SECONDS = 3.0

CARD_CX, CARD_CY = 240, 250
BACK_W, BACK_H = 300, 440
FACE = 380
WHITE = (255, 255, 255)


# =============================================================== ТЕМЫ
def _t(bg_in, bg_out, ray, accent, symbol, scene, moon=None, deco=()):
    return dict(bg_in=bg_in, bg_out=bg_out, ray=ray, accent=accent, symbol=symbol,
                scene=scene, moon=moon, deco=tuple(deco))


THEMES = [
    ("скелет",   _t((105, 110, 115), (8, 10, 14), (235, 235, 225), (240, 240, 228), "skull", "graveyard",
                    moon=(235, 235, 225), deco=("bones", "skulls", "fog"))),
    ("демон",    _t((255, 80, 25), (45, 0, 0), (255, 130, 40), (255, 150, 70), "pentagram", "hell",
                    deco=("flames", "embers", "bats", "bigring"))),
    ("призрач",  _t((125, 175, 225), (8, 18, 38), (205, 232, 255), (235, 245, 255), "ghost", "graveyard",
                    moon=(215, 235, 255), deco=("ghosts", "fog"))),
    ("тыквен",   _t((255, 135, 25), (35, 8, 0), (255, 175, 60), (255, 155, 35), "pumpkin", "graveyard",
                    moon=(255, 200, 90), deco=("pumpkins", "bats", "embers", "fog"))),
    ("ведьм",    _t((155, 75, 225), (20, 0, 38), (195, 125, 255), (205, 145, 255), "hat", "graveyard",
                    moon=(215, 170, 255), deco=("bats", "stars", "fog", "bigring"))),
    ("вампир",   _t((195, 15, 45), (28, 0, 6), (255, 55, 85), (255, 75, 95), "drop", "graveyard",
                    moon=(255, 70, 70), deco=("bats", "embers", "fog"))),
    ("кошмар",   _t((175, 0, 125), (10, 0, 18), (255, 65, 205), (255, 115, 225), "skull", "graveyard",
                    moon=(255, 120, 220), deco=("eyes", "ghosts", "fog", "bigring"))),
    ("зараж",    _t((95, 195, 45), (5, 28, 6), (155, 255, 85), (175, 255, 95), "biohazard", "toxic",
                    deco=("bubbles", "drips", "fog"))),
    ("токсич",   _t((205, 235, 25), (22, 28, 0), (235, 255, 65), (238, 255, 75), "radiation", "toxic",
                    deco=("bubbles", "drips", "fog", "bigring"))),
    ("мутир",    _t((35, 225, 155), (0, 28, 22), (85, 255, 205), (105, 255, 215), "biohazard", "toxic",
                    deco=("bubbles", "drips", "fog", "bigring"))),
    ("ядерн",    _t((255, 195, 25), (38, 14, 0), (255, 225, 65), (255, 218, 55), "radiation", "toxic",
                    deco=("embers", "fog", "bigring"))),
    ("критическ", _t((255, 65, 15), (42, 0, 0), (255, 145, 35), (255, 125, 45), "radiation", "hell",
                     deco=("flames", "embers", "bigring"))),
    ("отчужд",   _t((115, 45, 205), (0, 0, 10), (225, 205, 255), (232, 218, 255), "void", "cosmic",
                    deco=("stars", "bigring"))),
    ("бесконеч", _t((65, 205, 255), (18, 0, 45), (255, 125, 255), (175, 242, 255), "void", "cosmic",
                    deco=("stars", "sparkles", "bigring"))),
    ("специаль", _t((35, 205, 225), (0, 20, 32), (125, 255, 255), (145, 255, 255), "star", "cosmic",
                    deco=("stars", "sparkles"))),
    ("секретн",  _t((35, 165, 75), (0, 20, 10), (105, 255, 145), (125, 255, 155), "star", "royal",
                    deco=("embers", "sparkles", "bigring"))),
    ("легендар", _t((255, 195, 35), (38, 20, 0), (255, 232, 105), (255, 212, 75), "crown", "royal",
                    deco=("sparkles", "bigring"))),
    ("эпическ",  _t((165, 65, 235), (20, 0, 38), (215, 145, 255), (212, 152, 255), "gem", "royal",
                    deco=("sparkles", "bigring"))),
    ("редк",     _t((55, 135, 255), (0, 12, 38), (135, 195, 255), (145, 205, 255), "gem", "royal",
                    deco=("sparkles",))),
    ("обычн",    _t((135, 140, 150), (16, 17, 22), (215, 220, 230), (225, 230, 240), "gem", "royal",
                    deco=("sparkles",))),
]
DEFAULT_THEME = _t((110, 110, 125), (10, 10, 16), (210, 210, 230), (225, 225, 240), "gem", "royal",
                   deco=("sparkles",))


def _plain(s):
    return "".join(ch for ch in s if ch.isalnum() or ch in " -").strip()


def _theme(label):
    low = _plain(label).lower()
    for key, th in THEMES:
        if key in low:
            return th
    return DEFAULT_THEME


# =============================================================== УТИЛИТЫ
def _clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def _ease(x):
    x = _clamp(x)
    return x * x * (3 - 2 * x)


def _ease_out(x):
    x = _clamp(x)
    return 1 - (1 - x) ** 3


def _out_back(x):
    x = _clamp(x)
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def _mix(a, b, k):
    return tuple(int(a[i] * (1 - k) + b[i] * k) for i in range(3))


def _shade(c, k):
    return tuple(max(0, min(255, int(v * k))) for v in c)


def _font(path, size):
    for p in (path, "DejaVuSans-Bold.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _rr_mask(w, h, radius, inset=0):
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle((inset, inset, w - 1 - inset, h - 1 - inset), radius=radius, fill=255)
    return m


def _comp(dst, src, x, y):
    """alpha_composite с безопасным клиппингом (допускает отрицательные координаты)."""
    x, y = int(x), int(y)
    W, H = dst.size
    w, h = src.size
    sx0, sy0 = max(0, -x), max(0, -y)
    sx1, sy1 = min(w, W - x), min(h, H - y)
    if sx1 <= sx0 or sy1 <= sy0:
        return
    dst.alpha_composite(src, (x + sx0, y + sy0), (sx0, sy0, sx1, sy1))


def _pasteA(dst_rgb, src_rgba, x, y):
    """Вставка RGBA-спрайта в RGB-картинку с блендингом."""
    dst_rgb.paste(src_rgba.convert("RGB"), (int(x), int(y)), src_rgba.getchannel("A"))


_SPR = {}


def _spr(r, color, alpha=1.0, power=2.0):
    """Радиальное свечение (кэшируется)."""
    key = (r, color, round(alpha, 2), power)
    if key in _SPR:
        return _SPR[key]
    ys, xs = np.mgrid[-r:r, -r:r].astype(np.float32)
    d = np.sqrt(xs * xs + ys * ys) / r
    a = np.clip(1 - d, 0, 1) ** power * alpha
    arr = np.zeros((2 * r, 2 * r, 4), np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2] = color
    arr[..., 3] = np.clip(a * 255, 0, 255).astype(np.uint8)
    im = Image.fromarray(arr, "RGBA")
    if len(_SPR) > 400:
        _SPR.clear()
    _SPR[key] = im
    return im


def _fade(img, k):
    if k >= 0.995:
        return img
    out = img.copy()
    out.putalpha(out.getchannel("A").point(lambda v: int(v * k)))
    return out


# =============================================================== СИМВОЛЫ
def _symbol(kind, S, col):
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = S / 2
    r = S * 0.42
    fill = tuple(col) + (255,)
    dark = (8, 8, 12, 255)

    if kind == "skull":
        d.ellipse((c - .85 * r, c - r, c + .85 * r, c + .3 * r), fill=fill)
        d.rounded_rectangle((c - .5 * r, c - .1 * r, c + .5 * r, c + .9 * r), radius=8, fill=fill)
        for sx in (-1, 1):
            d.ellipse((c + sx * .35 * r - .22 * r, c - .35 * r, c + sx * .35 * r + .22 * r, c + .09 * r), fill=dark)
        d.polygon([(c, c + .02 * r), (c - .1 * r, c + .3 * r), (c + .1 * r, c + .3 * r)], fill=dark)
        for i in range(-2, 3):
            x = c + i * .2 * r
            d.line((x, c + .55 * r, x, c + .9 * r), fill=dark, width=max(2, S // 50))
    elif kind == "pentagram":
        d.ellipse((c - r, c - r, c + r, c + r), outline=fill, width=max(3, S // 28))
        pts = [(c + .95 * r * math.cos(math.radians(-90 + 72 * k)),
                c + .95 * r * math.sin(math.radians(-90 + 72 * k))) for k in range(5)]
        for i in range(5):
            d.line((pts[i], pts[(i + 2) % 5]), fill=fill, width=max(3, S // 28))
    elif kind == "ghost":
        d.ellipse((c - .6 * r, c - r, c + .6 * r, c + .2 * r), fill=fill)
        pts = [(c - .6 * r, c)]
        for i in range(7):
            pts.append((c - .6 * r + 1.2 * r * i / 6, c + (.95 * r if i % 2 == 0 else .6 * r)))
        pts.append((c + .6 * r, c))
        d.polygon(pts, fill=fill)
        for sx in (-1, 1):
            d.ellipse((c + sx * .25 * r - .1 * r, c - .4 * r, c + sx * .25 * r + .1 * r, c - .1 * r), fill=dark)
        d.ellipse((c - .12 * r, c, c + .12 * r, c + .3 * r), fill=dark)
    elif kind == "pumpkin":
        d.ellipse((c - .95 * r, c - .6 * r, c + .95 * r, c + .85 * r), fill=fill)
        d.ellipse((c - .5 * r, c - .6 * r, c + .5 * r, c + .85 * r), outline=dark, width=max(2, S // 50))
        d.rectangle((c - .08 * r, c - .95 * r, c + .1 * r, c - .55 * r), fill=(60, 130, 40, 255))
        for sx in (-1, 1):
            d.polygon([(c + sx * .45 * r, c - .25 * r), (c + sx * .2 * r, c + .1 * r),
                       (c + sx * .7 * r, c + .1 * r)], fill=dark)
        d.polygon([(c - .5 * r, c + .3 * r), (c - .25 * r, c + .55 * r), (c, c + .35 * r),
                   (c + .25 * r, c + .55 * r), (c + .5 * r, c + .3 * r), (c + .3 * r, c + .7 * r),
                   (c - .3 * r, c + .7 * r)], fill=dark)
    elif kind == "radiation":
        d.ellipse((c - r, c - r, c + r, c + r), outline=fill, width=max(3, S // 32))
        for a0 in (-120, 0, 120):
            d.pieslice((c - .9 * r, c - .9 * r, c + .9 * r, c + .9 * r), a0, a0 + 60, fill=fill)
        d.ellipse((c - .3 * r, c - .3 * r, c + .3 * r, c + .3 * r), fill=dark)
        d.ellipse((c - .18 * r, c - .18 * r, c + .18 * r, c + .18 * r), fill=fill)
    elif kind == "biohazard":
        for k in range(3):
            a = math.radians(-90 + 120 * k)
            x, y = c + .42 * r * math.cos(a), c + .42 * r * math.sin(a)
            d.ellipse((x - .5 * r, y - .5 * r, x + .5 * r, y + .5 * r), outline=fill, width=max(4, S // 20))
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
        d.line((c - r, c + .4 * r, c + r, c + .4 * r), fill=dark, width=max(2, S // 40))
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
            d.ellipse((c - rr, c - rr, c + rr, c + rr), outline=fill, width=max(3, S // 32))
        d.ellipse((c - .12 * r, c - .12 * r, c + .12 * r, c + .12 * r), fill=fill)
    else:  # gem
        d.polygon([(c - r, c - .2 * r), (c - .55 * r, c - .8 * r), (c + .55 * r, c - .8 * r),
                   (c + r, c - .2 * r), (c, c + .95 * r)], fill=fill)
        w = max(2, S // 50)
        d.line((c - r, c - .2 * r, c + r, c - .2 * r), fill=dark, width=w)
        d.line((c - .55 * r, c - .8 * r, c - .25 * r, c - .2 * r, c, c + .95 * r), fill=dark, width=w)
        d.line((c + .55 * r, c - .8 * r, c + .25 * r, c - .2 * r, c, c + .95 * r), fill=dark, width=w)
    return img


# =============================================================== СПРАЙТЫ СЦЕНЫ
def _tree(d, x, y, length, ang, depth, width, rnd, col):
    if depth == 0 or length < 6:
        return
    x2 = x + math.cos(ang) * length
    y2 = y + math.sin(ang) * length
    d.line((x, y, x2, y2), fill=col, width=max(1, int(width)))
    for _ in range(2 if rnd.random() < .8 else 3):
        _tree(d, x2, y2, length * rnd.uniform(.66, .8), ang + rnd.uniform(-.75, .75),
              depth - 1, width * .68, rnd, col)


def _bone(d, x, y, L, ang, col, w=5):
    dx, dy = math.cos(ang) * L / 2, math.sin(ang) * L / 2
    d.line((x - dx, y - dy, x + dx, y + dy), fill=col, width=w)
    px, py = -math.sin(ang) * w * .7, math.cos(ang) * w * .7
    for sx in (-1, 1):
        ex, ey = x + sx * dx, y + sx * dy
        for o in (-1, 1):
            r = w * .75
            d.ellipse((ex + o * px - r, ey + o * py - r, ex + o * px + r, ey + o * py + r), fill=col)


def _bat(d, x, y, s, flap, col):
    fl = math.sin(flap)
    for sx in (-1, 1):
        pts = [(x, y), (x + sx * s * .5, y - s * .35 - s * .2 * fl),
               (x + sx * s * 1.1, y - s * .1 - s * .6 * fl),
               (x + sx * s * .85, y + s * .05 - s * .2 * fl),
               (x + sx * s * .6, y + s * .2), (x + sx * s * .35, y + s * .05), (x, y + s * .25)]
        d.polygon(pts, fill=col)
    d.ellipse((x - s * .14, y - s * .2, x + s * .14, y + s * .25), fill=col)
    d.polygon([(x - s * .12, y - s * .15), (x - s * .08, y - s * .38), (x - s * .02, y - s * .2)], fill=col)
    d.polygon([(x + s * .12, y - s * .15), (x + s * .08, y - s * .38), (x + s * .02, y - s * .2)], fill=col)


def _moon(L, cx, cy, r, color):
    L.alpha_composite(_spr(int(r * 3.4), color, 0.55, 2.2), (int(cx - r * 3.4), int(cy - r * 3.4))) \
        if cx - r * 3.4 >= 0 and cy - r * 3.4 >= 0 else _comp(L, _spr(int(r * 3.4), color, 0.55, 2.2),
                                                             cx - r * 3.4, cy - r * 3.4)
    d = ImageDraw.Draw(L)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=_mix(color, WHITE, .55) + (255,))
    rnd = random.Random(7)
    for _ in range(7):
        a = rnd.uniform(0, 6.28)
        rr = rnd.uniform(0, r * .6)
        cr = rnd.uniform(r * .08, r * .2)
        x, y = cx + math.cos(a) * rr, cy + math.sin(a) * rr
        d.ellipse((x - cr, y - cr, x + cr, y + cr), fill=_mix(color, WHITE, .3) + (255,))


def _ground(L, col, rnd, rocks=False):
    d = ImageDraw.Draw(L)
    W, H = VIDEO_W, VIDEO_H
    pts = [(0, H)]
    if rocks:
        x = 0
        while x <= W + 20:
            pts.append((x, H - rnd.randint(18, 70)))
            x += rnd.randint(14, 30)
            pts.append((x, H - rnd.randint(8, 25)))
    else:
        for x in range(0, W + 1, 8):
            pts.append((x, H - 46 + math.sin(x * .02) * 10 + math.sin(x * .05) * 5))
    pts.append((W, H))
    d.polygon(pts, fill=tuple(col) + (255,))
    if not rocks:
        for x in (20, 70, 118, 360, 408, 450):
            h = rnd.randint(30, 52)
            y = H - 44 - h + 8
            if rnd.random() < .4:
                d.rectangle((x + 8, y - 8, x + 14, y + h), fill=tuple(col) + (255,))
                d.rectangle((x, y + 6, x + 22, y + 12), fill=tuple(col) + (255,))
            else:
                d.rounded_rectangle((x, y, x + 24, y + h), radius=11, fill=tuple(col) + (255,))


def _skyline(L, col, lit, rnd):
    d = ImageDraw.Draw(L)
    W, H = VIDEO_W, VIDEO_H
    x = -10
    while x < W:
        w = rnd.randint(36, 72)
        h = rnd.randint(90, 240)
        top = H - h
        pts = [(x, H), (x, top)]
        steps = rnd.randint(2, 4)
        for i in range(1, steps + 1):
            pts.append((x + w * i / steps, top + rnd.randint(-14, 20)))
        pts.append((x + w, H))
        d.polygon(pts, fill=tuple(col) + (255,))
        if rnd.random() < .5:
            d.rectangle((x + w * .6, top - 22, x + w * .6 + 6, top + 6), fill=tuple(col) + (255,))
        for wy in range(top + 22, H - 40, 22):
            for wx in range(int(x) + 8, int(x + w) - 8, 16):
                if rnd.random() < .16:
                    d.rectangle((wx, wy, wx + 6, wy + 9), fill=tuple(lit) + (210,))
        x += w + rnd.randint(-6, 8)


def _rune_ring(S, col, rnd, sym=None):
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = S / 2
    u = S / 232.0
    colA = tuple(col) + (255,)
    for rr, w in ((c - 3 * u, max(2, int(3 * u))), (c - 14 * u, 1), (c * .70, max(1, int(2 * u)))):
        d.ellipse((c - rr, c - rr, c + rr, c + rr), outline=colA, width=w)
    for i in range(72):
        a = math.radians(i * 5)
        l = 9 * u if i % 6 == 0 else 5 * u
        r1 = c - 14 * u
        d.line((c + math.cos(a) * r1, c + math.sin(a) * r1,
                c + math.cos(a) * (r1 - l), c + math.sin(a) * (r1 - l)), fill=colA, width=max(1, int(u)))
    for i in range(24):
        a = math.radians(i * 15 + 7)
        rr = c - 28 * u
        x, y = c + math.cos(a) * rr, c + math.sin(a) * rr
        for _ in range(3):
            d.line((x + rnd.uniform(-5, 5) * u, y + rnd.uniform(-5, 5) * u,
                    x + rnd.uniform(-5, 5) * u, y + rnd.uniform(-5, 5) * u), fill=colA, width=max(1, int(2 * u)))
    if sym:
        s = _symbol(sym, int(c * 1.0), col)
        _comp(img, s, c - s.width / 2, c - s.height / 2)
    return img


def _fog_tex(col, seed):
    rs = np.random.RandomState(seed)
    small = rs.rand(8, 16).astype(np.float32)
    im = Image.fromarray((small * 255).astype(np.uint8), "L").resize((960, 360), Image.BICUBIC)
    a = np.asarray(im).astype(np.float32) / 255
    a = np.clip((a - .35) * 1.7, 0, 1)
    vy = np.linspace(0, 1, 360, dtype=np.float32)[:, None] ** 1.4
    a = a * vy * .38
    arr = np.zeros((360, 960, 4), np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2] = _mix(col, WHITE, .3)
    arr[..., 3] = (a * 255).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


# =============================================================== ФОН
def _gradient_bg(th):
    W, H = VIDEO_W, VIDEO_H
    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.clip(np.sqrt((xs - CARD_CX) ** 2 + (ys - CARD_CY) ** 2) / 430, 0, 1)
    a = np.array(th["bg_in"], np.float32)
    b = np.array(th["bg_out"], np.float32)
    k = (d ** .8)[..., None]
    arr = a * (1 - k) + b * k
    arr = arr * .6 + b * .4
    arr *= (1 - .25 * (ys / H))[..., None]
    return arr.astype(np.float32)


def _build_static(th, rnd):
    W, H = VIDEO_W, VIDEO_H
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(L)
    col = th["accent"]
    sil = _shade(th["bg_out"], .5)
    sc = th["scene"]
    st = {"pumpkins": []}

    if th["moon"]:
        _moon(L, 392, 80, 40, th["moon"])

    if sc == "graveyard":
        _tree(d, 34, H - 30, 95, -1.25, 8, 11, rnd, sil + (255,))
        _tree(d, W - 34, H - 30, 90, -1.9, 8, 11, rnd, sil + (255,))
        _ground(L, sil, rnd)
    elif sc == "hell":
        _ground(L, sil, rnd, rocks=True)
    elif sc == "toxic":
        _skyline(L, sil, _mix(col, WHITE, .2), rnd)
        _ground(L, sil, rnd, rocks=False)
        # слизь сверху
        pts = [(0, 0)] + [(x, 14 + math.sin(x * .05) * 6) for x in range(0, W + 1, 10)] + [(W, 0)]
        d.polygon(pts, fill=col + (150,))
        for _ in range(9):
            x = rnd.randint(10, W - 10)
            ln = rnd.randint(30, 110)
            d.rounded_rectangle((x - 3, 0, x + 3, ln), radius=3, fill=col + (170,))
            d.ellipse((x - 6, ln - 4, x + 6, ln + 10), fill=col + (190,))
    elif sc == "cosmic":
        neb = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        nd = ImageDraw.Draw(neb)
        for i in range(6):
            cc = _mix(th["bg_in"], th["ray"], rnd.random())
            x, y = rnd.randint(-40, W + 40), rnd.randint(-40, H + 40)
            r = rnd.randint(90, 190)
            nd.ellipse((x - r, y - r * .7, x + r, y + r * .7), fill=cc + (70,))
        neb = neb.filter(ImageFilter.GaussianBlur(40))
        L.alpha_composite(neb)
        d = ImageDraw.Draw(L)
        for _ in range(170):
            x, y = rnd.randint(0, W - 1), rnd.randint(0, H - 1)
            r = rnd.choice((1, 1, 1, 2))
            a = rnd.randint(90, 230)
            d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, a))
        px, py, pr = 70, 560, 46
        d.ellipse((px - pr, py - pr, px + pr, py + pr), fill=_shade(th["bg_in"], .55) + (255,))
        d.ellipse((px - pr + 8, py - pr + 8, px + pr - 22, py + pr - 22), fill=_shade(th["bg_in"], .75) + (255,))
        d.arc((px - 90, py - 22, px + 90, py + 22), 200, 340, fill=col + (200,), width=3)
        d.arc((px - 78, py - 16, px + 78, py + 16), 200, 340, fill=col + (140,), width=2)
    else:  # royal
        for (x, y, sx, sy) in ((0, 0, 1, 1), (W, 0, -1, 1), (0, H, 1, -1), (W, H, -1, -1)):
            a0 = {(1, 1): 0, (-1, 1): 90, (-1, -1): 180, (1, -1): 270}[(sx, sy)]
            for r, w in ((46, 3), (70, 2), (96, 1)):
                d.arc((x - r, y - r, x + r, y + r), a0, a0 + 90, fill=col + (150,), width=w)
            px, py = x + sx * 26, y + sy * 26
            d.polygon([(px, py - 8), (px + 8, py), (px, py + 8), (px - 8, py)], fill=col + (200,))
        d.rounded_rectangle((8, 8, W - 9, H - 9), radius=18, outline=col + (90,), width=1)
        d.rounded_rectangle((14, 14, W - 15, H - 15), radius=14, outline=col + (50,), width=1)

    if "bones" in th["deco"]:
        for _ in range(9):
            if rnd.random() < .5:
                x = rnd.choice((rnd.randint(12, 75), rnd.randint(405, 468)))
                y = rnd.randint(110, 520)
            else:
                x, y = rnd.randint(20, 460), rnd.randint(500, 600)
            _bone(d, x, y, rnd.randint(30, 52), rnd.uniform(0, 3.14), (228, 228, 212, 215), 5)
    if "skulls" in th["deco"]:
        sk = _symbol("skull", 52, (232, 232, 218))
        _comp(L, sk, 6, H - 62)
        _comp(L, sk, W - 58, H - 62)
        _comp(L, _symbol("skull", 34, (200, 200, 190)), 64, H - 44)
    if "pumpkins" in th["deco"]:
        for (x, y, s) in ((46, H - 52, 46), (W - 50, H - 50, 52), (118, H - 36, 30)):
            pk = _symbol("pumpkin", s * 2, col)
            _comp(L, pk, x - s, y - s)
            st["pumpkins"].append((x, y))
    return L, st


# =============================================================== РУБАШКА И ЛИЦО
def _corner_orn(d, x, y, sx, sy, col, dim):
    a0 = {(1, 1): 0, (-1, 1): 90, (-1, -1): 180, (1, -1): 270}[(sx, sy)]
    for r, w in ((14, 2), (24, 2), (34, 1)):
        d.arc((x - r, y - r, x + r, y + r), a0, a0 + 90, fill=col, width=w)
    px, py = x + sx * 9, y + sy * 9
    d.polygon([(px, py - 5), (px + 5, py), (px, py + 5), (px - 5, py)], fill=col)
    d.line((x + sx * 40, y + sy * 5, x + sx * 76, y + sy * 5), fill=dim, width=1)
    d.line((x + sx * 5, y + sy * 40, x + sx * 5, y + sy * 76), fill=dim, width=1)
    for (ex, ey) in ((x + sx * 82, y + sy * 5), (x + sx * 5, y + sy * 82), (x + sx * 52, y + sy * 5), (x + sx * 5, y + sy * 52)):
        d.ellipse((ex - 2.5, ey - 2.5, ex + 2.5, ey + 2.5), fill=col)


def _make_back(th):
    W, H = BACK_W, BACK_H
    col = th["accent"]
    dim = _shade(col, .5)
    dk = _shade(col, .13)
    cx, cy = W / 2, H / 2

    ys = np.linspace(0, 1, H, dtype=np.float32).reshape(H, 1, 1)
    body = np.array(_shade(col, .11), np.float32) * (1 - ys) + np.array(_shade(col, .03), np.float32) * ys
    body = np.broadcast_to(body, (H, W, 3)).copy()
    gy, gx = np.mgrid[0:H, 0:W].astype(np.float32)
    dd = np.sqrt((gx - cx) ** 2 + (gy - cy) ** 2) / 230
    body += np.array(col, np.float32) * .12 * (np.clip(1 - dd, 0, 1) ** 2)[..., None]
    img = Image.fromarray(np.clip(body, 0, 255).astype(np.uint8), "RGB")

    # решётка и лучи
    lat = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lat)
    for k in range(-H, W + H, 22):
        ld.line((k, 0, k + H, H), fill=col + (32,), width=1)
        ld.line((k + H, 0, k, H), fill=col + (32,), width=1)
    for i in range(36):
        a0, a1 = math.radians(i * 10), math.radians(i * 10 + 3.5)
        ld.polygon([(cx, cy), (cx + math.cos(a0) * 320, cy + math.sin(a0) * 320),
                    (cx + math.cos(a1) * 320, cy + math.sin(a1) * 320)], fill=col + (24,))
    lat.putalpha(ImageChops.multiply(lat.getchannel("A"), _rr_mask(W, H, 18, 12)))
    _pasteA(img, lat, 0, 0)

    # свечение медальона
    gl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(gl).ellipse((cx - 100, cy - 100, cx + 100, cy + 100), fill=col + (150,))
    _pasteA(img, gl.filter(ImageFilter.GaussianBlur(16)), 0, 0)

    d = ImageDraw.Draw(img, "RGBA")
    # рамки
    def rr(inset, rad, c, w):
        d.rounded_rectangle((inset, inset, W - 1 - inset, H - 1 - inset), radius=rad, outline=c, width=w)
    rr(0, 24, col + (255,), 5)
    rr(6, 19, dim + (255,), 2)
    rr(12, 14, col + (210,), 1)
    rr(18, 10, dim + (255,), 1)
    rr(26, 6, col + (130,), 1)

    # фаски
    d.line((8, 3, W - 9, 3), fill=(255, 255, 255, 90), width=1)
    d.line((3, 8, 3, H - 9), fill=(255, 255, 255, 60), width=1)
    d.line((8, H - 4, W - 9, H - 4), fill=(0, 0, 0, 120), width=1)

    # уголки
    for (x, y, sx, sy) in ((26, 26, 1, 1), (W - 27, 26, -1, 1), (26, H - 27, 1, -1), (W - 27, H - 27, -1, -1)):
        _corner_orn(d, x, y, sx, sy, col + (255,), dim + (255,))

    # боковые орнаменты
    for x in (22, W - 23):
        d.line((x, cy - 70, x, cy - 20), fill=dim + (255,), width=1)
        d.line((x, cy + 20, x, cy + 70), fill=dim + (255,), width=1)
        d.polygon([(x, cy - 8), (x + 6, cy), (x, cy + 8), (x - 6, cy)], fill=col + (255,))

    # верхняя и нижняя эмблемы
    sm = _symbol(th["symbol"], 38, col)
    _pasteA(img, sm, cx - 19, 30)
    _pasteA(img, sm.rotate(180), cx - 19, H - 68)
    for y in (49, H - 49):
        d.line((cx - 70, y, cx - 28, y), fill=dim + (255,), width=1)
        d.line((cx + 28, y, cx + 70, y), fill=dim + (255,), width=1)
        for x in (cx - 76, cx + 76):
            d.polygon([(x, y - 4), (x + 4, y), (x, y + 4), (x - 4, y)], fill=col + (255,))

    # медальон
    d.ellipse((cx - 96, cy - 96, cx + 96, cy + 96), fill=dk + (255,), outline=col + (255,), width=3)
    d.ellipse((cx - 86, cy - 86, cx + 86, cy + 86), outline=dim + (255,), width=1)
    d.ellipse((cx - 104, cy - 104, cx + 104, cy + 104), outline=dim + (255,), width=1)
    for i in range(72):
        a = math.radians(i * 5)
        l = 6 if i % 6 == 0 else 3
        d.line((cx + math.cos(a) * 96, cy + math.sin(a) * 96, cx + math.cos(a) * (96 + l), cy + math.sin(a) * (96 + l)),
               fill=col + (200,), width=1)
    for (ax, ay) in ((0, -1), (1, 0), (0, 1), (-1, 0)):
        x, y = cx + ax * 112, cy + ay * 112
        d.polygon([(x, y - 6), (x + 6, y), (x, y + 6), (x - 6, y)], fill=col + (255,))
    _pasteA(img, _spr(90, col, .30, 1.6), cx - 90, cy - 90)

    # мягкое внутреннее свечение рамки
    edge = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(edge).rounded_rectangle((3, 3, W - 4, H - 4), radius=22, outline=col + (255,), width=5)
    edge = edge.filter(ImageFilter.GaussianBlur(5))
    edge.putalpha(edge.getchannel("A").point(lambda v: int(v * .55)))
    _pasteA(img, edge, 0, 0)

    out = img.convert("RGBA")
    out.putalpha(_rr_mask(W, H, 24))
    return out


def _make_face(path, th):
    col = th["accent"]
    dim = _shade(col, .45)
    try:
        art = Image.open(path).convert("RGB")
    except Exception:
        art = Image.new("RGB", (FACE, FACE), (40, 40, 50))
    w, h = art.size
    s = min(w, h)
    art = art.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s)).resize((FACE, FACE), Image.LANCZOS)
    B = 12
    T = FACE + 2 * B
    gy, gx = np.mgrid[0:T, 0:T].astype(np.float32)
    k = ((gx + gy) / (2 * T))[..., None]
    c1 = np.array(_mix(col, WHITE, .55), np.float32)
    c2 = np.array(dim, np.float32)
    g = (c1 * (1 - k) + c2 * k) * (.85 + .3 * np.sin(k * 10) ** 2)
    img = Image.fromarray(np.clip(g, 0, 255).astype(np.uint8), "RGB")
    d = ImageDraw.Draw(img, "RGBA")
    d.rounded_rectangle((4, 4, T - 5, T - 5), radius=30, outline=(0, 0, 0, 150), width=2)
    img.paste(art, (B, B), _rr_mask(FACE, FACE, 26))
    d.rounded_rectangle((B - 1, B - 1, B + FACE, B + FACE), radius=27, outline=(0, 0, 0, 170), width=2)
    d.rounded_rectangle((B + 4, B + 4, B + FACE - 5, B + FACE - 5), radius=22, outline=col + (110,), width=1)
    for (x, y) in ((13, 13), (T - 14, 13), (13, T - 14), (T - 14, T - 14)):
        d.polygon([(x, y - 9), (x + 9, y), (x, y + 9), (x - 9, y)], fill=col + (255,), outline=(255, 255, 255, 230))
        d.polygon([(x, y - 4), (x + 4, y), (x, y + 4), (x - 4, y)], fill=(255, 255, 255, 200))
    for (x, y) in ((T // 2, 6), (T // 2, T - 7), (6, T // 2), (T - 7, T // 2)):
        d.polygon([(x, y - 5), (x + 5, y), (x, y + 5), (x - 5, y)], fill=col + (255,), outline=(255, 255, 255, 200))
    out = img.convert("RGBA")
    out.putalpha(_rr_mask(T, T, 34))
    return out


def _sheen(size, alpha_arr, u, pos, strength):
    band = np.exp(-((u - pos) / .06) ** 2) * strength
    lay = np.zeros((size[1], size[0], 4), np.uint8)
    lay[..., :3] = 255
    lay[..., 3] = np.clip(band * alpha_arr * 255, 0, 255).astype(np.uint8)
    return Image.fromarray(lay, "RGBA")


def _u_grid(w, h):
    gy, gx = np.mgrid[0:h, 0:w].astype(np.float32)
    return (gx + gy * .55) / (w + h * .55)


# =============================================================== КОНТЕКСТ
def _build_ctx(card_file, name, rarity_label, font_path):
    th = _theme(rarity_label)
    col = th["accent"]
    seed = sum(ord(ch) for ch in name + rarity_label) % 100000
    rnd = random.Random(seed)
    W, H = VIDEO_W, VIDEO_H
    c = {"th": th, "col": col}

    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    dx, dy = xs - CARD_CX, ys - CARD_CY
    c["dist"] = np.clip(np.sqrt(dx * dx + dy * dy) / 480.0, 0, 1)
    c["ang"] = np.arctan2(dy, dx)
    c["bg"] = _gradient_bg(th)
    c["static"], st = _build_static(th, rnd)

    sym_for_ring = th["symbol"] if th["symbol"] in ("pentagram", "radiation", "biohazard", "void") else None
    c["bgring"] = _rune_ring(560, col, random.Random(seed + 1), sym_for_ring)
    c["mring"] = _rune_ring(232, col, random.Random(seed + 2))
    c["sym"] = _symbol(th["symbol"], 150, col)
    c["back"] = _make_back(th)
    c["face"] = _make_face(card_file, th)
    c["back_alpha"] = np.asarray(c["back"].getchannel("A")).astype(np.float32) / 255
    c["face_alpha"] = np.asarray(c["face"].getchannel("A")).astype(np.float32) / 255
    c["back_u"] = _u_grid(*c["back"].size)
    c["face_u"] = _u_grid(*c["face"].size)
    c["shadow"] = _spr(150, (0, 0, 0), .55, 1.2).resize((300, 56))
    c["fogs"] = [(_fog_tex(col, seed + 3), 18), (_fog_tex(col, seed + 4), 34)] if "fog" in th["deco"] else []

    st["stars"] = [(rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(.5, 1.6), rnd.uniform(0, 6.28))
                   for _ in range(70 if th["scene"] == "cosmic" else 36)]
    st["embers"] = [(rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(.4, 1.2), rnd.uniform(0, 6.28)) for _ in range(38)]
    st["bubbles"] = [(rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(.4, 1.2), rnd.uniform(0, 6.28)) for _ in range(16)]
    st["drops"] = [(rnd.uniform(20, W - 20), rnd.uniform(60, 300), rnd.uniform(.5, 1.0)) for _ in range(6)]
    st["ghosts"] = [(rnd.uniform(20, W - 20), rnd.uniform(60, 520), rnd.randint(34, 60), rnd.uniform(.25, .5), rnd.uniform(0, 6.28))
                    for _ in range(6)]
    st["bats"] = [(rnd.uniform(0, W + 120), rnd.uniform(40, 230), rnd.uniform(55, 120), rnd.choice((-1, 1)),
                   rnd.uniform(16, 32), rnd.uniform(0, 6.28)) for _ in range(5)]
    st["eyes"] = [(rnd.uniform(15, W - 15), rnd.uniform(120, 560), rnd.uniform(0, 6.28)) for _ in range(6)]
    st["sparkles"] = [(rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(.5, 1.5), rnd.uniform(0, 6.28)) for _ in range(24)]
    c["st"] = st

    prt = []
    for _ in range(72):
        a = rnd.uniform(0, 6.28)
        ta = rnd.uniform(0, 6.28)
        tr = rnd.uniform(0, 55)
        prt.append(dict(a=a, r0=rnd.uniform(200, 440), tx=CARD_CX + math.cos(ta) * tr, ty=CARD_CY + math.sin(ta) * tr,
                        delay=rnd.uniform(0, .35), size=rnd.uniform(1.4, 3.6)))
    c["prt"] = prt
    c["sparks"] = [dict(a=rnd.uniform(0, 6.28), v=rnd.uniform(160, 560), life=rnd.uniform(.5, 1.1), w=rnd.choice((1, 2, 2, 3)))
                   for _ in range(120)]
    c["twinkle"] = [(rnd.uniform(0, 6.28), rnd.uniform(215, 262), rnd.uniform(0, 6.28)) for _ in range(16)]

    c["f_name"] = _font(font_path, 40)
    while c["f_name"].getlength(name) > 410 and c["f_name"].size > 18:
        c["f_name"] = _font(font_path, c["f_name"].size - 2)
    c["f_rar"] = _font(font_path, 25)
    c["name"] = name
    c["rar"] = _plain(rarity_label)
    return c


# =============================================================== ДЕКОР (динамика)
def _decor_dynamic(c, ov, d, sec, t):
    th, col, dec, st = c["th"], c["col"], c["th"]["deco"], c["st"]
    W, H = VIDEO_W, VIDEO_H
    fade = _ease(t / .15)

    if "flames" in dec:
        _comp(ov, _spr(300, col, .45 * fade, 1.5), 240 - 300, H - 300)
        for k in range(3):
            cc = (_shade(col, .6), col, (255, 225, 130))[k]
            al = (210, 230, 235)[k]
            for i in range(-1, 13):
                x = i * 42 + k * 14
                w = 34 - 6 * k
                h = ((70 - 14 * k) + 25 * math.sin(sec * 8 + i * 1.3 + k) + 12 * math.sin(sec * 13 + i * .7)) * (.55 if k == 2 else 1) * fade
                sway = math.sin(sec * 6 + i) * 6
                d.polygon([(x - w, H), (x - w * .4, H - h * .5), (x + sway, H - h), (x + w * .4, H - h * .5), (x + w, H)],
                          fill=tuple(cc) + (al,))
    if "stars" in dec:
        for (x, y, s, ph) in st["stars"]:
            tw = .5 + .5 * math.sin(sec * 6 + ph)
            r = 1 + s * 2.4 * tw
            cc = tuple(_mix(col, WHITE, .5)) + (int(70 + 160 * tw),)
            d.line((x - r, y, x + r, y), fill=cc, width=1)
            d.line((x, y - r, x, y + r), fill=cc, width=1)
        if th["scene"] == "cosmic":
            p = (sec / 1.3) % 1
            if p < .4:
                k = p / .4
                x, y = 440 - 380 * k, 40 + 260 * k
                for j in range(14):
                    kk = max(0, k - j * .012)
                    d.ellipse((440 - 380 * kk - 2 + j * 0, 40 + 260 * kk - 2, 440 - 380 * kk + 2, 40 + 260 * kk + 2),
                              fill=(255, 255, 255, int(220 * (1 - j / 14) * (1 - k * .5))))
    if "embers" in dec:
        for (x, y0, s, ph) in st["embers"]:
            yy = (y0 - sec * 110 * (.5 + s * .4)) % H
            xx = x + math.sin(sec * 3 + ph) * 12
            _comp(ov, _spr(6, col, .8, 1.5), xx - 6, yy - 6)
            d.ellipse((xx - s, yy - s, xx + s, yy + s), fill=tuple(_mix(col, WHITE, .6)) + (230,))
    if "bubbles" in dec:
        for (x, y0, s, ph) in st["bubbles"]:
            yy = (y0 - sec * 70 * (.4 + s * .3)) % H
            xx = x + math.sin(sec * 2 + ph) * 8
            r = 4 + s * 8
            d.ellipse((xx - r, yy - r, xx + r, yy + r), outline=tuple(col) + (170,), width=2)
            d.ellipse((xx - r * .5, yy - r * .5, xx - r * .15, yy - r * .15), fill=(255, 255, 255, 180))
    if "drips" in dec:
        for (x, y0, s) in st["drops"]:
            yy = (y0 + sec * 160 * s) % (H * .8)
            d.ellipse((x - 3, yy - 5, x + 3, yy + 6), fill=tuple(col) + (200,))
    if "ghosts" in dec:
        gc = _mix(col, WHITE, .6)
        for (x, y, s, al, ph) in st["ghosts"]:
            g = _fade(_symbol("ghost", s, gc), al * (.6 + .4 * math.sin(sec * 2 + ph)) * fade)
            _comp(ov, g, x + math.sin(sec * .8 + ph) * 14 - s / 2, y + math.sin(sec * 1.7 + ph) * 10 - s / 2)
    if "bats" in dec:
        for (x0, y0, sp, dr, s, ph) in st["bats"]:
            x = (x0 + dr * sp * sec) % (W + 120) - 60
            y = y0 + math.sin(sec * 2 + ph) * 14
            _bat(d, x, y, s, sec * 14 + ph, (10, 8, 12, 235))
    if "eyes" in dec:
        for (x, y, ph) in st["eyes"]:
            v = math.sin(sec * 2 + ph)
            if v > -.3:
                a = _clamp((v + .3) * 2)
                for ex in (x - 7, x + 7):
                    _comp(ov, _spr(9, col, .8 * a, 1.4), ex - 9, y - 9)
                    d.ellipse((ex - 2.5, y - 1.5, ex + 2.5, y + 1.5), fill=(255, 240, 240, int(255 * a)))
    if "pumpkins" in dec:
        for (x, y) in st["pumpkins"]:
            fl = .55 + .25 * math.sin(sec * 9 + x) + .1 * math.sin(sec * 17 + y)
            _comp(ov, _spr(60, col, fl, 1.6), x - 60, y - 60)
    if "sparkles" in dec:
        for (x, y0, s, ph) in st["sparkles"]:
            yy = (y0 - sec * 24 * s) % H
            tw = max(0, math.sin(sec * 5 + ph))
            r = 3 + 8 * s * tw
            cc = tuple(_mix(col, WHITE, .6)) + (int(220 * tw),)
            d.line((x - r, yy, x + r, yy), fill=cc, width=1)
            d.line((x, yy - r, x, yy + r), fill=cc, width=1)
            d.line((x - r * .5, yy - r * .5, x + r * .5, yy + r * .5), fill=cc, width=1)
            d.line((x - r * .5, yy + r * .5, x + r * .5, yy - r * .5), fill=cc, width=1)


# =============================================================== КАДР
def _back_layer(c, sec, t):
    col = c["col"]
    back = c["back"].copy()
    bw, bh = back.size
    ring = c["mring"].rotate(-sec * 28, resample=Image.BICUBIC)
    _comp(back, _fade(ring, .85), (bw - ring.width) // 2, (bh - ring.height) // 2)
    sa = _ease((t - .08) / .42)
    pulse = .85 + .15 * math.sin(sec * 9)
    cx, cy = bw // 2, bh // 2
    _comp(back, _spr(95, col, .6 * sa * pulse, 1.6), cx - 95, cy - 95)
    _comp(back, _fade(c["sym"], sa), cx - c["sym"].width // 2, cy - c["sym"].height // 2)
    charge = _ease((t - .5) / .12)
    if charge > 0:
        _comp(back, _spr(115, WHITE, .65 * charge, 1.8), cx - 115, cy - 115)
    pos = (sec * .6) % 1.7 - .35
    back.alpha_composite(_sheen(back.size, c["back_alpha"], c["back_u"], pos, .32))
    return back


def _face_layer(c, sec, t):
    face = c["face"].copy()
    pos = ((t - .75) * 4.2) - .3
    face.alpha_composite(_sheen(face.size, c["face_alpha"], c["face_u"], pos, .38))
    return face


def _frame(c, fi, total):
    th, col = c["th"], c["col"]
    W, H = VIDEO_W, VIDEO_H
    t = fi / (total - 1)
    sec = fi / VIDEO_FPS
    boost = max(0.0, 1 - (t - .68) / .22) if t > .68 else 0.0

    # --- фон + лучи
    ray_s = .4 + .9 * _ease(t / .55) + 1.1 * boost
    rays = (.5 + .5 * np.sin(c["ang"] * 16 + sec * 1.8)) ** 6 * np.exp(-c["dist"] * 1.6) * ray_s
    arr = c["bg"] + np.array(th["ray"], np.float32) * (rays * .5)[..., None]
    base = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB").convert("RGBA")

    a = (.42 if "bigring" in th["deco"] else .16) * (.7 + .3 * math.sin(sec * 2)) * _ease(t / .15)
    ring = _fade(c["bgring"].rotate(sec * 9, resample=Image.BICUBIC), a)
    _comp(base, ring, CARD_CX - ring.width // 2, CARD_CY - ring.height // 2)
    _comp(base, c["static"], 0, 0)
    for tex, sp in c["fogs"]:
        off = int((sec * sp) % 480)
        _comp(base, tex.crop((off, 0, off + W, tex.height)), 0, H - tex.height)

    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    _decor_dynamic(c, ov, ImageDraw.Draw(ov), sec, t)
    _comp(base, ov, 0, 0)

    # --- аура и тень
    aura = (.22 + .18 * math.sin(sec * 4)) * _ease(t / .2) + .5 * boost
    _comp(base, _spr(300, col, min(1.0, aura), 1.7), CARD_CX - 300, CARD_CY - 300)
    _comp(base, _fade(c["shadow"], _ease(t / .15)), CARD_CX - 150, CARD_CY + BACK_H // 2 + 4)

    # --- карта
    flip_p = _ease((t - .62) / .17)
    if t < .62 or flip_p < .5:
        layer = _back_layer(c, sec, t)
    else:
        layer = _face_layer(c, sec, t)
    if t >= .62:
        sx = abs(math.cos(math.pi * flip_p))
        sy = 1 + .07 * math.sin(math.pi * flip_p)
        layer = layer.resize((max(2, int(layer.width * sx)), int(layer.height * sy)), Image.BILINEAR)
    if t < .18:
        k = t / .18
        sc = .5 + .5 * _out_back(k)
        layer = layer.resize((max(2, int(layer.width * sc)), max(2, int(layer.height * sc))), Image.BILINEAR)
        layer = layer.rotate((1 - _ease(k)) * -14, expand=True, resample=Image.BILINEAR)
        layer = _fade(layer, _ease(t / .1))
    elif .79 < t < .91:
        sc = 1 + .05 * (1 - _ease((t - .79) / .12))
        layer = layer.resize((int(layer.width * sc), int(layer.height * sc)), Image.BILINEAR)
    bob = math.sin(sec * 3) * 3 if t < .6 else 0
    shk = math.sin(sec * 70) * 4 * _ease((t - .48) / .12) if t < .62 else 0
    _comp(base, layer, CARD_CX + shk - layer.width / 2, CARD_CY + bob - layer.height / 2)

    # --- эффекты
    fx = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fx)
    if .1 < t < .6:
        for k in range(3):
            ph = ((t - .1) / .45 + k / 3) % 1
            r = 300 * (1 - ph) + 100
            al = int(170 * ph * (1 - _ease((t - .5) / .1)))
            fd.ellipse((CARD_CX - r, CARD_CY - r, CARD_CX + r, CARD_CY + r), outline=tuple(col) + (al,), width=2)
    if t < .64:
        pr = (t - .06) / .5
        fo = 1 - _ease((t - .5) / .12)
        for p in c["prt"]:
            k = _ease(pr * 1.25 - p["delay"])
            rr = p["r0"] * (1 - k)
            ap = p["a"] + (1 - k) * 2.4
            x = p["tx"] * k + (CARD_CX + math.cos(ap) * rr) * (1 - k)
            y = p["ty"] * k + (CARD_CY + math.sin(ap) * rr) * (1 - k)
            if k > 0.001 or pr > 0:
                _comp(fx, _spr(7, col, .7 * fo, 1.5), x - 7, y - 7)
                s = p["size"]
                fd.ellipse((x - s, y - s, x + s, y + s), fill=tuple(_mix(col, WHITE, .5)) + (int(230 * fo),))
    if t >= .66:
        dtb = (t - .66) * VIDEO_SECONDS
        if dtb < .6:
            k = dtb / .6
            r = 60 + 650 * _ease_out(k)
            fd.ellipse((CARD_CX - r, CARD_CY - r, CARD_CX + r, CARD_CY + r),
                       outline=tuple(_mix(col, WHITE, .5)) + (int(220 * (1 - k)),), width=max(1, int(7 * (1 - k))))
            r2 = r * .7
            fd.ellipse((CARD_CX - r2, CARD_CY - r2, CARD_CX + r2, CARD_CY + r2),
                       outline=tuple(col) + (int(150 * (1 - k)),), width=2)
        for sp in c["sparks"]:
            if dtb > sp["life"]:
                continue
            def pos(tt):
                dist = sp["v"] * (1 - math.exp(-3 * tt)) / 3
                return (CARD_CX + math.cos(sp["a"]) * dist, CARD_CY + math.sin(sp["a"]) * dist + 160 * tt * tt)
            x1, y1 = pos(dtb)
            x0, y0 = pos(max(0, dtb - .035))
            al = int(255 * (1 - dtb / sp["life"]))
            fd.line((x0, y0, x1, y1), fill=tuple(_mix(col, WHITE, .55)) + (al,), width=sp["w"])
    if t > .82:
        ka = _ease((t - .82) / .1)
        for (ang, rad, ph) in c["twinkle"]:
            x, y = CARD_CX + math.cos(ang) * rad * .95, CARD_CY + math.sin(ang) * rad * .95
            tw = max(0, math.sin(sec * 7 + ph)) * ka
            r = 3 + 11 * tw
            cc = tuple(_mix(col, WHITE, .6)) + (int(235 * tw),)
            fd.line((x - r, y, x + r, y), fill=cc, width=2)
            fd.line((x, y - r, x, y + r), fill=cc, width=2)
            fd.line((x - r * .5, y - r * .5, x + r * .5, y + r * .5), fill=cc, width=1)
            fd.line((x - r * .5, y + r * .5, x + r * .5, y - r * .5), fill=cc, width=1)
    _comp(base, fx, 0, 0)

    flash = max(0.0, 1 - abs(t - .705) / .05) * .75
    if flash > 0:
        _comp(base, Image.new("RGBA", (W, H), (255, 255, 255, int(255 * flash))), 0, 0)

    # --- плашка с названием
    if t > .79:
        ta = _ease((t - .80) / .12)
        bw = int(432 * _ease((t - .79) / .1))
        tl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        td = ImageDraw.Draw(tl)
        if bw > 12:
            x0, x1 = 240 - bw // 2, 240 + bw // 2
            td.rounded_rectangle((x0, 470, x1, 598), radius=16, fill=(6, 6, 10, int(180 * ta)),
                                 outline=tuple(col) + (int(230 * ta),), width=2)
            td.rounded_rectangle((x0 + 5, 475, x1 - 5, 593), radius=12, outline=tuple(col) + (int(90 * ta),), width=1)
        if ta > 0:
            ny = 508 - int(14 * (1 - ta))
            td.text((240, ny), c["name"], font=c["f_name"], fill=(255, 255, 255, int(255 * ta)), anchor="mm",
                    stroke_width=2, stroke_fill=(0, 0, 0, int(210 * ta)))
            lw = int(120 * ta)
            td.line((240 - lw, 534, 240 + lw, 534), fill=tuple(col) + (int(200 * ta),), width=1)
            td.polygon([(240, 529), (245, 534), (240, 539), (235, 534)], fill=tuple(col) + (int(255 * ta),))
            tw_ = c["f_rar"].getlength(c["rar"])
            td.text((240, 566), c["rar"], font=c["f_rar"], fill=tuple(col) + (int(255 * ta),), anchor="mm",
                    stroke_width=2, stroke_fill=(0, 0, 0, int(210 * ta)))
            for sx in (-1, 1):
                dxm = 240 + sx * (tw_ / 2 + 22)
                td.polygon([(dxm, 560), (dxm + 6, 566), (dxm, 572), (dxm - 6, 566)], fill=tuple(col) + (int(255 * ta),))
                td.line((dxm + sx * 12, 566, dxm + sx * 56, 566), fill=tuple(col) + (int(170 * ta),), width=1)
        _comp(base, tl, 0, 0)

    out = np.asarray(base.convert("RGB"))
    f = .35 + .65 * _ease(t / .08)
    if f < .995:
        out = (out.astype(np.float32) * f).astype(np.uint8)
    return out


# =============================================================== ГЛАВНАЯ ФУНКЦИЯ
def render_card_video(card_file, out_path, name, rarity_label, font_path=None):
    c = _build_ctx(card_file, name, rarity_label, font_path)
    total = int(VIDEO_SECONDS * VIDEO_FPS)
    tmp = out_path + ".tmp.mp4"
    proc = subprocess.Popen(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{VIDEO_W}x{VIDEO_H}",
         "-r", str(VIDEO_FPS), "-i", "-",
         "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-f", "mp4", tmp],
        stdin=subprocess.PIPE)
    try:
        for fi in range(total):
            proc.stdin.write(np.ascontiguousarray(_frame(c, fi, total)).tobytes())
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



# =============================================================== ОБЩАЯ ЗАПИСЬ ВИДЕО
def _write_video(out_path, W, H, fps, total, frame_fn):
    tmp = out_path + ".tmp.mp4"
    proc = subprocess.Popen(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
         "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-f", "mp4", tmp],
        stdin=subprocess.PIPE)
    try:
        for fi in range(total):
            proc.stdin.write(np.ascontiguousarray(frame_fn(fi)).tobytes())
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


# =============================================================== COLOR DICE: падающие цвета
DICE_W, DICE_H = 480, 560
DICE_FPS = 20
DICE_DROP_START = 0.55
DICE_DROP_GAP = 0.72
DICE_SECONDS = DICE_DROP_START + 3 * DICE_DROP_GAP + 0.95 + 1.0

DICE_COLORS = {
    "blue": (50, 115, 255), "red": (240, 50, 62), "yellow": (255, 207, 40),
    "green": (50, 205, 95), "purple": (165, 85, 235), "orange": (255, 145, 30),
}
_DICE_ORDER = ["blue", "red", "yellow", "green", "purple", "orange"]
_DX = [78, 186, 294, 402]          # центры слотов
_WIN_Y = 106                        # центр окна раздатчика
_Y_REST = 456                       # центр шара на дне
_BALL_R = 34
_GRAV = 2600.0
_BALLS = {}


def _ball_sprite(code, R):
    key = (code, R)
    if key in _BALLS:
        return _BALLS[key]
    base = np.array(DICE_COLORS[code], np.float32)
    S = 2 * R + 4
    ys, xs = np.mgrid[0:S, 0:S].astype(np.float32)
    dx, dy = (xs - S / 2) / R, (ys - S / 2) / R
    r2 = dx * dx + dy * dy
    nz = np.sqrt(np.clip(1 - r2, 0, 1))
    L = np.array([-.45, -.55, .7], np.float32)
    L /= np.linalg.norm(L)
    nl = dx * L[0] + dy * L[1] + nz * L[2]
    diff = np.clip(nl, 0, 1)
    spec = np.clip(2 * nl * nz - L[2], 0, 1) ** 28
    col = base[None, None, :] * (.26 + .9 * diff)[..., None] + 255 * (spec * .85)[..., None]
    col += 70 * ((1 - nz) ** 3)[..., None] * (base / 255)[None, None, :]
    # блик-окошко
    hl = np.exp(-(((dx + .38) / .22) ** 2 + ((dy + .42) / .13) ** 2)) * .55
    col += 255 * hl[..., None]
    alpha = np.clip((1 - np.sqrt(r2)) * R * .9, 0, 1)
    arr = np.zeros((S, S, 4), np.uint8)
    arr[..., :3] = np.clip(col, 0, 255).astype(np.uint8)
    arr[..., 3] = (alpha * 255).astype(np.uint8)
    im = Image.fromarray(arr, "RGBA")
    _BALLS[key] = im
    return im


def _dice_static(font_path):
    W, H = DICE_W, DICE_H
    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.clip(np.sqrt((xs - 240) ** 2 + (ys - 300) ** 2) / 420, 0, 1)[..., None]
    arr = np.array((40, 24, 78), np.float32) * (1 - d) + np.array((6, 4, 16), np.float32) * d
    # неоновая сетка внизу
    grid = np.zeros((H, W), np.float32)
    for gy in range(330, H, 22):
        grid[gy:gy + 1, :] = .10
    for gx in range(-240, W + 240, 40):
        for yy in range(330, H):
            xx = int(gx + (gx - 240) * (yy - 330) / 300)
            if 0 <= xx < W:
                grid[yy, xx] = .08
    arr += grid[..., None] * np.array((180, 120, 255), np.float32)
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")
    d = ImageDraw.Draw(img, "RGBA")

    # рамка
    d.rounded_rectangle((6, 6, W - 7, H - 7), radius=22, outline=(190, 130, 255, 200), width=2)
    d.rounded_rectangle((12, 12, W - 13, H - 13), radius=18, outline=(190, 130, 255, 80), width=1)

    # заголовок со свечением
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    f = _font(font_path, 34)
    ImageDraw.Draw(glow).text((240, 38), "COLOR DICE", font=f, fill=(200, 140, 255, 255), anchor="mm")
    img.paste(glow.filter(ImageFilter.GaussianBlur(8)).convert("RGB"), (0, 0),
              glow.filter(ImageFilter.GaussianBlur(8)).getchannel("A"))
    d.text((240, 38), "COLOR DICE", font=f, fill=(255, 255, 255, 255), anchor="mm",
           stroke_width=2, stroke_fill=(60, 20, 110, 255))

    # раздатчик
    d.rounded_rectangle((24, 62, 456, 152), radius=22, fill=(30, 28, 50, 255), outline=(120, 120, 165, 255), width=3)
    d.line((40, 68, 440, 68), fill=(255, 255, 255, 70), width=2)
    for i, x in enumerate(_DX):
        d.ellipse((x - 46, _WIN_Y - 46, x + 46, _WIN_Y + 46), fill=(8, 8, 16, 255), outline=(150, 150, 195, 255), width=3)
        d.ellipse((x - 40, _WIN_Y - 40, x + 40, _WIN_Y + 40), outline=(60, 60, 90, 255), width=2)
        d.polygon([(x - 20, 152), (x + 20, 152), (x + 12, 164), (x - 12, 164)], fill=(60, 60, 90, 255))

    # задняя часть пробирок
    for x in _DX:
        d.rounded_rectangle((x - 48, 190, x + 48, 522), radius=26, fill=(8, 10, 24, 235),
                            outline=(110, 90, 160, 255), width=2)
        for k in range(9):
            yy = 210 + k * 36
            d.line((x - 40, yy, x - 30, yy), fill=(160, 130, 220, 90), width=1)
    # номера
    fn = _font(font_path, 22)
    for i, x in enumerate(_DX):
        d.ellipse((x - 17, 528, x + 17, 560 - 2), fill=(30, 20, 60, 255), outline=(190, 130, 255, 255), width=2)
        d.text((x, 544), str(i + 1), font=fn, fill=(255, 255, 255, 255), anchor="mm")
    return img.convert("RGBA")


def _dice_glass():
    W, H = DICE_W, DICE_H
    g = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(g)
    for x in _DX:
        d.rounded_rectangle((x - 48, 190, x + 48, 522), radius=26, outline=(230, 220, 255, 150), width=3)
        d.rounded_rectangle((x - 40, 200, x - 32, 500), radius=4, fill=(255, 255, 255, 38))
        d.rounded_rectangle((x + 30, 214, x + 35, 440), radius=2, fill=(255, 255, 255, 22))
        d.ellipse((x - 44, 514, x + 44, 526), fill=(255, 255, 255, 30))
    return g


def _simulate_ball(release, total):
    ys = [None] * total
    impacts = []
    y, v, t_cur, rest = float(_WIN_Y), 0.0, release, False
    dt = 1.0 / (DICE_FPS * 10)
    for fi in range(total):
        tf = fi / DICE_FPS
        if tf < release:
            continue
        while t_cur < tf:
            t_cur += dt
            if rest:
                continue
            v += _GRAV * dt
            y += v * dt
            if y >= _Y_REST:
                y = float(_Y_REST)
                if v > 150:
                    impacts.append(t_cur)
                v = -v * .36
                if abs(v) < 60:
                    v, rest = 0.0, True
        ys[fi] = y
    return ys, impacts


def render_dice_video(result_codes, out_path, font_path=None):
    """result_codes — 4 кода цветов ('blue', 'red', ...) в порядке падения."""
    W, H = DICE_W, DICE_H
    total = int(DICE_SECONDS * DICE_FPS)
    bg = _dice_static(font_path)
    glass = _dice_glass()
    rnd = random.Random(sum(ord(ch) for ch in "".join(result_codes)))

    balls = []
    for i, code in enumerate(result_codes):
        release = DICE_DROP_START + i * DICE_DROP_GAP
        ys, imp = _simulate_ball(release, total)
        sparks = [(rnd.uniform(-1, 1), rnd.uniform(160, 380), rnd.uniform(.3, .7)) for _ in range(12)]
        balls.append(dict(code=code, rel=release, ys=ys, imp=imp[0] if imp else None, sparks=sparks,
                          seq=[rnd.randrange(6) for _ in range(40)]))

    def frame(fi):
        tf = fi / DICE_FPS
        base = bg.copy()
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)
        for i, b in enumerate(balls):
            x = _DX[i]
            col = DICE_COLORS[b["code"]]
            R = _BALL_R
            # --- окно раздатчика: перебор цветов до броска
            if tf < b["rel"]:
                if tf > .05:
                    left = b["rel"] - tf
                    interval = 2 if left > 0.6 else (3 if left > 0.3 else 4)
                    idx = (fi // interval + i * 2) % 6
                    code = _DICE_ORDER[idx] if left > 0.18 else b["code"]
                else:
                    code = _DICE_ORDER[i % 6]
                c0 = DICE_COLORS[code]
                _comp(ov, _spr(58, c0, .55, 1.6), x - 58, _WIN_Y - 58)
                spr = _ball_sprite(code, R)
                _comp(ov, spr, x - spr.width // 2, _WIN_Y - spr.height // 2)
            else:
                # окно горит цветом выпавшего шара
                od.ellipse((x - 44, _WIN_Y - 44, x + 44, _WIN_Y + 44), outline=tuple(col) + (200,), width=4)
                _comp(ov, _spr(54, col, .35, 1.8), x - 54, _WIN_Y - 54)
                y = b["ys"][fi]
                prev = b["ys"][fi - 1] if fi > 0 and b["ys"][fi - 1] is not None else y
                # шлейф
                if y - prev > 25:
                    for k in range(1, 5):
                        _comp(ov, _spr(26, col, .5 * (1 - k / 5), 1.4), x - 26, y - k * 16 - 26)
                sx_, sy_ = 1.0, 1.0
                if b["imp"] is not None and 0 <= tf - b["imp"] < .1:
                    k = 1 - (tf - b["imp"]) / .1
                    sx_, sy_ = 1 + .14 * k, 1 - .2 * k
                spr = _ball_sprite(b["code"], R)
                if sx_ != 1.0:
                    spr = spr.resize((int(spr.width * sx_), int(spr.height * sy_)), Image.BILINEAR)
                bottom_shift = (R * (1 - sy_)) if sy_ != 1.0 else 0
                _comp(ov, spr, x - spr.width // 2, y - spr.height // 2 + bottom_shift)

            # --- эффекты приземления
            if b["imp"] is not None and tf >= b["imp"]:
                dt = tf - b["imp"]
                gl = _clamp(dt / .15) * (.5 + .15 * math.sin(tf * 6 + i))
                _comp(ov, _spr(78, col, gl, 1.5), x - 78, 450 - 78)
                if dt < .4:
                    k = dt / .4
                    r = 26 + 70 * _ease_out(k)
                    od.ellipse((x - r, 506 - r * .28, x + r, 506 + r * .28),
                               outline=tuple(_mix(col, WHITE, .4)) + (int(230 * (1 - k)),), width=3)
                for (ax, v0, life) in b["sparks"]:
                    if dt < life:
                        px = x + ax * 52 * (dt / life) ** .7 * 1.6
                        py = 500 - v0 * dt + 520 * dt * dt
                        od.ellipse((px - 2.5, py - 2.5, px + 2.5, py + 2.5),
                                   fill=tuple(_mix(col, WHITE, .5)) + (int(255 * (1 - dt / life)),))
        base.alpha_composite(ov)
        base.alpha_composite(glass)
        # финальные блики после всех приземлений
        end = DICE_DROP_START + 3 * DICE_DROP_GAP + .85
        if tf > end:
            k = _ease((tf - end) / .4)
            for i, x in enumerate(_DX):
                col = DICE_COLORS[balls[i]["code"]]
                r = 46 + 4 * math.sin(tf * 7 + i)
                fd = ImageDraw.Draw(base)
                _comp(base, _spr(60, col, .25 * k, 1.8), x - 60, 440 - 60)
        f = .4 + .6 * _ease(tf / .25)
        out = np.asarray(base.convert("RGB"))
        if f < .995:
            out = (out.astype(np.float32) * f).astype(np.uint8)
        return out

    return _write_video(out_path, W, H, DICE_FPS, total, frame), (W, H)


# =============================================================== БОСС: плавные переходы
BOSS_CLIP_SECONDS = 1.4
BOSS_FPS = 20


def boss_clip_size(path):
    im = Image.open(path)
    w, h = im.size
    s = 640.0 / max(w, h)
    return max(2, int(w * s) // 2 * 2), max(2, int(h * s) // 2 * 2)


def render_boss_transition(img_normal, img_other, out_path, kind="hurt"):
    """Плавный кроссфейд обычного кадра босса в другой (hurt/attack) и обратно.
    Первый и последний кадры = обычная картинка, поэтому стык с фото незаметен."""
    W, H = boss_clip_size(img_normal)
    a = Image.open(img_normal).convert("RGB").resize((W, H), Image.LANCZOS)
    b = Image.open(img_other).convert("RGB").resize((W, H), Image.LANCZOS)
    red = Image.new("RGB", (W, H), (255, 30, 30))
    white = Image.new("RGB", (W, H), (255, 255, 255))
    total = int(BOSS_CLIP_SECONDS * BOSS_FPS)

    def weight(t):
        if t < .22:
            return _ease(t / .22)
        if t < .55:
            return 1.0
        return 1 - _ease((t - .55) / .45)

    def frame(fi):
        t = fi / (total - 1)
        w = weight(t)
        img = Image.blend(a, b, w)
        zoom, sx, sy = 1.0, 0.0, 0.0
        if kind == "hurt":
            env = max(0.0, 1 - abs(t - .3) / .3)
            fl = max(0.0, 1 - abs(t - .22) / .12) * .5 + .14 * w * (1 - _ease((t - .55) / .45) if t > .55 else 1)
            img = Image.blend(img, red, min(.6, fl))
            sx, sy = math.sin(t * 70) * 12 * env, math.cos(t * 55) * 8 * env
            zoom = 1 + .05 * max(0.0, 1 - abs(t - .22) / .22)
        else:
            if t < .22:
                zw = _ease(t / .22)
            elif t < .45:
                zw = 1.0
            else:
                zw = 1 - _ease((t - .45) / .4)
            zoom = 1 + .14 * zw
            env = max(0.0, 1 - abs(t - .24) / .2)
            img = Image.blend(img, white, max(0.0, 1 - abs(t - .22) / .06) * .4)
            sx, sy = math.sin(t * 80) * 9 * env, math.cos(t * 60) * 6 * env
        if zoom != 1.0 or sx or sy:
            cw, ch = W / zoom, H / zoom
            cx = min(max(W / 2 + sx, cw / 2), W - cw / 2)
            cy = min(max(H / 2 + sy, ch / 2), H - ch / 2)
            img = img.resize((W, H), Image.BILINEAR, box=(cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2))
        return np.asarray(img)

    _write_video(out_path, W, H, BOSS_FPS, total, frame)
    return W, H


if __name__ == "__main__":
    import sys
    f = sys.argv[1] if len(sys.argv) > 1 else "test.png"
    lab = sys.argv[2] if len(sys.argv) > 2 else "💀 Скелетная"
    render_card_video(f, "test_out.mp4", "Пожиратель тыкв", lab, None)
    print("ok")
