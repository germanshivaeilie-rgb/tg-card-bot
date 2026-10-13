# -*- coding: utf-8 -*-
"""
🎬 game_video.py — видео-анимации для мини-игр (как в Color Dice).

Все render_*() работают одинаково: рисуют кадры в PIL и кодируют mp4 через ffmpeg.
Последние два аргумента всегда (path, font_path).

Нужен ffmpeg: либо пакет imageio-ffmpeg (pip install imageio-ffmpeg),
либо ffmpeg в системе (на Railway: добавь в nixpacks/apt пакет ffmpeg).
"""
import math
import os
import random
import shutil
import subprocess
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

GAME_W, GAME_H = 480, 480
FPS = 24

COIN_SECONDS = 3.0
WHEEL_SECONDS = 4.5
ROULETTE_SECONDS = 5.0
STRIP_SECONDS = 4.5
MINER_SECONDS = 2.2
VERSUS_SECONDS = 3.6
DEAL_STEP = 0.4
DEAL_FLIP = 0.5
DEAL_TAIL = 1.3

RED_NUMBERS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
WHEEL_ORDER = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24,
               16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]


def deal_seconds(n_cards):
    return n_cards * DEAL_STEP + DEAL_FLIP + DEAL_TAIL


# ───────────────────────── утилиты ─────────────────────────
@lru_cache(maxsize=64)
def _font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        try:
            return ImageFont.load_default(size)
        except TypeError:
            return ImageFont.load_default()


@lru_cache(maxsize=16)
def _bg_cached(top, bot):
    g = Image.linear_gradient("L").resize((GAME_W, GAME_H))
    return Image.composite(Image.new("RGB", (GAME_W, GAME_H), bot),
                           Image.new("RGB", (GAME_W, GAME_H), top), g)


def _bg(top=(18, 20, 40), bot=(46, 22, 78)):
    return _bg_cached(tuple(top), tuple(bot)).copy()


def _ease_out(t, p=3.0):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** p


def _clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def _ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return shutil.which("ffmpeg") or "ffmpeg"


