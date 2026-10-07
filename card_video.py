"""
card_video.py — короткое видео выпадения карты с тематическим анимированным фоном.

Для каждой редкости свой фон:
  Обычная      — лёгкая пыль
  Редкая       — синие искры
  Эпическая    — фиолетовые шары вокруг карты
  Легендарная  — золотые лучи и золотые искры
  Секретная    — падающие клевера, зелёный туман
  Бесконечная  — звёздное небо, падающие звёзды, радужные лучи
  Специальная  — бирюзовые шестиугольники
  Тыквенная    — огонь и тыквы
  Призрачная   — летающие призраки
  Ведьминская  — пузыри зелья и летучие мыши
  Вампирская   — летучие мыши и красный туман
  Скелетная    — черепа и пепел
  Демоническая — адское пламя
  Кошмарная    — моргающие глаза и черепа

Нужно: Pillow, numpy и ffmpeg (системный или пакет imageio-ffmpeg).
"""
import colorsys
import math
import os
import random
import shutil
import subprocess

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

VIDEO_W, VIDEO_H = 480, 640
FPS = 20
VIDEO_SECONDS = 2.4
N_FRAMES = int(FPS * VIDEO_SECONDS)

W, H = VIDEO_W, VIDEO_H
CARD_CX, CARD_CY = W // 2, int(H * 0.44)


