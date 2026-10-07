"""
Делает короткое видео «выпадения карты» из картинки карты.
Используется ботом (bot.py). Нужны: pillow, numpy, imageio-ffmpeg (или установленный ffmpeg).
"""
import colorsys
import math
import os
import random
import shutil
import subprocess

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

VIDEO_W, VIDEO_H, VIDEO_FPS, VIDEO_SECONDS = 576, 768, 24, 4.2

# Цвет эффекта по редкости (ищется по слову в названии редкости)
RARITY_COLORS = {
    "Обычная": (190, 190, 205),
    "Редкая": (60, 140, 255),
    "Эпическая": (170, 70, 255),
    "Легендарная": (255, 200, 40),
    "Секретная": (40, 220, 90),
    "Бесконечная": "rainbow",
    "Специальная": (0, 220, 230),
    "Тыквенная": (255, 140, 30),
    "Призрачная": (150, 200, 255),
    "Ведьминская": (150, 60, 230),
    "Вампирская": (220, 20, 40),
    "Скелетная": (225, 220, 190),
    "Демоническая": (255, 50, 20),
    "Кошмарная": (200, 30, 110),
}
DEFAULT_COLOR = (255, 140, 30)


def _ffmpeg_path():
    p = shutil.which("ffmpeg")
    if p:
        return p
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def _color_for(rarity_label):
    for key, col in RARITY_COLORS.items():
        if key.lower() in (rarity_label or "").lower():
            return col
    return DEFAULT_COLOR