def _encode(frame_fn, n_frames, path):
    """frame_fn(t, i) -> PIL.Image размера GAME_W x GAME_H"""
    tmp = path + ".part.mp4"
    cmd = [_ffmpeg(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{GAME_W}x{GAME_H}", "-r", str(FPS), "-i", "-", "-an",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "27",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", tmp]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        last = max(1, n_frames - 1)
        for i in range(n_frames):
            img = frame_fn(i / last, i).convert("RGB")
            if img.size != (GAME_W, GAME_H):
                img = img.resize((GAME_W, GAME_H))
            p.stdin.write(img.tobytes())
        p.stdin.close()
        err = p.stderr.read().decode("utf-8", "ignore")
        p.wait()
    except Exception:
        p.kill()
        raise
    if p.returncode != 0:
        raise RuntimeError("ffmpeg: " + err[-300:])
    os.replace(tmp, path)


def _wrap(text, per_line=11, max_lines=3):
    words, lines, cur = str(text).split(), [], ""
    for w in words:
        if len(cur) + len(w) + (1 if cur else 0) <= per_line:
            cur = (cur + " " + w).strip()
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines[:max_lines] or [""]


def _suit(d, s, cx, cy, r, fill):
    """0 пики, 1 червы, 2 бубны, 3 трефы"""
    if s == 2:
        d.polygon([(cx, cy - r), (cx + r * .75, cy), (cx, cy + r), (cx - r * .75, cy)], fill=fill)
    elif s == 1:
        d.ellipse((cx - r, cy - r * .9, cx, cy + r * .1), fill=fill)
        d.ellipse((cx, cy - r * .9, cx + r, cy + r * .1), fill=fill)
        d.polygon([(cx - r, cy - r * .3), (cx + r, cy - r * .3), (cx, cy + r)], fill=fill)
    elif s == 0:
        d.ellipse((cx - r, cy - r * .1, cx, cy + r * .9), fill=fill)
        d.ellipse((cx, cy - r * .1, cx + r, cy + r * .9), fill=fill)
        d.polygon([(cx - r, cy + r * .3), (cx + r, cy + r * .3), (cx, cy - r)], fill=fill)
        d.polygon([(cx, cy + r * .3), (cx - r * .3, cy + r), (cx + r * .3, cy + r)], fill=fill)
    else:
        for dx, dy in ((0, -.5), (-.55, .3), (.55, .3)):
            d.ellipse((cx + dx * r - r * .5, cy + dy * r - r * .5,
                       cx + dx * r + r * .5, cy + dy * r + r * .5), fill=fill)
        d.polygon([(cx, cy), (cx - r * .3, cy + r), (cx + r * .3, cy + r)], fill=fill)


# ───────────────────────── 🪙 МОНЕТА ─────────────────────────
def render_coin_video(result, path, font_path):
    """result: 'heads' (Орёл) или 'tails' (Монета)"""
    n = int(COIN_SECONDS * FPS)
    halves = 8 + (0 if result == "heads" else 1)
    faces = {}

    def face(kind):
        if kind not in faces:
            im = Image.new("RGBA", (240, 240), (0, 0, 0, 0))
            d = ImageDraw.Draw(im)
            d.ellipse((4, 4, 236, 236), fill=(214, 162, 28, 255), outline=(255, 226, 130, 255), width=9)
            d.ellipse((32, 32, 208, 208), outline=(150, 104, 12, 255), width=5)
            txt, sz = ("ОРЁЛ", 54) if kind == "heads" else ("МОНЕТА", 38)
            d.text((120, 120), txt, font=_font(font_path, sz), fill=(110, 72, 4, 255), anchor="mm")
            faces[kind] = im
        return faces[kind]

    label = "ОРЁЛ" if result == "heads" else "МОНЕТА"

    def frame(t, i):
        im = _bg((20, 24, 48), (60, 30, 90))
        d = ImageDraw.Draw(im)
        ang = halves * math.pi * _ease_out(t, 3)
        k = int(ang / math.pi + 1e-6)
        kind = "heads" if k % 2 == 0 else "tails"
        sy = max(0.04, abs(math.cos(ang)))
        yc = 300 - 170 * math.sin(math.pi * t)
        sw = 200 - 70 * math.sin(math.pi * t)
        d.ellipse((240 - sw / 2, 395, 240 + sw / 2, 420), fill=(8, 8, 18))
        c = face(kind).resize((240, max(4, int(240 * sy))))
        im.paste(c, (120, int(yc - c.height / 2)), c)
        if t > 0.85:
            d.text((240, 450), label, font=_font(font_path, 46), fill=(255, 226, 130), anchor="mm")
        return im

    _encode(frame, n, path)


# ───────────────────────── 🎡 КОЛЕСО ─────────────────────────
def render_wheel_video(segments, idx, path, font_path):
    """segments: [(название, (r,g,b)), ...]; idx — индекс выпавшего сегмента"""
    n = int(WHEEL_SECONDS * FPS)
    cnt = len(segments)
    seg = 360.0 / cnt
    total = 360 * 5 - (idx + 0.5) * seg
    cx, cy, R = 240, 255, 185
    lab = _font(font_path, 20)

    def frame(t, i):
        im = _bg((14, 16, 34), (34, 16, 60))
        d = ImageDraw.Draw(im)
        rot = total * _ease_out(t, 4)
        for k, (name, col) in enumerate(segments):
            a0 = -90 + k * seg + rot
            d.pieslice((cx - R, cy - R, cx + R, cy + R), a0, a0 + seg, fill=tuple(col),
                       outline=(255, 255, 255), width=3)
        for k, (name, col) in enumerate(segments):
            am = math.radians(-90 + (k + .5) * seg + rot)
            d.text((cx + R * .66 * math.cos(am), cy + R * .66 * math.sin(am)), name[:9],
                   font=lab, fill=(255, 255, 255), anchor="mm", stroke_width=2, stroke_fill=(0, 0, 0))
        d.ellipse((cx - 26, cy - 26, cx + 26, cy + 26), fill=(30, 30, 40), outline=(255, 255, 255), width=3)
        d.polygon([(cx - 18, 22), (cx + 18, 22), (cx, 66)], fill=(255, 215, 0), outline=(0, 0, 0))
        if t > 0.88:
            d.text((cx, 458), segments[idx][0], font=_font(font_path, 38), fill=(255, 226, 130), anchor="mm")
        return im

    _encode(frame, n, path)


# ───────────────────────── 🎰 РУЛЕТКА ─────────────────────────
def render_roulette_video(number, path, font_path):
    n = int(ROULETTE_SECONDS * FPS)
    seg = 360.0 / 37
    pos = WHEEL_ORDER.index(number)
    cx, cy = 240, 245
    num_f = _font(font_path, 15)

    def col(num):
        return (20, 150, 60) if num == 0 else ((200, 30, 40) if num in RED_NUMBERS else (30, 30, 36))

    def frame(t, i):
        im = _bg((12, 30, 22), (8, 16, 14))
        d = ImageDraw.Draw(im)
        wrot = 360 * 2 * _ease_out(t, 3)
        d.ellipse((cx - 190, cy - 190, cx + 190, cy + 190), fill=(70, 45, 20), outline=(200, 160, 60), width=5)
        for k, num in enumerate(WHEEL_ORDER):
            a0 = -90 + k * seg + wrot
            d.pieslice((cx - 165, cy - 165, cx + 165, cy + 165), a0, a0 + seg, fill=col(num),
                       outline=(220, 220, 220), width=1)
        d.ellipse((cx - 105, cy - 105, cx + 105, cy + 105), fill=(40, 28, 14), outline=(200, 160, 60), width=3)
        for k, num in enumerate(WHEEL_ORDER):
            am = math.radians(-90 + (k + .5) * seg + wrot)
            d.text((cx + 135 * math.cos(am), cy + 135 * math.sin(am)), str(num), font=num_f,
                   fill=(255, 255, 255), anchor="mm")
        ball_wheel = (pos + .5) * seg - (1 - _ease_out(t, 2.5)) * 360 * 5
        ang = math.radians(wrot + ball_wheel - 90)
        r = 178 - 40 * _clamp((t - .55) / .4) ** 1.5
        bx, by = cx + r * math.cos(ang), cy + r * math.sin(ang)
        d.ellipse((bx - 9, by - 9, bx + 9, by + 9), fill=(255, 255, 255), outline=(160, 160, 160))
        if t > .9:
            c = col(number)
            d.ellipse((240 - 36, 438 - 36, 240 + 36, 438 + 36), fill=c, outline=(255, 255, 255), width=4)
            d.text((240, 438), str(number), font=_font(font_path, 40), fill=(255, 255, 255), anchor="mm")
        return im

    _encode(frame, n, path)


# ───────────────────────── 🎴 ЛЕНТА (крутилка, кейсы) ─────────────────────────
def render_strip_video(items, target, path, font_path, title=""):
    """items: [(подпись, (r,g,b)), ...]; target — индекс выпавшего элемента в items"""
    n = int(STRIP_SECONDS * FPS)
    rnd = random.Random(f"{target}{len(items)}{items[target][0]}")
    N, stop, cell = 44, 36, 170
    seq = [items[rnd.randrange(len(items))] for _ in range(N)]
    seq[stop] = items[target]
    final_off = stop * cell + cell / 2 - GAME_W / 2
    lab = _font(font_path, 24)

    def frame(t, i):
        im = _bg((16, 18, 36), (40, 20, 66))
        d = ImageDraw.Draw(im)
        if title:
            d.text((240, 60), title, font=_font(font_path, 34), fill=(255, 255, 255), anchor="mm")
        off = final_off * _ease_out(t, 4)
        for k, (name, col) in enumerate(seq):
            x = k * cell - off
            if x > GAME_W or x + cell < 0:
                continue
            d.rounded_rectangle((x + 8, 150, x + cell - 8, 350), radius=18, fill=(26, 28, 48),
                                outline=tuple(col), width=6)
            lines = _wrap(name, 10, 3)
            y0 = 250 - (len(lines) - 1) * 15
            for li, ln in enumerate(lines):
                d.text((x + cell / 2, y0 + li * 30), ln, font=lab, fill=(255, 255, 255), anchor="mm")
        d.polygon([(240 - 16, 110), (240 + 16, 110), (240, 148)], fill=(255, 215, 0))
        d.polygon([(240 - 16, 390), (240 + 16, 390), (240, 352)], fill=(255, 215, 0))
        if t > .9:
            d.text((240, 440), items[target][0][:28], font=_font(font_path, 32),
                   fill=(255, 226, 130), anchor="mm")
        return im

    _encode(frame, n, path)


# ───────────────────────── 💣 МИНЁР ─────────────────────────
def render_miner_video(kind, text, path, font_path):
    """kind: 'boom' или 'win'; text — подпись (например '×3 • +900')"""
    n = int(MINER_SECONDS * FPS)
    rnd = random.Random(11)
    sparks = [(rnd.randint(40, 440), rnd.randint(60, 400), rnd.random()) for _ in range(26)]

    def frame(t, i):
        if kind == "boom":
            im = _bg((34, 10, 10), (10, 4, 4))
            d = ImageDraw.Draw(im)
            if t < .35:
                sh = int(9 * math.sin(i * 2.3))
                cx, cy = 240 + sh, 250
                d.ellipse((cx - 72, cy - 56, cx + 72, cy + 84), fill=(30, 30, 36), outline=(100, 100, 110), width=4)
                d.line((cx + 30, cy - 52, cx + 62, cy - 96), fill=(190, 150, 80), width=6)
                if i % 2 == 0:
                    d.ellipse((cx + 56, cy - 112, cx + 76, cy - 92), fill=(255, 200, 40))
            else:
                u = (t - .35) / .65
                cx, cy = 240, 250
                for rad, c in ((400 * u, (255, 70, 20)), (310 * u, (255, 165, 30)), (200 * u, (255, 235, 130))):
                    d.ellipse((cx - rad, cy - rad, cx + rad, cy + rad), fill=c)
                if u > .55:
                    ov = Image.new("RGB", (GAME_W, GAME_H), (10, 4, 4))
                    im = Image.blend(im, ov, _clamp((u - .55) / .45) * .85)
                    d = ImageDraw.Draw(im)
                    d.text((240, 240), "ВЗРЫВ!", font=_font(font_path, 78), fill=(255, 90, 40), anchor="mm")
            return im
        im = _bg((8, 44, 30), (6, 18, 40))
        d = ImageDraw.Draw(im)
        s = _ease_out(t * 1.6, 3)
        r = 110 * s
        cx, cy = 240, 230
        d.polygon([(cx, cy - r), (cx + r * .8, cy - r * .2), (cx, cy + r), (cx - r * .8, cy - r * .2)],
                  fill=(60, 230, 160), outline=(220, 255, 240))
        d.polygon([(cx, cy - r), (cx + r * .3, cy - r * .2), (cx, cy + r), (cx - r * .3, cy - r * .2)],
                  fill=(130, 255, 205))
        for (sx, sy, ph) in sparks:
            a = abs(math.sin((t * 3 + ph) * math.pi))
            rr = 3 + 7 * a
            d.polygon([(sx, sy - rr), (sx + rr * .3, sy), (sx, sy + rr), (sx - rr * .3, sy)], fill=(255, 255, 200))
        if t > .45 and text:
            d.text((240, 410), text, font=_font(font_path, 46), fill=(255, 226, 130), anchor="mm")
        return im

    _encode(frame, n, path)


# ───────────────────────── ⚔️ ДУЭЛЬ / БИТВА / КЛАНЫ ─────────────────────────
def render_versus_video(left, right, winner, path, font_path):
    """left/right: {'name','sub','color'}; winner: 0 — левый, 1 — правый"""
    n = int(VERSUS_SECONDS * FPS)
    imgs = {}

    def card(info, key):
        if key in imgs:
            return imgs[key]
        im = Image.new("RGBA", (190, 250), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        col = tuple(info.get("color", (130, 130, 170)))
        d.rounded_rectangle((0, 0, 189, 249), radius=22, fill=(24, 26, 44, 255), outline=col + (255,), width=7)
        lines = _wrap(info.get("name", "?"), 10, 2)
        for li, ln in enumerate(lines):
            d.text((95, 55 + li * 30), ln, font=_font(font_path, 26), fill=(255, 255, 255, 255), anchor="mm")
        sub = _wrap(info.get("sub", ""), 14, 4)
        for li, ln in enumerate(sub):
            d.text((95, 135 + li * 26), ln, font=_font(font_path, 20), fill=col + (255,), anchor="mm")
        imgs[key] = im
        return im

    def put(im, c, cx, cy, scale=1.0, alpha=1.0):
        c = c.copy()
        if scale != 1.0:
            c = c.resize((max(2, int(c.width * scale)), max(2, int(c.height * scale))))
        if alpha < 1.0:
            c.putalpha(c.getchannel("A").point(lambda v: int(v * alpha)))
        im.paste(c, (int(cx - c.width / 2), int(cy - c.height / 2)), c)

    def frame(t, i):
        im = _bg((24, 14, 40), (60, 16, 30))
        d = ImageDraw.Draw(im)
        cl, cr = card(left, "L"), card(right, "R")
        if t < .3:
            s = _ease_out(t / .3, 3)
            put(im, cl, -100 + 230 * s, 250)
            put(im, cr, 580 - 230 * s, 250)
            d.text((240, 60), "VS", font=_font(font_path, 60), fill=(255, 255, 255), anchor="mm")
        elif t < .5:
            s = (t - .3) / .2
            put(im, cl, 130 + 60 * s, 250)
            put(im, cr, 350 - 60 * s, 250)
            if s > .7:
                im = Image.blend(im, Image.new("RGB", (GAME_W, GAME_H), (255, 255, 255)), (s - .7) / .3 * .8)
        else:
            u = (t - .5) / .5
            wc, lc = (cl, cr) if winner == 0 else (cr, cl)
            wx = 190 if winner == 0 else 290
            lx = 290 if winner == 0 else 190
            put(im, lc, lx + (60 if winner == 0 else -60) * u, 250 + 160 * u, 1 - .4 * u, 1 - u)
            put(im, wc, wx + (240 - wx) * _ease_out(u, 2), 250, 1 + .25 * _ease_out(u, 2))
            d = ImageDraw.Draw(im)
            win_info = left if winner == 0 else right
            if u > .35:
                d.text((240, 70), "ПОБЕДА!", font=_font(font_path, 58), fill=(255, 215, 0), anchor="mm")
                d.text((240, 440), str(win_info.get("name", ""))[:22], font=_font(font_path, 34),
                       fill=(255, 255, 255), anchor="mm")
        return im

    _encode(frame, n, path)


# ───────────────────────── 🃏 РАЗДАЧА (блэкджек / покер) ─────────────────────────
def render_deal_video(player, dealer, labels, result_text, path, font_path):
    """player/dealer: [(ранг_строкой, масть 0-3)], labels: ('Ты','Дилер'), result_text — итог"""
    total_n = len(player) + len(dealer)
    total = deal_seconds(total_n)
    n = int(total * FPS)
    cw = max(46, min(84, int(440 / max(len(player), len(dealer), 1)) - 8))
    ch = int(cw * 1.4)
    schedule = []
    for k in range(max(len(player), len(dealer))):
        if k < len(player):
            schedule.append(("p", k))
        if k < len(dealer):
            schedule.append(("d", k))
    start = {key: j * DEAL_STEP for j, key in enumerate(schedule)}
    cache = {}

    def face(rank, s):
        key = (rank, s)
        if key not in cache:
            im = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
            d = ImageDraw.Draw(im)
            red = s in (1, 2)
            col = (200, 30, 40) if red else (20, 20, 28)
            d.rounded_rectangle((0, 0, cw - 1, ch - 1), radius=9, fill=(250, 250, 245), outline=(120, 120, 130), width=2)
            d.text((cw / 2, ch * .28), str(rank), font=_font(font_path, int(cw * .42)), fill=col, anchor="mm")
            _suit(d, s, cw / 2, ch * .66, cw * .22, col)
            cache[key] = im
        return cache[key]

    back = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    bd = ImageDraw.Draw(back)
    bd.rounded_rectangle((0, 0, cw - 1, ch - 1), radius=9, fill=(40, 70, 170), outline=(220, 220, 240), width=3)
    bd.rounded_rectangle((7, 7, cw - 8, ch - 8), radius=6, outline=(120, 150, 240), width=2)

    def row_x(count, k):
        tw = count * (cw + 8) - 8
        return 240 - tw / 2 + k * (cw + 8) + cw / 2

    def frame(t, i):
        sec = t * total
        im = _bg((10, 40, 28), (6, 22, 18))
        d = ImageDraw.Draw(im)
        d.text((240, 70), labels[1], font=_font(font_path, 26), fill=(220, 240, 230), anchor="mm")
        d.text((240, 255), labels[0], font=_font(font_path, 26), fill=(220, 240, 230), anchor="mm")
        for who, hand, cy in (("d", dealer, 150), ("p", player, 340)):
            for k, (rank, s) in enumerate(hand):
                p = _clamp((sec - start[(who, k)]) / DEAL_FLIP)
                sx = abs(math.cos(math.pi * p))
                img = back if p < .5 else face(rank, s)
                w = max(2, int(cw * sx))
                c = img.resize((w, ch))
                im.paste(c, (int(row_x(len(hand), k) - w / 2), int(cy - ch / 2)), c)
        if sec > total - DEAL_TAIL + .2:
            d.text((240, 440), result_text, font=_font(font_path, 38), fill=(255, 226, 130), anchor="mm")
        return im

    _encode(frame, n, path)