# ------------------------------------------------------------------ ТЕМЫ
# layers: (shape, count, (size_min, size_max), (speed_min, speed_max), direction, colors, alpha)
THEMES = {
    "common": dict(
        top=(30, 32, 40), bot=(10, 10, 16), accent=(200, 200, 215),
        layers=[("dot", 34, (1.2, 2.8), (0.05, 0.12), "up", [(255, 255, 255)], 140)],
    ),
    "rare": dict(
        top=(8, 34, 80), bot=(3, 8, 26), accent=(80, 170, 255),
        layers=[("spark", 18, (2, 4), (0.0, 0.0), "float", [(150, 210, 255)], 200),
                ("dot", 18, (1.2, 2.5), (0.08, 0.16), "up", [(120, 190, 255)], 150)],
    ),
    "epic": dict(
        top=(54, 12, 88), bot=(14, 4, 30), accent=(190, 100, 255),
        layers=[("orb", 14, (3, 6), (0.12, 0.25), "orbit", [(210, 140, 255), (150, 90, 255)], 210),
                ("spark", 10, (2, 4), (0.0, 0.0), "float", [(235, 190, 255)], 190)],
    ),
    "legendary": dict(
        top=(96, 58, 0), bot=(26, 12, 0), accent=(255, 205, 60), rays=(255, 210, 90),
        layers=[("spark", 22, (2, 5), (0.08, 0.2), "up", [(255, 225, 120), (255, 190, 50)], 220),
                ("dot", 20, (1.5, 3), (0.1, 0.2), "up", [(255, 240, 170)], 170)],
    ),
    "secret": dict(
        top=(0, 46, 24), bot=(0, 10, 6), accent=(60, 255, 140), mist=(30, 200, 100),
        layers=[("clover", 16, (4, 8), (0.07, 0.16), "down", [(60, 255, 140), (20, 170, 90)], 150),
                ("dot", 20, (1.2, 2.5), (0.05, 0.12), "up", [(150, 255, 200)], 140)],
    ),
    "infinite": dict(
        top=(22, 0, 64), bot=(0, 0, 12), accent=(150, 120, 255), rays="rainbow", rainbow=True,
        layers=[("star", 60, (1, 2.6), (0.0, 0.0), "float", [(255, 255, 255)], 230),
                ("shoot", 3, (1, 1), (0.9, 1.4), "shoot", [(255, 255, 255)], 230)],
    ),
    "special": dict(
        top=(0, 52, 74), bot=(0, 10, 26), accent=(0, 230, 255),
        layers=[("hex", 14, (6, 16), (0.06, 0.14), "up", [(0, 230, 255), (255, 80, 220)], 170),
                ("spark", 10, (2, 4), (0.0, 0.0), "float", [(200, 255, 255)], 200)],
    ),
    "pumpkin": dict(
        top=(78, 30, 0), bot=(20, 6, 0), accent=(255, 140, 20),
        layers=[("pumpkin", 6, (5, 9), (0.05, 0.1), "float", [(255, 130, 20)], 170),
                ("dot", 30, (1.5, 3.2), (0.12, 0.28), "up", [(255, 200, 60), (255, 120, 20)], 220)],
    ),
    "ghost": dict(
        top=(34, 62, 80), bot=(8, 16, 28), accent=(180, 235, 255), mist=(150, 210, 230),
        layers=[("ghost", 9, (5, 10), (0.04, 0.09), "up", [(220, 245, 255)], 120),
                ("dot", 18, (1.2, 2.4), (0.05, 0.1), "up", [(200, 240, 255)], 120)],
    ),
    "witch": dict(
        top=(46, 10, 68), bot=(8, 20, 10), accent=(150, 255, 80),
        layers=[("bubble", 18, (3, 8), (0.1, 0.22), "up", [(150, 255, 80), (190, 110, 255)], 170),
                ("bat", 4, (4, 6), (0.12, 0.2), "across", [(150, 90, 200)], 210),
                ("spark", 10, (2, 3.5), (0.0, 0.0), "float", [(200, 255, 150)], 190)],
    ),
    "vampire": dict(
        top=(78, 0, 12), bot=(18, 0, 4), accent=(235, 30, 55), mist=(200, 20, 40),
        layers=[("bat", 7, (4, 7), (0.1, 0.22), "across", [(200, 40, 65)], 210),
                ("dot", 12, (2, 3.5), (0.1, 0.2), "down", [(255, 40, 60)], 200)],
    ),
    "skeleton": dict(
        top=(50, 54, 58), bot=(10, 10, 12), accent=(235, 235, 220),
        layers=[("skull", 6, (5, 8), (0.05, 0.1), "float", [(235, 235, 220)], 110),
                ("dot", 34, (1, 2.4), (0.04, 0.1), "down", [(200, 200, 190)], 150)],
    ),
    "demon": dict(
        top=(100, 12, 0), bot=(22, 0, 0), accent=(255, 70, 20), rays=(255, 70, 20),
        layers=[("flame", 22, (4, 9), (0.12, 0.26), "up", [(255, 90, 20), (255, 160, 40)], 190),
                ("dot", 30, (1.2, 2.6), (0.15, 0.3), "up", [(255, 220, 80)], 230)],
    ),
    "nightmare": dict(
        top=(18, 0, 30), bot=(0, 0, 0), accent=(205, 0, 255),
        layers=[("eye", 10, (4, 7), (0.0, 0.0), "float", [(255, 40, 200)], 200),
                ("skull", 3, (6, 9), (0.04, 0.08), "float", [(190, 160, 220)], 90),
                ("spark", 12, (2, 3.5), (0.0, 0.0), "float", [(220, 120, 255)], 190)],
    ),
}

KEYWORDS = [
    ("обычн", "common"), ("редк", "rare"), ("эпическ", "epic"), ("легендар", "legendary"),
    ("секретн", "secret"), ("бесконечн", "infinite"), ("специальн", "special"),
    ("тыквен", "pumpkin"), ("призрачн", "ghost"), ("ведьмин", "witch"),
    ("вампирск", "vampire"), ("скелетн", "skeleton"), ("демонич", "demon"),
    ("кошмарн", "nightmare"),
]


def theme_key(rarity_label):
    low = (rarity_label or "").lower()
    for kw, key in KEYWORDS:
        if kw in low:
            return key
    return "common"


# ------------------------------------------------------------------ ФИГУРЫ
def sh_dot(d, x, y, s, c, **k):
    d.ellipse((x - s, y - s, x + s, y + s), fill=c)