def _load_font(size, font_path):
    for p in (font_path,
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if p and os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()


def _smooth(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def _ease_out_back(x, s=1.9):
    x = min(max(x, 0.0), 1.0) - 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


def render_card_video(src_path, out_path, title, rarity_label, font_path=None):
    W, H, FPS, DUR = VIDEO_W, VIDEO_H, VIDEO_FPS, VIDEO_SECONDS
    N = int(FPS * DUR)
    CX, CY = W // 2, 352
    CS = 432
    TS = CS + 12
    rnd = random.Random()

    base_col = _color_for(rarity_label)
    rainbow = base_col == "rainbow"

    def color_at(t):
        if rainbow:
            r, g, b = colorsys.hsv_to_rgb((t * 0.25) % 1.0, 0.85, 1.0)
            return np.array([r * 255, g * 255, b * 255], dtype=np.float32)
        return np.array(base_col, dtype=np.float32)

    static_col = np.array((255, 200, 60) if rainbow else base_col, dtype=np.float32)
    edge = tuple(int(v) for v in (static_col * 0.65 + 255 * 0.35))
    dark_edge = tuple(int(v) for v in static_col)

    # --- лицо и рубашка карты
    art = Image.open(src_path)
    art = ImageOps.exif_transpose(art).convert("RGB")
    art = ImageOps.fit(art, (CS, CS), Image.LANCZOS)
    m = Image.new("L", (CS, CS), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, CS - 1, CS - 1), 24, fill=255)
    front = Image.new("RGBA", (TS, TS), (0, 0, 0, 0))
    ImageDraw.Draw(front).rounded_rectangle((0, 0, TS - 1, TS - 1), 30, fill=edge + (255,))
    front.paste(art, (6, 6), m)

    back = Image.new("RGBA", (TS, TS), (0, 0, 0, 0))
    bd = ImageDraw.Draw(back)
    bd.rounded_rectangle((0, 0, TS - 1, TS - 1), 30, fill=dark_edge + (255,))
    bd.rounded_rectangle((8, 8, TS - 9, TS - 9), 25, fill=(24, 10, 6, 255))
    for i in range(5):
        bd.rounded_rectangle((24 + i * 11, 24 + i * 11, TS - 25 - i * 11, TS - 25 - i * 11), 16,
                             outline=tuple(int(v * (0.5 + 0.1 * i)) for v in static_col) + (255,), width=2)
    qf = _load_font(240, font_path)
    bb = bd.textbbox((0, 0), "?", font=qf)
    bd.text(((TS - (bb[2] - bb[0])) / 2 - bb[0], (TS - (bb[3] - bb[1])) / 2 - bb[1]), "?",
            font=qf, fill=dark_edge + (255,))

    # --- сетка для фона
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    dx, dy = xx - CX, yy - CY
    ang = np.arctan2(dy, dx)
    dist = np.sqrt(dx * dx + dy * dy)
    vign = np.clip(1 - ((xx - W / 2) ** 2 / (W * 0.9) ** 2 + (yy - H / 2) ** 2 / (H * 0.75) ** 2), 0, 1)
    card_glow = np.exp(-(dist / 265) ** 2)

    def background(t, power, col):
        rays = 0.5 + 0.5 * np.sin(ang * 12 + t * 1.2) * np.sin(ang * 5 - t * 0.7)
        rays = np.clip(rays, 0, 1) ** 2
        fall = np.exp(-dist / (265 + 95 * power))
        glow = np.exp(-(dist / (160 + 120 * power)) ** 2)
        base = np.array([10, 5, 4], dtype=np.float32)
        lum = (rays * fall * 0.75 + glow * 0.9) * power
        return base[None, None, :] * vign[..., None] + lum[..., None] * col[None, None, :]

    # --- частицы
    particles = []

    def burst(n, speed=(3, 13)):
        for _ in range(n):
            a = rnd.uniform(0, 2 * math.pi)
            s = rnd.uniform(*speed)
            particles.append([CX, CY, math.cos(a) * s, math.sin(a) * s - 1, rnd.uniform(0.6, 1.6), rnd.uniform(1.6, 4), 0.0])

    def ambient():
        if rnd.random() < 0.6:
            particles.append([rnd.uniform(50, W - 50), H - rnd.uniform(0, 50), rnd.uniform(-0.5, 0.5),
                              rnd.uniform(-2.6, -1.2), rnd.uniform(1.2, 2.4), rnd.uniform(1.2, 3), 0.0])

    def draw_particles(col):
        layer = Image.new("RGB", (W, H), (0, 0, 0))
        d = ImageDraw.Draw(layer)
        tint = col * 0.7 + 255 * 0.3
        alive = []
        for p in particles:
            p[0] += p[2]; p[1] += p[3]; p[2] *= 0.965; p[3] *= 0.965; p[6] += 1 / FPS
            life = 1 - p[6] / p[4]
            if life <= 0:
                continue
            r = p[5] * (0.5 + life)
            c = tuple(int(min(255, v * life)) for v in tint)
            d.ellipse((p[0] - r, p[1] - r, p[0] + r, p[1] + r), fill=c)
            alive.append(p)
        particles[:] = alive
        return layer.filter(ImageFilter.GaussianBlur(1.0))

    # --- подписи
    clean_rarity = "".join(ch for ch in (rarity_label or "") if ch.isalnum() or ch in " -").strip()
    name_size = 36
    name_font = _load_font(name_size, font_path)
    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    while probe.textlength(title, font=name_font) > W - 50 and name_size > 18:
        name_size -= 2
        name_font = _load_font(name_size, font_path)
    sub_font = _load_font(24, font_path)

    T_CHARGE, T_FLASH, T_FLIP_END = 1.0, 1.12, 1.85

    tmp_out = out_path + ".tmp.mp4"
    ff = subprocess.Popen(
        [_ffmpeg_path(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-crf", "22", "-preset", "veryfast", "-movflags", "+faststart", "-an", tmp_out],
        stdin=subprocess.PIPE)

    burst_done = burst2 = False
    try:
        for i in range(N):
            t = i / FPS
            col = color_at(t)
            if t < T_CHARGE:
                power = 0.25 + 0.55 * _smooth(t / T_CHARGE)
            elif t < T_FLASH:
                power = 1.2
            else:
                power = 1.0 + 0.15 * math.sin(t * 3)
            img = background(t, power, col)
            img += (card_glow * (0.35 if t < T_FLASH else 0.55))[..., None] * col[None, None, :]

            shake = 0.0
            if t < T_FLASH:
                k = _smooth(t / T_CHARGE)
                shake = math.sin(t * 60) * 8 * k
                sc = 0.45 + 0.15 * k + 0.03 * math.sin(t * 25) * k
                card_img, flipw = back, 1.0
            else:
                u = (t - T_FLASH) / (T_FLIP_END - T_FLASH)
                sc = 0.6 + 0.4 * _ease_out_back(u)
                theta = math.pi * _smooth(u)
                flipw = max(abs(math.cos(theta)), 0.02)
                card_img = back if theta < math.pi / 2 else front
                if u >= 1:
                    flipw, card_img = 1.0, front
                    sc = 1.0 + 0.012 * math.sin((t - T_FLIP_END) * 2.2)
            bob = 0.0 if t < T_FLIP_END else math.sin((t - T_FLIP_END) * 2.0) * 6

            base = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
            cw, ch = max(2, int(TS * sc * flipw)), max(2, int(TS * sc))
            ci = card_img.resize((cw, ch), Image.BILINEAR)
            if card_img is front and flipw < 0.999:
                sh = int(255 * (0.55 + 0.45 * flipw))
                ci = ImageChops.multiply(ci, Image.new("RGBA", ci.size, (sh, sh, sh, 255)))
            px, py = int(CX - cw / 2 + shake), int(CY - ch / 2 + bob)
            base.paste(ci, (px, py), ci)

            if T_FLIP_END + 0.15 < t < T_FLIP_END + 0.9:
                s = (t - T_FLIP_END - 0.15) / 0.75
                band = Image.new("L", (cw, ch), 0)
                x0 = int(-0.4 * cw + s * 1.8 * cw)
                ImageDraw.Draw(band).polygon([(x0, 0), (x0 + 72, 0), (x0 + 72 - 112, ch), (x0 - 112, ch)], fill=150)
                band = band.filter(ImageFilter.GaussianBlur(11))
                mk = ImageChops.multiply(band, ci.split()[3])
                base.paste(Image.new("RGB", (cw, ch), (255, 235, 210)), (px, py), mk)

            if t >= T_FLASH and not burst_done:
                burst(150); burst_done = True
            if t >= T_FLIP_END and not burst2:
                burst(70, (2, 8)); burst2 = True
            if t > T_FLIP_END:
                ambient()
            elif t < T_FLASH and rnd.random() < 0.5 * _smooth(t / T_CHARGE):
                particles.append([CX + rnd.uniform(-160, 160), CY + rnd.uniform(-160, 160), 0, 0, 0.5, 2.5, 0.0])
            base = ImageChops.add(base, draw_particles(col))

            if t > T_FLIP_END + 0.2:
                a = _smooth((t - T_FLIP_END - 0.2) / 0.5)
                tl = Image.new("RGBA", (W, 130), (0, 0, 0, 0))
                td = ImageDraw.Draw(tl)
                name_col = tuple(int(v) for v in (static_col * 0.4 + 255 * 0.6))
                for txt, f_, y, c_ in ((title, name_font, 6, name_col), (clean_rarity, sub_font, 62, dark_edge)):
                    if not txt:
                        continue
                    w_ = td.textlength(txt, font=f_)
                    td.text(((W - w_) / 2, y), txt, font=f_, fill=c_ + (int(255 * a),))
                base.paste(tl, (0, 620 + int((1 - a) * 16)), tl)

            arr = np.asarray(base).astype(np.float32)
            if T_CHARGE <= t < T_FLASH + 0.3:
                fl = _smooth((t - T_CHARGE) / (T_FLASH - T_CHARGE)) if t < T_FLASH else 1 - _smooth((t - T_FLASH) / 0.3)
                arr = arr + (255 - arr) * fl
            if t < 0.2:
                arr = arr * _smooth(t / 0.2)
            ff.stdin.write(np.clip(arr, 0, 255).astype(np.uint8).tobytes())
        ff.stdin.close()
        ff.wait()
        if ff.returncode != 0:
            raise RuntimeError("ffmpeg завершился с ошибкой")
        os.replace(tmp_out, out_path)
    except Exception:
        try:
            ff.kill()
        except Exception:
            pass
        if os.path.exists(tmp_out):
            os.remove(tmp_out)
        raise
    return out_path