def sh_spark(d, x, y, s, c, **k):
    p = [(x, y - s * 2), (x + s * .4, y - s * .4), (x + s * 2, y), (x + s * .4, y + s * .4),
         (x, y + s * 2), (x - s * .4, y + s * .4), (x - s * 2, y), (x - s * .4, y - s * .4)]
    d.polygon(p, fill=c)


def sh_orb(d, x, y, s, c, **k):
    d.ellipse((x - s * 2.2, y - s * 2.2, x + s * 2.2, y + s * 2.2), fill=c[:3] + (c[3] // 4,))
    d.ellipse((x - s, y - s, x + s, y + s), fill=c)


def sh_ghost(d, x, y, s, c, ph=0, **k):
    s *= 1.6
    d.ellipse((x - s, y - s * 1.2, x + s, y + s * .8), fill=c)
    d.rectangle((x - s, y - s * .2, x + s, y + s * 1.2), fill=c)
    wob = math.sin(ph) * s * .15
    d.polygon([(x - s, y + s * 1.2), (x - s * .5, y + s * 1.7 + wob), (x, y + s * 1.2),
               (x + s * .5, y + s * 1.7 - wob), (x + s, y + s * 1.2)], fill=c)
    eye = (20, 30, 50, min(255, c[3] + 80))
    d.ellipse((x - s * .5, y - s * .35, x - s * .15, y + s * .15), fill=eye)
    d.ellipse((x + s * .15, y - s * .35, x + s * .5, y + s * .15), fill=eye)
    d.ellipse((x - s * .2, y + s * .3, x + s * .2, y + s * .65), fill=eye)


def sh_bat(d, x, y, s, c, ph=0, **k):
    f = math.sin(ph * 3) * s * .9
    for sg in (-1, 1):
        d.polygon([(x, y), (x + sg * s * 1.1, y - s * .9 + f), (x + sg * s * 2.4, y - s * .2 + f),
                   (x + sg * s * 1.8, y + s * .35), (x + sg * s * 1.2, y + s * .1),
                   (x + sg * s * .7, y + s * .45), (x, y + s * .3)], fill=c)
    d.ellipse((x - s * .4, y - s * .5, x + s * .4, y + s * .5), fill=c)
    d.polygon([(x - s * .35, y - s * .4), (x - s * .25, y - s * .9), (x - s * .05, y - s * .45)], fill=c)
    d.polygon([(x + s * .35, y - s * .4), (x + s * .25, y - s * .9), (x + s * .05, y - s * .45)], fill=c)


def sh_flame(d, x, y, s, c, ph=0, **k):
    fl = math.sin(ph * 4) * s * .25
    d.polygon([(x + fl, y - s * 2), (x + s * .9, y - s * .2), (x + s * .6, y + s * .8), (x, y + s),
               (x - s * .6, y + s * .8), (x - s * .9, y - s * .2)], fill=c)
    inner = (255, 235, 140, c[3])
    d.polygon([(x + fl * .5, y - s * .9), (x + s * .4, y + s * .1), (x, y + s * .7), (x - s * .4, y + s * .1)],
              fill=inner)


def sh_hex(d, x, y, s, c, ph=0, **k):
    pts = [(x + math.cos(ph * .3 + i * math.pi / 3) * s, y + math.sin(ph * .3 + i * math.pi / 3) * s)
           for i in range(6)]
    d.polygon(pts, outline=c, width=2)


def sh_clover(d, x, y, s, c, **k):
    r = s * .75
    for dx, dy in ((0, -.7), (-.7, .2), (.7, .2)):
        d.ellipse((x + dx * s - r, y + dy * s - r, x + dx * s + r, y + dy * s + r), fill=c)
    d.rectangle((x - s * .12, y, x + s * .12, y + s * 1.5), fill=c)


def sh_skull(d, x, y, s, c, **k):
    d.ellipse((x - s, y - s, x + s, y + s * .8), fill=c)
    d.rectangle((x - s * .55, y + s * .4, x + s * .55, y + s * 1.2), fill=c)
    dark = (10, 10, 14, min(255, c[3] + 120))
    d.ellipse((x - s * .6, y - s * .3, x - s * .15, y + s * .25), fill=dark)
    d.ellipse((x + s * .15, y - s * .3, x + s * .6, y + s * .25), fill=dark)
    d.polygon([(x, y + s * .2), (x - s * .12, y + s * .5), (x + s * .12, y + s * .5)], fill=dark)


def sh_pumpkin(d, x, y, s, c, **k):
    d.ellipse((x - s * 1.4, y - s, x + s * 1.4, y + s), fill=c)
    d.ellipse((x - s * .7, y - s, x + s * .7, y + s), outline=(120, 50, 0, c[3]), width=2)
    d.rectangle((x - s * .15, y - s * 1.4, x + s * .15, y - s * .8), fill=(60, 110, 20, c[3]))
    dark = (50, 15, 0, min(255, c[3] + 60))
    d.polygon([(x - s * .7, y - s * .2), (x - s * .3, y - s * .2), (x - s * .5, y - s * .6)], fill=dark)
    d.polygon([(x + s * .7, y - s * .2), (x + s * .3, y - s * .2), (x + s * .5, y - s * .6)], fill=dark)
    d.polygon([(x - s * .6, y + s * .3), (x + s * .6, y + s * .3), (x, y + s * .7)], fill=dark)


def sh_bubble(d, x, y, s, c, **k):
    d.ellipse((x - s, y - s, x + s, y + s), outline=c, width=2, fill=c[:3] + (c[3] // 5,))
    d.ellipse((x - s * .5, y - s * .6, x - s * .15, y - s * .25), fill=(255, 255, 255, c[3]))


def sh_eye(d, x, y, s, c, ph=0, **k):
    openness = max(0.08, abs(math.sin(ph)) ** 0.5)
    w, h = s * 2.6, s * 1.3 * openness
    d.ellipse((x - w, y - h, x + w, y + h), fill=c)
    d.ellipse((x - s * .5, y - h * .9, x + s * .5, y + h * .9), fill=(0, 0, 0, c[3]))


SHAPES = {
    "dot": sh_dot, "spark": sh_spark, "star": sh_spark, "orb": sh_orb, "ghost": sh_ghost,
    "bat": sh_bat, "flame": sh_flame, "hex": sh_hex, "clover": sh_clover, "skull": sh_skull,
    "pumpkin": sh_pumpkin, "bubble": sh_bubble, "eye": sh_eye,
}


SIZE_BOOST = {"ghost": 2.3, "bat": 2.0, "skull": 2.0, "pumpkin": 2.0, "clover": 1.9, "hex": 1.5,
              "flame": 1.8, "eye": 1.9, "bubble": 1.6, "orb": 1.5, "spark": 1.5}


class Particle:
    __slots__ = ("shape", "x0", "y0", "spd", "size", "ph", "color", "alpha", "dirn", "amp", "w")


def build_particles(theme, seed):
    rnd = random.Random(seed)
    res = []
    for shape, count, (smin, smax), (vmin, vmax), dirn, colors, alpha in theme["layers"]:
        for _ in range(count):
            p = Particle()
            p.shape = shape
            p.x0 = rnd.random()
            p.y0 = rnd.random()
            p.spd = rnd.uniform(vmin, vmax)
            p.size = rnd.uniform(smin, smax) * SIZE_BOOST.get(shape, 1.0)
            p.ph = rnd.uniform(0, 6.28)
            p.color = rnd.choice(colors)
            p.alpha = alpha
            p.dirn = dirn
            p.amp = rnd.uniform(6, 22)
            p.w = rnd.uniform(1.2, 3.2)
            res.append(p)
    return res


def particle_pos(p, t):
    if p.dirn == "up":
        return p.x0 * W + math.sin(t * p.w + p.ph) * p.amp, H * (1.15 - ((p.y0 + p.spd * t) % 1.3))
    if p.dirn == "down":
        return p.x0 * W + math.sin(t * p.w + p.ph) * p.amp, H * (((p.y0 + p.spd * t) % 1.3) - 0.15)
    if p.dirn == "across":
        return W * (((p.x0 + p.spd * t) % 1.4) - 0.2), p.y0 * H * .8 + math.sin(t * p.w + p.ph) * p.amp * 1.5
    if p.dirn == "orbit":
        ang = p.ph + t * p.spd * 6.28
        return (CARD_CX + math.cos(ang) * (W * .30 + p.x0 * W * .22),
                CARD_CY + math.sin(ang) * (H * .20 + p.y0 * H * .14))
    if p.dirn == "shoot":
        k = (t * p.spd + p.x0) % 1.6
        return W * (1.1 - k * 1.1) + p.y0 * 60, H * (-0.1 + k * 0.6) + p.y0 * 40
    return (p.x0 * W + math.sin(t * p.w * .5 + p.ph) * p.amp,
            p.y0 * H + math.cos(t * p.w * .4 + p.ph) * p.amp * .6)


# ------------------------------------------------------------------ ФОН
def make_gradient(top, bot):
    t = np.linspace(0, 1, H)[:, None, None]
    arr = np.array(top, dtype=float)[None, None, :] * (1 - t) + np.array(bot, dtype=float)[None, None, :] * t
    arr = np.repeat(arr, W, axis=1)
    yy, xx = np.mgrid[0:H, 0:W]
    dist = np.sqrt(((xx - W / 2) / (W * .75)) ** 2 + ((yy - H / 2) / (H * .75)) ** 2)
    arr *= np.clip(1.15 - dist * .55, .35, 1.0)[:, :, None]
    return Image.fromarray(arr.clip(0, 255).astype("uint8"), "RGB")


def make_glow(color):
    yy, xx = np.mgrid[0:H, 0:W]
    dist = np.sqrt(((xx - CARD_CX) / (W * .55)) ** 2 + ((yy - CARD_CY) / (H * .42)) ** 2)
    k = np.clip(1 - dist, 0, 1) ** 2
    arr = np.array(color, dtype=float)[None, None, :] * k[:, :, None] * .55
    return Image.fromarray(arr.clip(0, 255).astype("uint8"), "RGB")


def draw_rays(d, t, color, alpha=34, count=14):
    for i in range(count):
        a0 = t * .5 + i * (2 * math.pi / count)
        a1 = a0 + math.pi / count * .8
        R = H * 1.2
        c = color(i) if callable(color) else color
        d.polygon([(CARD_CX, CARD_CY), (CARD_CX + math.cos(a0) * R, CARD_CY + math.sin(a0) * R),
                   (CARD_CX + math.cos(a1) * R, CARD_CY + math.sin(a1) * R)], fill=c[:3] + (alpha,))


def draw_mist(d, t, color):
    for i in range(5):
        x = (i * .27 + t * .03) % 1.3 * W - W * .15
        y = H * (.72 + .05 * math.sin(t + i))
        r = 110 + i * 12
        d.ellipse((x - r, y - r * .35, x + r, y + r * .35), fill=color[:3] + (22,))


# ------------------------------------------------------------------ КАРТА
def ease_out_back(p):
    c1, c3 = 1.35, 2.35
    return 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2


def make_card_sprite(card_path, accent):
    box_w, box_h = int(W * .72), int(H * .56)
    img = Image.open(card_path).convert("RGBA")
    img.thumbnail((box_w, box_h), Image.LANCZOS)
    pad = 5
    cw, ch = img.size[0] + pad * 2, img.size[1] + pad * 2
    sprite = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    frame = Image.new("RGBA", (cw, ch), accent + (255,))
    mask = Image.new("L", (cw, ch), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, cw - 1, ch - 1), radius=20, fill=255)
    sprite.paste(frame, (0, 0), mask)
    inner = Image.new("L", (img.size[0], img.size[1]), 0)
    ImageDraw.Draw(inner).rounded_rectangle((0, 0, img.size[0] - 1, img.size[1] - 1), radius=16, fill=255)
    sprite.paste(img, (pad, pad), ImageChops.multiply(inner, img.split()[3]))
    return sprite


def make_card_glow(size, accent):
    gw, gh = size[0] + 120, size[1] + 120
    g = Image.new("RGBA", (gw, gh), (0, 0, 0, 0))
    ImageDraw.Draw(g).rounded_rectangle((60, 60, gw - 60, gh - 60), radius=30, fill=accent + (210,))
    return g.filter(ImageFilter.GaussianBlur(28))


def scale_alpha(img, k):
    if k >= 0.999:
        return img
    r, g, b, a = img.split()
    return Image.merge("RGBA", (r, g, b, a.point(lambda v: int(v * k))))


def load_font(path, size):
    for p in (path, "DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size)
    except Exception:
        return ImageFont.load_default()


def strip_emoji(label):
    parts = (label or "").split(" ", 1)
    return parts[1] if len(parts) == 2 else (label or "")


def fit_text(d, text, font_path, size, max_w):
    while size > 14:
        f = load_font(font_path, size)
        if d.textlength(text, font=f) <= max_w:
            return f
        size -= 2
    return load_font(font_path, 14)


# ------------------------------------------------------------------ ВИДЕО
def _ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    exe = shutil.which("ffmpeg")
    if not exe:
        raise RuntimeError("ffmpeg не найден: добавь imageio-ffmpeg в requirements.txt")
    return exe


def render_frames(card_path, name, rarity_label, font_path):
    key = theme_key(rarity_label)
    th = THEMES[key]
    accent = th["accent"]
    seed = sum(ord(ch) for ch in (name or "") + key)
    particles = build_particles(th, seed)

    bg = make_gradient(th["top"], th["bot"])
    glow = make_glow(accent)
    sprite = make_card_sprite(card_path, accent)
    card_glow = make_card_glow(sprite.size, accent)
    sw, sh = sprite.size

    tmp = ImageDraw.Draw(Image.new("RGB", (4, 4)))
    name_font = fit_text(tmp, name, font_path, 34, W * .88)
    label = strip_emoji(rarity_label).upper()
    label_font = load_font(font_path, 22)
    label_w = tmp.textlength(label, font=label_font)

    rainbow = th.get("rainbow", False)

    for i in range(N_FRAMES):
        t = i / FPS
        fade = min(1.0, t / 0.25)

        # фон + пульсирующее свечение
        pulse = (0.75 + 0.25 * math.sin(t * 4)) * fade
        lut = [int(v * pulse) for v in range(256)] * 3
        frame = ImageChops.add(bg, glow.point(lut)).convert("RGBA")

        # лучи / туман / частицы
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov, "RGBA")
        rays = th.get("rays")
        if rays == "rainbow":
            draw_rays(d, t, lambda k_, t_=t: tuple(int(c * 255) for c in colorsys.hsv_to_rgb(((k_ / 14) + t_ * .3) % 1, .7, 1)), 30)
        elif rays:
            draw_rays(d, t, rays, 32)
        if th.get("mist"):
            draw_mist(d, t, th["mist"])

        for p in particles:
            x, y = particle_pos(p, t)
            if x < -40 or x > W + 40 or y < -40 or y > H + 40:
                continue
            a = p.alpha * fade
            if p.shape in ("spark", "star", "eye"):
                a *= 0.55 + 0.45 * math.sin(t * p.w * 2 + p.ph)
            col = p.color
            if rainbow and p.shape in ("star", "shoot"):
                col = tuple(int(c * 255) for c in colorsys.hsv_to_rgb((p.x0 + t * .2) % 1, .35, 1))
            c = col + (max(0, min(255, int(a))),)
            if p.shape == "shoot":
                d.line((x, y, x + 46, y - 22), fill=c, width=2)
                continue
            SHAPES[p.shape](d, x, y, p.size, c, ph=p.ph + t * p.w)
        frame = Image.alpha_composite(frame, ov)

        # карта: выпрыгивает с отскоком
        p_in = max(0.0, min(1.0, (t - 0.12) / 0.55))
        if p_in > 0:
            sc = max(0.05, ease_out_back(p_in))
            ang = (1 - p_in) * -14
            bob = math.sin(t * 3.2) * 4 if p_in >= 1 else 0
            cur_sprite = sprite.resize((max(2, int(sw * sc)), max(2, int(sh * sc))), Image.BILINEAR)
            cur_glow = card_glow.resize((max(2, int(card_glow.size[0] * sc)), max(2, int(card_glow.size[1] * sc))), Image.BILINEAR)
            if abs(ang) > 0.5:
                cur_sprite = cur_sprite.rotate(ang, resample=Image.BILINEAR, expand=True)
            gk = min(1.0, p_in * 1.5) * (0.8 + 0.2 * math.sin(t * 5))
            cur_glow = scale_alpha(cur_glow, gk)
            cur_sprite = scale_alpha(cur_sprite, min(1.0, p_in * 2.5))
            gx, gy = CARD_CX - cur_glow.size[0] // 2, int(CARD_CY + bob) - cur_glow.size[1] // 2
            frame.paste(cur_glow, (gx, gy), cur_glow)
            cx, cy = CARD_CX - cur_sprite.size[0] // 2, int(CARD_CY + bob) - cur_sprite.size[1] // 2
            frame.paste(cur_sprite, (cx, cy), cur_sprite)

        # вспышка и ударная волна в момент приземления
        tf = t - 0.55
        if 0 <= tf < 0.5:
            fo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            fd = ImageDraw.Draw(fo, "RGBA")
            r = tf * 900
            fd.ellipse((CARD_CX - r, CARD_CY - r, CARD_CX + r, CARD_CY + r),
                       outline=accent + (int(220 * (1 - tf / .5)),), width=6)
            flash = Image.new("RGBA", (W, H), tuple(min(255, c + 90) for c in accent) + (int(90 * (1 - tf / .5) ** 2),))
            frame = Image.alpha_composite(frame, Image.alpha_composite(fo, flash) if tf < .25 else fo)

        # название и редкость
        tn = (t - 0.8) / 0.35
        if tn > 0:
            tn = min(1.0, tn)
            to = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            td = ImageDraw.Draw(to, "RGBA")
            ny = int(H * 0.80 + (1 - tn) * 24)
            nw = td.textlength(name, font=name_font)
            nx = int((W - nw) / 2)
            td.text((nx + 2, ny + 2), name, font=name_font, fill=(0, 0, 0, int(200 * tn)))
            td.text((nx, ny), name, font=name_font, fill=(255, 255, 255, int(255 * tn)))
            ly = int(H * 0.89 + (1 - tn) * 24)
            px0, px1 = (W - label_w) / 2 - 18, (W + label_w) / 2 + 18
            td.rounded_rectangle((px0, ly - 4, px1, ly + 34), radius=18,
                                 fill=(0, 0, 0, int(140 * tn)), outline=accent + (int(255 * tn),), width=2)
            td.text(((W - label_w) / 2, ly), label, font=label_font, fill=accent + (int(255 * tn),))
            frame = Image.alpha_composite(frame, to)

        yield frame.convert("RGB")


def render_card_video(card_path, out_path, name, rarity_label, font_path=None):
    """Собирает mp4 (без звука). Сигнатура совместима с bot.py."""
    exe = _ffmpeg_exe()
    tmp_out = out_path + ".part.mp4"
    cmd = [exe, "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "27",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", tmp_out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for fr in render_frames(card_path, name, rarity_label, font_path):
            proc.stdin.write(fr.tobytes())
        proc.stdin.close()
        if proc.wait() != 0:
            raise RuntimeError("ffmpeg завершился с ошибкой")
        os.replace(tmp_out, out_path)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
        if os.path.exists(tmp_out):
            os.remove(tmp_out)
        raise
