import asyncio
import hashlib
import io
import os
import random
import sqlite3
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile, InputMediaPhoto
from aiogram.filters import Command
from PIL import Image, ImageDraw, ImageFont

# Видео выпадения карт (файл card_video.py должен лежать рядом с bot.py)
try:
    from card_video import render_card_video, VIDEO_W, VIDEO_H, VIDEO_SECONDS
    USE_REVEAL_VIDEO = True
except Exception as _e:
    print("⚠️ Видео выпадения отключено:", _e)
    USE_REVEAL_VIDEO = False
    VIDEO_W, VIDEO_H, VIDEO_SECONDS = 480, 640, 2.4

BOT_TOKEN = os.getenv("BOT_TOKEN")
COOLDOWN_MINUTES = 15
DEV_ID = 1473258682
TRADE_COOLDOWN_MIN = 5

FONT_PATH = "Roboto-Italic-VariableFont_wdth,wght.ttf"
BG_PATH = "ChatGPT Image 5 окт. 2026 г., 09_26_45.png"

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

RARITY_CHANCES = {
    "⚪ Обычная":      55,
    "🔷 Редкая":       18,
    "🔮 Эпическая":    10,
    "👑 Легендарная":  6,
    "♣️ Секретная":    3,
    "🌌 Бесконечная":  2,
}

cards = [
    {"name": "Засохшая лилия",          "rarity": "⚪ Обычная",     "price": 100,    "file": "Засохшая лилия на чёрном фоне (1).png"},
    {"name": "Шоколадный глаз рубрика", "rarity": "⚪ Обычная",     "price": 150,    "file": "IMG_20261004_163909_865.jpg"},
    {"name": "Поедатель чижика",        "rarity": "🔷 Редкая",      "price": 500,    "file": "IMG_20261004_205356_295.jpg"},
    {"name": "Фонк",                    "rarity": "🔷 Редкая",      "price": 400,    "file": "ChatGPT Image 4 окт. 2026 г., 15_45_06.png"},
    {"name": "Лера",                    "rarity": "🔷 Редкая",      "price": 750,    "file": "IMG_20261005_193418_201.jpg"},
    {"name": "Грустный хлеб",           "rarity": "🔮 Эпическая",   "price": 1000,   "file": "ChatGPT Image 22 сент. 2026 г., 22_04_28.png"},
    {"name": "Ляшки асеки",             "rarity": "🔮 Эпическая",   "price": 800,    "file": "IMG_20261005_143214_562.jpg"},
    {"name": "Зелёная шлюшка",          "rarity": "🔮 Эпическая",   "price": 1500,   "file": "IMG_20261005_152528_718.jpg"},
    {"name": "Тру Адамс",               "rarity": "👑 Легендарная", "price": 5000,   "file": "ChatGPT Image 3 окт. 2026 г., 20_39_20.png"},
    {"name": "Давалка",                 "rarity": "👑 Легендарная", "price": 10000,  "file": "IMG_20261004_211521_420.jpg"},
    {"name": "Moggфон",                 "rarity": "♣️ Секретная",   "price": 50000,  "file": "IMG_20261004_211400_997.jpg"},
    {"name": "Топ 1 Минёр",             "rarity": "💠 Специальная", "price": 50000,  "file": "Picsart_26-10-05_23-53-56-160.jpg"},
    {"name": "Лучший Израель йегуда",   "rarity": "🌌 Бесконечная", "price": 500000, "file": "ChatGPT Image 5 окт. 2026 г., 15_32_46.png"},
    {"name": "Хеллоуинский босс",       "rarity": "💠 Специальная", "price": 100000, "file": "ChatGPT Image 6 окт. 2026 г., 12_19_03.png"},
]

# Хеллоуинские карточки больше нигде не выпадают и не продаются в магазине,
# но остаются в базе, чтобы у игроков они сохранились (просмотр, продажа, трейд).
HW_CARDS = {
    "pumpkin": {
        "🎃 Тыквенная": [
            {"name": "Огненная Лера",   "price": 250,  "file": "ChatGPT Image 6 окт. 2026 г., 11_30_41.png"},
            {"name": "Пожиратель тыкв", "price": 500,  "file": "ChatGPT Image 6 окт. 2026 г., 11_26_06.png"},
            {"name": "Нора с тыквами",  "price": 1000, "file": "ChatGPT Image 6 окт. 2026 г., 11_19_50.png"},
        ],
        "👻 Призрачная": [
            {"name": "Призрачный рубрик", "price": 1500, "file": "ChatGPT Image 6 окт. 2026 г., 11_23_00.png"},
        ],
        "🧙 Ведьминская": [
            {"name": "Ведьминский Еля", "price": 10000, "file": "ChatGPT Image 6 окт. 2026 г., 11_16_21.png"},
        ],
        "🧛 Вампирская": [
            {"name": "Вампирский хлеб", "price": 20000, "file": "ChatGPT Image 6 окт. 2026 г., 10_48_44.png"},
        ],
    },
    "skeleton": {
        "👻 Призрачная": [
            {"name": "Призрачный рубрик", "price": 1500, "file": "ChatGPT Image 6 окт. 2026 г., 11_23_00.png"},
            {"name": "Котакбас",          "price": 3000, "file": "ChatGPT Image 6 окт. 2026 г., 14_07_30.png"},
            {"name": "Призрак заез",      "price": 5000, "file": "ChatGPT Image 6 окт. 2026 г., 14_10_39.png"},
        ],
        "🧙 Ведьминская": [
            {"name": "Ведьминский Еля",   "price": 10000, "file": "ChatGPT Image 6 окт. 2026 г., 11_16_21.png"},
            {"name": "Ведьминская кошка", "price": 15000, "file": "ChatGPT Image 6 окт. 2026 г., 14_03_47.png"},
            {"name": "Ведьма неля",       "price": 17000, "file": "ChatGPT Image 6 окт. 2026 г., 14_23_18.png"},
        ],
        "🧛 Вампирская": [
            {"name": "Вампирский хлеб",                 "price": 20000, "file": "ChatGPT Image 6 окт. 2026 г., 10_48_44.png"},
            {"name": "А хотелось бы ведьминский жезл",  "price": 25000, "file": "ChatGPT Image 6 окт. 2026 г., 14_28_54.png"},
        ],
        "💀 Скелетная": [
            {"name": "Костяной Губка боб",       "price": 30000, "file": "ChatGPT Image 6 окт. 2026 г., 14_36_53.png"},
            {"name": "Костяной Литвин x Спид",   "price": 40000, "file": "ChatGPT Image 6 окт. 2026 г., 14_42_20.png"},
        ],
        "😈 Демоническая": [
            {"name": "Коллекционер душ", "price": 100000, "file": "ChatGPT Image 6 окт. 2026 г., 14_45_53.png"},
        ],
    },
    "ghost": {
        "💀 Скелетная": [
            {"name": "Костяной Губка боб",       "price": 30000, "file": "ChatGPT Image 6 окт. 2026 г., 14_36_53.png"},
            {"name": "Костяной Литвин x Спид",   "price": 40000, "file": "ChatGPT Image 6 окт. 2026 г., 14_42_20.png"},
        ],
        "😈 Демоническая": [
            {"name": "Коллекционер душ", "price": 100000, "file": "ChatGPT Image 6 окт. 2026 г., 14_45_53.png"},
        ],
        "😱 Кошмарная": [
            {"name": "Кошмарный Moggfone", "price": 500000, "file": "ChatGPT Image 6 окт. 2026 г., 15_28_10.png"},
        ],
    },
}

HALLOWEEN_RATE_BACK = 9

UPGRADE_PRICES = {2: 100000, 3: 1000000}
MAX_LEVEL = 3

COLORS = [
    {"emoji": "🔵", "name": "Синий",       "code": "blue"},
    {"emoji": "🔴", "name": "Красный",     "code": "red"},
    {"emoji": "🟡", "name": "Жёлтый",      "code": "yellow"},
    {"emoji": "🟢", "name": "Зелёный",     "code": "green"},
    {"emoji": "🟣", "name": "Фиолетовый",  "code": "purple"},
    {"emoji": "🟠", "name": "Оранжевый",   "code": "orange"},
]

MINER_MULTIPLIERS = {
    1: 1.2, 2: 1.5, 3: 2.0, 4: 3.0,
    5: 5.0, 6: 8.0, 7: 15.0, 8: 30.0, 9: 100.0,
}

color_games = {}
miner_games = {}
coin_games = {}
send_games = {}
trade_games = {}
cards_view_games = {}
sell_games = {}
wheel_games = {}

WHEEL_SEGMENTS = [
    {"emoji": "👻", "name": "Призрак",      "mult": 0,   "weight": 45},
    {"emoji": "🕷", "name": "Паук",         "mult": 0.5, "weight": 22},
    {"emoji": "🦇", "name": "Летучая мышь", "mult": 1.5, "weight": 16},
    {"emoji": "🧛", "name": "Вампир",       "mult": 2,   "weight": 11},
    {"emoji": "🎃", "name": "Тыква-босс",   "mult": 5,   "weight": 5},
    {"emoji": "👑", "name": "Король тыкв",  "mult": 10,  "weight": 1},
]

DAILY_CANDY = 1000

DB_PATH = os.path.join(os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "."), "game.db")
db = sqlite3.connect(DB_PATH)
cur = db.cursor()
cur.execute("""CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    balance INTEGER DEFAULT 0,
    last_card TEXT,
    level INTEGER DEFAULT 1,
    registered_at TEXT,
    hw_balance INTEGER DEFAULT 0,
    last_trade TEXT
)""")
cur.execute("""CREATE TABLE IF NOT EXISTS inventory (
    user_id INTEGER,
    card_name TEXT
)""")
cur.execute("""CREATE TABLE IF NOT EXISTS trades (
    from_id INTEGER,
    to_id INTEGER,
    card_name TEXT
)""")
db.commit()

for _col, _type in (("hw_balance", "INTEGER DEFAULT 0"), ("registered_at", "TEXT"),
                    ("last_trade", "TEXT"), ("last_daily", "TEXT")):
    try:
        cur.execute(f"SELECT {_col} FROM users LIMIT 1")
    except sqlite3.OperationalError:
        cur.execute(f"ALTER TABLE users ADD COLUMN {_col} {_type}")
        db.commit()

today = datetime.now().isoformat()
cur.execute("UPDATE users SET registered_at = ? WHERE registered_at IS NULL", (today,))
db.commit()


# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
def roll_card():
    total = sum(RARITY_CHANCES.values())
    r = random.uniform(0, total)
    upto = 0
    chosen = None
    for rarity, chance in RARITY_CHANCES.items():
        upto += chance
        if r <= upto:
            chosen = rarity
            break
    pool = [c for c in cards if c["rarity"] == chosen]
    if not pool:
        pool = cards
    return random.choice(pool)


def find_hw_card(name):
    for case_type, rarities in HW_CARDS.items():
        for rarity, lst in rarities.items():
            for c in lst:
                if c["name"].lower() == name.lower():
                    return c
    return None


def find_any_card(name):
    for c in cards:
        if c["name"].lower() == name.lower():
            return c
    hw = find_hw_card(name)
    if hw:
        return hw
    return None


def get_all_cards_unique():
    result = []
    for c in cards:
        result.append(c)
    seen = set(c["name"] for c in cards)
    for case_type, rarities in HW_CARDS.items():
        for rarity, lst in rarities.items():
            for c in lst:
                if c["name"] not in seen:
                    result.append(c)
                    seen.add(c["name"])
    return result


def get_user(uid, username=None):
    cur.execute("SELECT balance, last_card, level, registered_at, hw_balance, last_trade FROM users WHERE user_id = ?", (uid,))
    row = cur.fetchone()
    if not row:
        now = datetime.now().isoformat()
        cur.execute("INSERT INTO users (user_id, username, registered_at) VALUES (?, ?, ?)", (uid, username, now))
        db.commit()
        return 0, None, 1, now, 0, None
    if username:
        cur.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, uid))
        db.commit()
    return row[0], row[1], row[2], row[3], row[4], row[5]


def format_date_ru(iso_str):
    if not iso_str:
        return "неизвестно"
    try:
        dt = datetime.fromisoformat(iso_str)
    except Exception:
        return "неизвестно"
    months = ["января", "февраля", "марта", "апреля", "мая", "июня",
              "июля", "августа", "сентября", "октября", "ноября", "декабря"]
    return f"{dt.day} {months[dt.month - 1]} {dt.year} года"


def format_cooldown(seconds_left):
    mins = seconds_left // 60
    secs = seconds_left % 60
    if mins > 0:
        return f"{mins} мин {secs} сек"
    return f"{secs} сек"


async def safe_edit(msg, text, **kwargs):
    """Редактирует сообщение и молча игнорирует ошибки (например «текст не изменился»)."""
    try:
        await msg.edit_text(text, **kwargs)
    except Exception:
        pass


def make_circle_avatar(avatar_img, size, border=8):
    avatar_img = avatar_img.resize((size, size))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    total = size + border * 2
    canvas = Image.new("RGBA", (total, total), (0, 0, 0, 0))
    ImageDraw.Draw(canvas).ellipse((0, 0, total, total), fill=(255, 255, 255, 255))
    canvas.paste(avatar_img, (border, border), mask)
    return canvas, total


async def make_profile_image(user_id, username, balance, place, level, total_cards):
    bg = Image.open(BG_PATH).convert("RGBA")
    w, h = bg.size
    avatar = None
    try:
        photos = await bot.get_user_profile_photos(user_id, limit=1)
        if photos.total_count > 0:
            file_id = photos.photos[0][-1].file_id
            file = await bot.get_file(file_id)
            data = await bot.download_file(file.file_path)
            avatar = Image.open(io.BytesIO(data.read())).convert("RGBA")
    except Exception:
        pass
    size = int(h * 0.5)
    if avatar is None:
        avatar = Image.new("RGBA", (size, size), (60, 60, 80, 255))
    avatar_final, total_size = make_circle_avatar(avatar, size, border=8)
    avatar_x = int(w * 0.10)
    avatar_y = (h - total_size) // 2
    bg.paste(avatar_final, (avatar_x, avatar_y), avatar_final)
    draw = ImageDraw.Draw(bg)
    try:
        font_big = ImageFont.truetype(FONT_PATH, 72)
        font_mid = ImageFont.truetype(FONT_PATH, 50)
    except Exception:
        font_big = font_mid = ImageFont.load_default()
    x = int(w * 0.42)
    y = int(h * 0.18)
    line = int(h * 0.17)
    draw.text((x, y), f"@{username or 'Игрок'}", font=font_big, fill="white")
    draw.text((x, y + line), f"Баланс: {balance}", font=font_mid, fill="#FFD700")
    draw.text((x, y + line * 2), f"Уровень: {level}", font=font_mid, fill="#00E5FF")
    draw.text((x, y + line * 3), f"Карт: {total_cards}", font=font_mid, fill="#CCCCCC")
    draw.text((x, y + line * 4), f"Место: #{place}", font=font_mid, fill="#00FF99")
    output = io.BytesIO()
    bg.save(output, format="PNG")
    output.seek(0)
    return output


# ==================== ВИДЕО ВЫПАДЕНИЯ КАРТЫ ====================
VIDEO_DIR = os.path.join(os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "."), "video_cache")
os.makedirs(VIDEO_DIR, exist_ok=True)
render_sem = asyncio.Semaphore(2)   # одновременно собираем не больше 2 видео
video_file_ids = {}                 # после первой отправки Telegram запоминает видео — дальше оно уходит мгновенно


def _video_path(card_data, rarity_label):
    # v2 — новый дизайн фона; старые кэшированные видео не используются
    key = hashlib.md5(f"{card_data['file']}|{card_data['name']}|{rarity_label}|v2".encode()).hexdigest()
    return os.path.join(VIDEO_DIR, key + ".mp4")


async def send_reveal(message, card_data, rarity_label, caption, reply_markup=None, parse_mode=None):
    """1) Отправляет видео с подписью (без кнопок).
    2) Когда видео доиграло — то же сообщение превращается в картинку карты с кнопками.
    Возвращает True, если видео отправилось. Если нет — False (тогда шлём обычное фото)."""
    if not USE_REVEAL_VIDEO:
        return False
    status = None
    try:
        path = _video_path(card_data, rarity_label)
        if path not in video_file_ids and not os.path.exists(path):
            status = await message.answer("🎁 Открываем...")
            async with render_sem:
                if not os.path.exists(path):
                    await asyncio.to_thread(
                        render_card_video, card_data["file"], path,
                        card_data["name"], rarity_label, FONT_PATH
                    )
        media = video_file_ids.get(path) or FSInputFile(path)
        sent = await message.answer_animation(
            media, caption=caption, parse_mode=parse_mode, width=VIDEO_W, height=VIDEO_H
        )
        if sent.animation:
            video_file_ids[path] = sent.animation.file_id
        elif sent.video:
            video_file_ids[path] = sent.video.file_id
        if status:
            try:
                await status.delete()
            except Exception:
                pass
            status = None
    except Exception as e:
        print("Ошибка видео выпадения:", e)
        if status:
            try:
                await status.delete()
            except Exception:
                pass
        return False

    # ждём, пока видео доиграет, и меняем его на картинку карты
    await asyncio.sleep(VIDEO_SECONDS + 0.4)
    try:
        await sent.edit_media(
            InputMediaPhoto(media=FSInputFile(card_data["file"]), caption=caption, parse_mode=parse_mode),
            reply_markup=reply_markup
        )
    except Exception as e:
        print("Не удалось заменить видео на картинку:", e)
        try:
            await sent.delete()
        except Exception:
            pass
        try:
            await message.answer_photo(FSInputFile(card_data["file"]), caption=caption,
                                       reply_markup=reply_markup, parse_mode=parse_mode)
        except Exception:
            await message.answer(caption, reply_markup=reply_markup, parse_mode=parse_mode)
    return True


async def prerender_videos():
    """При старте бота заранее собирает видео для всех выпадающих карт —
    тогда первое выпадение тоже приходит мгновенно."""
    if not USE_REVEAL_VIDEO:
        return
    for c in cards:
        if c["rarity"] not in RARITY_CHANCES:
            continue
        path = _video_path(c, c["rarity"])
        if os.path.exists(path):
            continue
        try:
            async with render_sem:
                await asyncio.to_thread(render_card_video, c["file"], path, c["name"], c["rarity"], FONT_PATH)
        except Exception as e:
            print("Не удалось заранее собрать видео для", c["name"], "-", e)


# ==================== ОСНОВНЫЕ КОМАНДЫ ====================
@dp.message(Command("start"))
async def start(message: types.Message):
    get_user(message.from_user.id, message.from_user.username)
    await message.answer(
        "🎴 Привет! Я бот-коллекционер карточек.\n\n"
        "/card — выбить карточку\n"
        "/cards — просмотр карточек\n"
        "/casino — 🎰 Casino\n"
        "/daily — 🎁 ежедневная награда\n"
        "/mycards — инвентарь\n"
        "/balance — баланс\n"
        "/sell — продать карточку\n"
        "/sellall — продать всё\n"
        "/send @username сумма — передать монеты\n"
        "/trade @username — трейд картами\n"
        "/upgrade — улучшение\n"
        "/profile — профиль\n"
        "/top — топ-3\n"
        "/cancel — отмена действия"
    )


@dp.message(Command("card"))
async def card(message: types.Message):
    uid = message.from_user.id
    username = message.from_user.username or "Игрок"
    balance, last, level, _, _, _ = get_user(uid, message.from_user.username)
    if last:
        last_dt = datetime.fromisoformat(last)
        elapsed = datetime.now() - last_dt
        if elapsed < timedelta(minutes=COOLDOWN_MINUTES):
            left = timedelta(minutes=COOLDOWN_MINUTES) - elapsed
            await message.answer(f"@{username}, ты уже крутил, открой позже.\n⏳ Ждать ещё: {format_cooldown(int(left.total_seconds()))}")
            return
    cur.execute("UPDATE users SET last_card = ? WHERE user_id = ?", (datetime.now().isoformat(), uid))
    db.commit()

    # Сначала выбиваем все карты и кладём в инвентарь
    drawn = []
    for _ in range(level):
        c = roll_card()
        cur.execute("INSERT INTO inventory (user_id, card_name) VALUES (?, ?)", (uid, c["name"]))
        db.commit()
        cur.execute("SELECT rowid FROM inventory WHERE user_id = ? AND card_name = ? ORDER BY rowid DESC LIMIT 1", (uid, c["name"]))
        inv_id = cur.fetchone()[0]
        drawn.append((c, inv_id))

    async def show_one(c, inv_id):
        caption = f"@{username}, вам выпала:\n🎴 {c['name']}\n{c['rarity']} | 💰 Цена: {c['price']} монет"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"💰 Продать: {c['name']} ({c['price']})", callback_data=f"sell_card_{inv_id}_{c['price']}")],
            [InlineKeyboardButton(text="🎰 Casino", callback_data=f"open_casino_{uid}")],
        ])
        ok = await send_reveal(message, c, c["rarity"], caption, reply_markup=kb)
        if not ok:
            photo = FSInputFile(c["file"])
            await message.answer_photo(photo, caption=caption, reply_markup=kb)

    # Все карты показываем одновременно — не ждём одну за другой
    await asyncio.gather(*(show_one(c, inv_id) for c, inv_id in drawn))


@dp.callback_query(F.data.startswith("sell_card_"))
async def sell_card_callback(call: types.CallbackQuery):
    parts = call.data.split("_")
    inv_id = int(parts[2])
    price = int(parts[3])
    uid = call.from_user.id
    cur.execute("SELECT card_name FROM inventory WHERE rowid = ? AND user_id = ?", (inv_id, uid))
    row = cur.fetchone()
    if not row:
        await call.answer("❌ Уже продана.", show_alert=True)
        return
    cur.execute("DELETE FROM inventory WHERE rowid = ?", (inv_id,))
    hw = find_hw_card(row[0])
    if hw:
        cur.execute("UPDATE users SET hw_balance = hw_balance + ? WHERE user_id = ?", (price, uid))
    else:
        cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (price, uid))
    db.commit()
    await call.message.edit_caption(caption=f"✅ Продано: {row[0]} за {price}", reply_markup=None)
    await call.answer("Готово!")


@dp.message(Command("balance"))
async def balance_cmd(message: types.Message):
    balance, _, _, _, hw, _ = get_user(message.from_user.id, message.from_user.username)
    await message.answer(f"💰 Обычных: {balance}\n🍬 Конфет: {hw}")


@dp.message(Command("daily"))
async def daily_cmd(message: types.Message):
    uid = message.from_user.id
    get_user(uid, message.from_user.username)
    cur.execute("SELECT last_daily FROM users WHERE user_id = ?", (uid,))
    row = cur.fetchone()
    last = row[0] if row else None
    if last:
        elapsed = datetime.now() - datetime.fromisoformat(last)
        if elapsed < timedelta(days=1):
            secs = int((timedelta(days=1) - elapsed).total_seconds())
            hours = secs // 3600
            mins = (secs % 3600) // 60
            await message.answer(f"⏳ Ты уже забрал награду.\nПриходи через: {hours} ч {mins} мин")
            return
    cur.execute(
        "UPDATE users SET hw_balance = hw_balance + ?, last_daily = ? WHERE user_id = ?",
        (DAILY_CANDY, datetime.now().isoformat(), uid)
    )
    db.commit()
    _, _, _, _, hw, _ = get_user(uid)
    await message.answer(f"🎁 Ежедневная награда: +{DAILY_CANDY} 🍬\n🍬 Теперь у тебя: {hw}\n\nСледующая через 24 часа.")


@dp.message(Command("mycards"))
async def mycards(message: types.Message):
    uid = message.from_user.id
    cur.execute("SELECT card_name FROM inventory WHERE user_id = ?", (uid,))
    rows = cur.fetchall()
    if not rows:
        await message.answer("Пусто. Напиши /card")
        return
    counts = {}
    for (name,) in rows:
        counts[name] = counts.get(name, 0) + 1
    text = "🎒 *Инвентарь:*\n\n"
    for name, cnt in counts.items():
        text += f"• {name} × {cnt}\n"
    await message.answer(text, parse_mode="Markdown")


# ==================== DEV КОМАНДЫ ====================
@dp.message(Command("give"))
async def give_card(message: types.Message):
    uid = message.from_user.id
    if uid != DEV_ID:
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Использование: /give НазваниеКарты")
        return
    name = args[1].strip()
    found = find_any_card(name)
    if not found:
        await message.answer(f"❌ Карта «{name}» не найдена.")
        return
    cur.execute("INSERT INTO inventory (user_id, card_name) VALUES (?, ?)", (uid, found["name"]))
    db.commit()
    await message.answer(f"✅ Выдано: {found['name']} ({found['price']})")


@dp.message(Command("giveall"))
async def giveall_cards(message: types.Message):
    uid = message.from_user.id
    if uid != DEV_ID:
        return
    all_cards = get_all_cards_unique()
    for c in all_cards:
        cur.execute("INSERT INTO inventory (user_id, card_name) VALUES (?, ?)", (uid, c["name"]))
    db.commit()
    await message.answer(f"✅ Выдано {len(all_cards)} карт!")


@dp.message(Command("setmoney"))
async def setmoney(message: types.Message):
    uid = message.from_user.id
    if uid != DEV_ID:
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Использование: /setmoney Сумма")
        return
    try:
        amount = int(args[1])
    except ValueError:
        await message.answer("❌ Введи число.")
        return
    get_user(uid, message.from_user.username)
    cur.execute("UPDATE users SET balance = ? WHERE user_id = ?", (amount, uid))
    db.commit()
    await message.answer(f"✅ Баланс установлен: {amount} монет")


@dp.message(Command("setcandy"))
async def setcandy(message: types.Message):
    uid = message.from_user.id
    if uid != DEV_ID:
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Использование: /setcandy Сумма")
        return
    try:
        amount = int(args[1])
    except ValueError:
        await message.answer("❌ Введи число.")
        return
    get_user(uid, message.from_user.username)
    cur.execute("UPDATE users SET hw_balance = ? WHERE user_id = ?", (amount, uid))
    db.commit()
    await message.answer(f"✅ Конфет установлено: {amount}")


# ==================== ПЕРЕДАЧА ДЕНЕГ ====================
@dp.message(Command("send"))
async def send_money(message: types.Message):
    uid = message.from_user.id
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("Использование: /send @username сумма")
        return
    target_username = args[1].lstrip("@")
    try:
        amount = int(args[2])
    except ValueError:
        await message.answer("❌ Сумма должна быть числом.")
        return
    if amount <= 0:
        await message.answer("❌ Сумма должна быть больше 0.")
        return
    cur.execute("SELECT user_id FROM users WHERE username = ?", (target_username,))
    row = cur.fetchone()
    if not row:
        await message.answer("❌ Игрок не найден.")
        return
    tid = row[0]
    if tid == uid:
        await message.answer("❌ Себе нельзя.")
        return
    balance, _, _, _, _, _ = get_user(uid, message.from_user.username)
    if balance < amount:
        await message.answer(f"❌ Не хватает. У тебя {balance}.")
        return
    cur.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, uid))
    cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, tid))
    db.commit()
    await message.answer(f"✅ Отправлено {amount} монет @{target_username}")
    try:
        await bot.send_message(tid, f"💸 @{message.from_user.username} отправил тебе {amount} монет!")
    except Exception:
        pass


# ==================== CASINO ====================
def casino_menu_kb(uid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲 Color Dice", callback_data=f"casino_color_{uid}")],
        [InlineKeyboardButton(text="💣 Минёр", callback_data=f"casino_miner_{uid}")],
        [InlineKeyboardButton(text="🪙 Орёл и Решка", callback_data=f"casino_coin_{uid}")],
        [InlineKeyboardButton(text="👹 Колесо монстров", callback_data=f"casino_wheel_{uid}")],
        [InlineKeyboardButton(text="🔙 Закрыть", callback_data=f"casino_close_{uid}")],
    ])


@dp.message(Command("casino"))
async def casino_command(message: types.Message):
    uid = message.from_user.id
    username = message.from_user.username or message.from_user.full_name or "Игрок"
    await message.answer(f"🎰 *Casino* — @{username}\n\nВыбери игру:", reply_markup=casino_menu_kb(uid), parse_mode="Markdown")


@dp.callback_query(F.data.startswith("open_casino_"))
async def open_casino(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Это не твоё меню!", show_alert=True)
        return
    username = call.from_user.username or call.from_user.full_name or "Игрок"
    await call.message.answer(f"🎰 *Casino* — @{username}\n\nВыбери игру:", reply_markup=casino_menu_kb(uid), parse_mode="Markdown")
    await call.answer()


@dp.callback_query(F.data.startswith("casino_close_"))
async def casino_close(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Не твоё меню!", show_alert=True)
        return
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.answer()


# ---- COLOR DICE ----
@dp.callback_query(F.data.startswith("casino_color_"))
async def casino_color(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Не твоё меню!", show_alert=True)
        return
    username = call.from_user.username or call.from_user.full_name or "Игрок"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔵 Синий", callback_data=f"col_blue_{uid}"), InlineKeyboardButton(text="🔴 Красный", callback_data=f"col_red_{uid}")],
        [InlineKeyboardButton(text="🟡 Жёлтый", callback_data=f"col_yellow_{uid}"), InlineKeyboardButton(text="🟢 Зелёный", callback_data=f"col_green_{uid}")],
        [InlineKeyboardButton(text="🟣 Фиолетовый", callback_data=f"col_purple_{uid}"), InlineKeyboardButton(text="🟠 Оранжевый", callback_data=f"col_orange_{uid}")],
    ])
    await call.message.edit_text(
        f"🎲 *Color Dice* — @{username}\n\nПравила:\n🎉 1 совпадение → ×2\n🎉 4 совпадения → ×4\n❌ 0, 2, 3 → проигрыш\n\nВыбери цвет:",
        reply_markup=kb, parse_mode="Markdown"
    )
    await call.answer()


@dp.callback_query(F.data.startswith("col_"))
async def color_chosen(call: types.CallbackQuery):
    parts = call.data.split("_")
    if len(parts) < 3:
        await call.answer("Ошибка", show_alert=True)
        return
    code = parts[1]
    uid = int(parts[2])
    if call.from_user.id != uid:
        await call.answer("Не твоя игра!", show_alert=True)
        return
    chosen = next((c for c in COLORS if c["code"] == code), None)
    if not chosen:
        await call.answer("Ошибка цвета", show_alert=True)
        return
    color_games[uid] = {"color": chosen, "state": "wait_bet"}
    await call.message.edit_text(
        f"🎲 Твой цвет: {chosen['emoji']} {chosen['name']}\n\n💰 Напиши сумму ставки числом (например 100).\nОтмена — /cancel"
    )
    await call.answer()


# ---- МИНЁР ----
@dp.callback_query(F.data.startswith("casino_miner_"))
async def casino_miner(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Не твоё меню!", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Сделать ставку", callback_data=f"miner_bet_{uid}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"casino_back_{uid}")],
    ])
    await call.message.edit_text(
        "💣 *Минёр*\n\n📋 *Правила:*\n• 9 клеток\n• Спрятано 2-6 мин\n• Открывай клетки\n• Попадёшь — теряешь ставку\n• Открыл все безопасные — выигрыш\n\n"
        "📈 *Множители:*\n1 → ×1.2\n2 → ×1.5\n3 → ×2\n4 → ×3\n5 → ×5\n6 → ×8\n7 → ×15\n8 → ×30\n\n"
        "🎁 Открыл все безопасные при 3+ минах — карточка «Топ 1 Минёр» (💠)!",
        reply_markup=kb, parse_mode="Markdown"
    )
    await call.answer()


@dp.callback_query(F.data.startswith("casino_back_"))
async def casino_back(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Не твоё меню!", show_alert=True)
        return
    username = call.from_user.username or call.from_user.full_name or "Игрок"
    await call.message.edit_text(f"🎰 *Casino* — @{username}\n\nВыбери игру:", reply_markup=casino_menu_kb(uid), parse_mode="Markdown")
    await call.answer()


@dp.callback_query(F.data.startswith("miner_bet_"))
async def miner_bet_request(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Не твоё меню!", show_alert=True)
        return
    miner_games[uid] = {"state": "wait_bet"}
    await call.message.edit_text(
        "💣 *Минёр*\n\n💰 Напиши сумму ставки числом (например 100).\nОтмена — /cancel",
        parse_mode="Markdown"
    )
    await call.answer()


def render_miner_field(opened, mines_set, reveal_all=False):
    row = []
    for i in range(9):
        if i in opened:
            row.append("🟢")
        elif reveal_all and i in mines_set:
            row.append("💣")
        else:
            row.append("🟦")
    return row


def miner_keyboard(opened, mines_set, uid):
    buttons = []
    row1 = []
    for i in range(9):
        if i in opened:
            row1.append(InlineKeyboardButton(text="🟢", callback_data=f"miner_noop_{i}_{uid}"))
        else:
            row1.append(InlineKeyboardButton(text="🟦", callback_data=f"miner_open_{i}_{uid}"))
    buttons.append(row1)
    buttons.append([InlineKeyboardButton(text="💰 Забрать", callback_data=f"miner_cashout_{uid}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@dp.callback_query(F.data.startswith("miner_noop_"))
async def miner_noop(call: types.CallbackQuery):
    parts = call.data.split("_")
    uid = int(parts[3])
    if call.from_user.id != uid:
        await call.answer("Не твоя игра!", show_alert=True)
        return
    await call.answer("Уже открыто.")


@dp.callback_query(F.data.startswith("miner_open_"))
async def miner_open(call: types.CallbackQuery):
    parts = call.data.split("_")
    idx = int(parts[2])
    uid = int(parts[3])
    if call.from_user.id != uid:
        await call.answer("Не твоя игра!", show_alert=True)
        return
    username = call.from_user.username or call.from_user.full_name or "Игрок"
    game = miner_games.get(uid)
    if not game or game.get("state") != "playing":
        await call.answer("Игра не активна.", show_alert=True)
        return
    if idx in game["opened"]:
        await call.answer("Уже открыто.")
        return
    if idx in game["mines"]:
        game["state"] = "finished"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎰 Играть снова", callback_data=f"casino_miner_{uid}")],
            [InlineKeyboardButton(text="🔙 Casino", callback_data=f"open_casino_{uid}")],
        ])
        await call.message.edit_text(
            f"💣 *Минёр* — @{username}\n\n💰 Ставка: {game['bet']}\n💥 Попал на мину!\n\n"
            f"{' '.join(render_miner_field(game['opened'], game['mines'], reveal_all=True))}\n\n"
            f"❌ *Проиграл {game['bet']} монет.*",
            reply_markup=kb, parse_mode="Markdown"
        )
        del miner_games[uid]
        await call.answer("💥 Бум!")
        return
    game["opened"].append(idx)
    count = len(game["opened"])
    multiplier = MINER_MULTIPLIERS.get(count, 30.0)
    potential = int(game["bet"] * multiplier)
    safe_cells_count = 9 - len(game["mines"])
    all_safe_opened = count >= safe_cells_count
    if all_safe_opened:
        game["state"] = "finished"
        win = int(game["bet"] * multiplier)
        cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (win, uid))
        special_card = False
        if len(game["mines"]) >= 3:
            cur.execute("INSERT INTO inventory (user_id, card_name) VALUES (?, ?)", (uid, "Топ 1 Минёр"))
            special_card = True
        db.commit()
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎰 Играть снова", callback_data=f"casino_miner_{uid}")],
            [InlineKeyboardButton(text="🔙 Casino", callback_data=f"open_casino_{uid}")],
        ])
        text = (
            f"💣 *Минёр* — @{username}\n\n💰 Ставка: {game['bet']}\n🎉 Все безопасные открыты!\n📈 Множитель: ×{multiplier}\n\n"
            f"{' '.join(render_miner_field(game['opened'], game['mines'], reveal_all=True))}\n\n💰 *Выигрыш: {win} монет!*"
        )
        if special_card:
            text += "\n\n💠 *ВЫПАЛА КАРТОЧКА «Топ 1 Минёр»!*"
        await call.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        if special_card:
            try:
                cd = next((c for c in cards if c["name"] == "Топ 1 Минёр"), None)
                if cd:
                    photo = FSInputFile(cd["file"])
                    await call.message.answer_photo(photo, caption=f"🎁 *Награда!*\n\n🎴 {cd['name']}\n{cd['rarity']} | 💰 {cd['price']}", parse_mode="Markdown")
            except Exception:
                pass
        del miner_games[uid]
        await call.answer("🎉 Победа!")
        return
    await call.message.edit_text(
        f"💣 *Минёр* — @{username}\n💰 Ставка: {game['bet']}\n🟢 Открыто: {count}\n📈 Множитель: ×{multiplier}\n💵 Заберёшь: {potential}",
        reply_markup=miner_keyboard(game["opened"], game["mines"], uid), parse_mode="Markdown"
    )
    await call.answer(f"Открыто: {count} | ×{multiplier}")


@dp.callback_query(F.data.startswith("miner_cashout_"))
async def miner_cashout(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Не твоя игра!", show_alert=True)
        return
    username = call.from_user.username or call.from_user.full_name or "Игрок"
    game = miner_games.get(uid)
    if not game or game.get("state") != "playing":
        await call.answer("Игра не активна.", show_alert=True)
        return
    count = len(game["opened"])
    if count == 0:
        await call.answer("Открой хотя бы одну клетку!", show_alert=True)
        return
    multiplier = MINER_MULTIPLIERS.get(count, 30.0)
    win = int(game["bet"] * multiplier)
    cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (win, uid))
    db.commit()
    game["state"] = "finished"
    del miner_games[uid]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎰 Играть снова", callback_data=f"casino_miner_{uid}")],
        [InlineKeyboardButton(text="🔙 Casino", callback_data=f"open_casino_{uid}")],
    ])
    await call.message.edit_text(
        f"💣 *Минёр* — @{username}\n\n💰 Ставка: {game['bet']}\n🟢 Открыто: {count}\n📈 Множитель: ×{multiplier}\n\n✅ *Забрал {win} монет!*",
        reply_markup=kb, parse_mode="Markdown"
    )
    await call.answer(f"Получено {win}!")


# ---- ОРЁЛ И РЕШКА ----
@dp.callback_query(F.data.startswith("casino_coin_"))
async def casino_coin(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Не твоё меню!", show_alert=True)
        return
    username = call.from_user.username or call.from_user.full_name or "Игрок"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🦅 Орёл", callback_data=f"coin_heads_{uid}")],
        [InlineKeyboardButton(text="🪙 Монета", callback_data=f"coin_tails_{uid}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"casino_back_{uid}")],
    ])
    await call.message.edit_text(
        f"🪙 *Орёл и Решка* — @{username}\n\n"
        "Правила:\n🦅 Угадал сторону → выигрыш ×2\n❌ Не угадал → проигрыш\n\n"
        "*Выбери сторону:*",
        reply_markup=kb, parse_mode="Markdown"
    )
    await call.answer()


@dp.callback_query(F.data.startswith("coin_heads_"))
async def coin_heads(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Не твоя игра!", show_alert=True)
        return
    coin_games[uid] = {"choice": "heads", "state": "wait_bet"}
    await call.message.edit_text(
        "🪙 Твой выбор: 🦅 Орёл\n\n💰 Напиши сумму ставки числом (например 100).\nОтмена — /cancel"
    )
    await call.answer()


@dp.callback_query(F.data.startswith("coin_tails_"))
async def coin_tails(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Не твоя игра!", show_alert=True)
        return
    coin_games[uid] = {"choice": "tails", "state": "wait_bet"}
    await call.message.edit_text(
        "🪙 Твой выбор: 🪙 Монета\n\n💰 Напиши сумму ставки числом (например 100).\nОтмена — /cancel"
    )
    await call.answer()


# ---- КОЛЕСО МОНСТРОВ ----
@dp.callback_query(F.data.startswith("casino_wheel_"))
async def casino_wheel(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Не твоё меню!", show_alert=True)
        return
    lines = []
    for s in WHEEL_SEGMENTS:
        lines.append(f"{s['emoji']} {s['name']} — ×{s['mult']} ({s['weight']}%)")
    rules = "\n".join(lines)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Сделать ставку", callback_data=f"wheel_bet_{uid}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"casino_back_{uid}")],
    ])
    await call.message.edit_text(
        f"👹 *Колесо монстров*\n\nКрутишь колесо, и тебе выпадает монстр.\n"
        f"Он решает, сколько ты выиграешь.\n\n{rules}\n\nГотов рискнуть?",
        reply_markup=kb, parse_mode="Markdown"
    )
    await call.answer()


@dp.callback_query(F.data.startswith("wheel_bet_"))
async def wheel_bet_request(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Не твоё меню!", show_alert=True)
        return
    wheel_games[uid] = {"state": "wait_bet"}
    await call.message.edit_text(
        "👹 *Колесо монстров*\n\n💰 Напиши сумму ставки числом (например 100).\nОтмена — /cancel",
        parse_mode="Markdown"
    )
    await call.answer()


# ==================== ПРОСМОТР КАРТОЧЕК /cards ====================
@dp.message(Command("cards"))
async def cards_view(message: types.Message):
    uid = message.from_user.id
    cur.execute("SELECT DISTINCT card_name FROM inventory WHERE user_id = ?", (uid,))
    rows = cur.fetchall()
    if not rows:
        await message.answer("Инвентарь пуст.")
        return
    unique = [r[0] for r in rows]
    cards_view_games[uid] = {"all": unique, "page": 0, "filter": None, "shown": []}
    await send_cards_page(message, uid)


async def send_cards_page(message_or_call, uid, edit=False):
    g = cards_view_games.get(uid)
    if not g:
        return
    items = g["all"]
    if g["filter"]:
        items = [n for n in items if g["filter"].lower() in n.lower()]
    g["shown"] = items
    if not items:
        text = "🔍 Ничего не найдено по фильтру."
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Новый поиск", callback_data=f"cards_search_{uid}")],
            [InlineKeyboardButton(text="🔙 Закрыть", callback_data=f"cards_close_{uid}")],
        ])
        try:
            await message_or_call.edit_text(text, reply_markup=kb)
        except Exception:
            await bot.send_message(uid, text, reply_markup=kb)
        return
    page_size = 8
    total_pages = (len(items) + page_size - 1) // page_size
    page = g["page"] % total_pages
    g["page"] = page
    start_i = page * page_size
    chunk = items[start_i:start_i + page_size]
    buttons = []
    for i, name in enumerate(chunk):
        buttons.append([InlineKeyboardButton(text=name, callback_data=f"card_show_{uid}_{start_i + i}")])
    nav = []
    if total_pages > 1:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"cards_prev_{uid}"))
        nav.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="cards_noop"))
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"cards_next_{uid}"))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton(text="🔍 Поиск", callback_data=f"cards_search_{uid}")])
    buttons.append([InlineKeyboardButton(text="🔙 Закрыть", callback_data=f"cards_close_{uid}")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    text = f"🎴 *Твои карточки* ({len(items)})"
    if g["filter"]:
        text += f"\n🔍 Фильтр: «{g['filter']}»"
    if edit:
        try:
            await message_or_call.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass
    else:
        await message_or_call.answer(text, reply_markup=kb, parse_mode="Markdown")


@dp.callback_query(F.data.startswith("cards_next_"))
async def cards_next(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Не твоё!", show_alert=True)
        return
    g = cards_view_games.get(uid)
    if g:
        g["page"] += 1
    await send_cards_page(call.message, uid, edit=True)
    await call.answer()


@dp.callback_query(F.data.startswith("cards_prev_"))
async def cards_prev(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Не твоё!", show_alert=True)
        return
    g = cards_view_games.get(uid)
    if g:
        g["page"] -= 1
    await send_cards_page(call.message, uid, edit=True)
    await call.answer()


@dp.callback_query(F.data == "cards_noop")
async def cards_noop(call: types.CallbackQuery):
    await call.answer()


@dp.callback_query(F.data.startswith("cards_close_"))
async def cards_close(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Не твоё!", show_alert=True)
        return
    cards_view_games.pop(uid, None)
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.answer()


@dp.callback_query(F.data.startswith("cards_search_"))
async def cards_search(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Не твоё!", show_alert=True)
        return
    g = cards_view_games.get(uid)
    if not g:
        await call.answer("Открой /cards заново.", show_alert=True)
        return
    g["state"] = "wait_search"
    await call.message.edit_text("🔍 Напиши часть названия карты для поиска.\nОтмена — /cancel")
    await call.answer()


@dp.callback_query(F.data.startswith("card_show_"))
async def card_show(call: types.CallbackQuery):
    parts = call.data.split("_")
    uid = int(parts[2])
    idx = int(parts[3])
    if call.from_user.id != uid:
        await call.answer("Не твоё!", show_alert=True)
        return
    g = cards_view_games.get(uid)
    if not g or idx >= len(g.get("shown", [])):
        await call.answer("Открой /cards заново.", show_alert=True)
        return
    full_name = g["shown"][idx]
    card_data = find_any_card(full_name)
    if not card_data:
        await call.answer("Данные карты не найдены.", show_alert=True)
        return
    cur.execute("SELECT COUNT(*) FROM inventory WHERE user_id = ? AND card_name = ?", (uid, full_name))
    cnt = cur.fetchone()[0]
    caption = f"🎴 *{card_data['name']}*\nРедкость: {card_data.get('rarity', '🎃 Хеллоуинская')}\n💰 Цена: {card_data['price']}\n📦 У тебя: {cnt} шт."
    try:
        photo = FSInputFile(card_data["file"])
        await call.message.answer_photo(photo, caption=caption, parse_mode="Markdown")
    except Exception:
        await call.message.answer(caption, parse_mode="Markdown")
    await call.answer()


# ==================== ТРЕЙД ====================
@dp.message(Command("trade"))
async def trade_start(message: types.Message):
    uid = message.from_user.id
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Использование: /trade @username")
        return
    target_username = args[1].lstrip("@").strip()
    cur.execute("SELECT user_id, username, last_trade FROM users WHERE username = ?", (target_username,))
    row = cur.fetchone()
    if not row:
        await message.answer("❌ Игрок не найден.")
        return
    tid, tun, last_trade = row
    if tid == uid:
        await message.answer("❌ Себе нельзя.")
        return
    if last_trade:
        last_dt = datetime.fromisoformat(last_trade)
        elapsed = datetime.now() - last_dt
        if elapsed < timedelta(minutes=TRADE_COOLDOWN_MIN):
            left = timedelta(minutes=TRADE_COOLDOWN_MIN) - elapsed
            await message.answer(f"⏳ Подожди {format_cooldown(int(left.total_seconds()))} перед новым трейдом.")
            return
    cur.execute("SELECT DISTINCT card_name FROM inventory WHERE user_id = ?", (uid,))
    my_cards = [r[0] for r in cur.fetchall()]
    if not my_cards:
        await message.answer("❌ У тебя нет карточек для трейда.")
        return
    trade_games[uid] = {
        "partner_id": tid,
        "partner_username": tun,
        "my_cards": my_cards,
        "page": 0,
        "stage": "choose_my",
        "my_card": None,
    }
    await send_trade_my_page(message, uid)


async def send_trade_my_page(message_or_call, uid, edit=False):
    g = trade_games.get(uid)
    if not g:
        return
    items = g["my_cards"]
    page_size = 8
    total_pages = (len(items) + page_size - 1) // page_size
    page = g["page"] % total_pages
    g["page"] = page
    start_i = page * page_size
    chunk = items[start_i:start_i + page_size]
    buttons = []
    for i, name in enumerate(chunk):
        buttons.append([InlineKeyboardButton(text=name, callback_data=f"tr_my_{uid}_{start_i + i}")])
    nav = []
    if total_pages > 1:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"tr_myp_{uid}"))
        nav.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="cards_noop"))
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"tr_myn_{uid}"))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton(text="🔍 Поиск", callback_data=f"tr_mys_{uid}")])
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data=f"tr_cancel_{uid}")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    text = f"🤝 *Трейд с @{g['partner_username']}*\n\n📤 Выбери СВОЮ карту для обмена ({len(items)}):"
    if edit:
        try:
            await message_or_call.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass
    else:
        await message_or_call.answer(text, reply_markup=kb, parse_mode="Markdown")


@dp.callback_query(F.data.startswith("tr_myn_"))
async def tr_myn(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Не твоё!", show_alert=True)
        return
    g = trade_games.get(uid)
    if g:
        g["page"] += 1
    await send_trade_my_page(call.message, uid, edit=True)
    await call.answer()


@dp.callback_query(F.data.startswith("tr_myp_"))
async def tr_myp(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Не твоё!", show_alert=True)
        return
    g = trade_games.get(uid)
    if g:
        g["page"] -= 1
    await send_trade_my_page(call.message, uid, edit=True)
    await call.answer()


@dp.callback_query(F.data.startswith("tr_cancel_"))
async def tr_cancel(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Не твоё!", show_alert=True)
        return
    trade_games.pop(uid, None)
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.answer("Отменено")


@dp.callback_query(F.data.startswith("tr_mys_"))
async def tr_mys(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Не твоё!", show_alert=True)
        return
    g = trade_games.get(uid)
    if not g:
        await call.answer("Начни трейд заново.", show_alert=True)
        return
    g["state"] = "wait_search_my"
    await call.message.edit_text("🔍 Напиши часть названия ТВОЕЙ карты.\nОтмена — /cancel")
    await call.answer()


@dp.callback_query(F.data.startswith("tr_my_"))
async def tr_my_choose(call: types.CallbackQuery):
    parts = call.data.split("_")
    uid = int(parts[2])
    idx = int(parts[3])
    if call.from_user.id != uid:
        await call.answer("Не твоё!", show_alert=True)
        return
    g = trade_games.get(uid)
    if not g or idx >= len(g["my_cards"]):
        await call.answer("Начни трейд заново.", show_alert=True)
        return
    full_name = g["my_cards"][idx]
    g["my_card"] = full_name
    g["stage"] = "choose_his"
    tid = g["partner_id"]
    cur.execute("SELECT DISTINCT card_name FROM inventory WHERE user_id = ?", (tid,))
    his_cards = [r[0] for r in cur.fetchall()]
    if not his_cards:
        await call.answer("У партнёра нет карточек!", show_alert=True)
        trade_games.pop(uid, None)
        return
    g["his_cards"] = his_cards
    g["page"] = 0
    await send_trade_his_page(call.message, uid, edit=True)
    await call.answer()


async def send_trade_his_page(message_or_call, uid, edit=False):
    g = trade_games.get(uid)
    if not g:
        return
    items = g["his_cards"]
    page_size = 8
    total_pages = (len(items) + page_size - 1) // page_size
    page = g["page"] % total_pages
    g["page"] = page
    start_i = page * page_size
    chunk = items[start_i:start_i + page_size]
    buttons = []
    for i, name in enumerate(chunk):
        buttons.append([InlineKeyboardButton(text=name, callback_data=f"tr_his_{uid}_{start_i + i}")])
    nav = []
    if total_pages > 1:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"tr_hisp_{uid}"))
        nav.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="cards_noop"))
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"tr_hisn_{uid}"))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"tr_back_{uid}")])
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data=f"tr_cancel_{uid}")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    text = (
        f"🤝 *Трейд с @{g['partner_username']}*\n\n"
        f"📤 Ты отдаёшь: *{g['my_card']}*\n"
        f"📥 Выбери ЕГО карту ({len(items)}):"
    )
    if edit:
        try:
            await message_or_call.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass
    else:
        await message_or_call.answer(text, reply_markup=kb, parse_mode="Markdown")


@dp.callback_query(F.data.startswith("tr_hisn_"))
async def tr_hisn(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Не твоё!", show_alert=True)
        return
    g = trade_games.get(uid)
    if g:
        g["page"] += 1
    await send_trade_his_page(call.message, uid, edit=True)
    await call.answer()


@dp.callback_query(F.data.startswith("tr_hisp_"))
async def tr_hisp(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Не твоё!", show_alert=True)
        return
    g = trade_games.get(uid)
    if g:
        g["page"] -= 1
    await send_trade_his_page(call.message, uid, edit=True)
    await call.answer()


@dp.callback_query(F.data.startswith("tr_back_"))
async def tr_back(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Не твоё!", show_alert=True)
        return
    g = trade_games.get(uid)
    if g:
        g["stage"] = "choose_my"
        g["page"] = 0
    await send_trade_my_page(call.message, uid, edit=True)
    await call.answer()


@dp.callback_query(F.data.startswith("tr_his_"))
async def tr_his_choose(call: types.CallbackQuery):
    parts = call.data.split("_")
    uid = int(parts[2])
    idx = int(parts[3])
    if call.from_user.id != uid:
        await call.answer("Не твоё!", show_alert=True)
        return
    g = trade_games.get(uid)
    if not g or idx >= len(g.get("his_cards", [])):
        await call.answer("Начни трейд заново.", show_alert=True)
        return
    full_name = g["his_cards"][idx]
    g["his_card"] = full_name
    tid = g["partner_id"]
    my_card = g["my_card"]
    my_username = call.from_user.username or call.from_user.full_name
    trade_id = str(uid) + "_" + str(tid)
    trade_games[trade_id] = {
        "from_id": uid,
        "from_username": my_username,
        "to_id": tid,
        "my_card": my_card,
        "his_card": full_name,
    }
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принять", callback_data=f"tr_acc_{trade_id}")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"tr_dec_{trade_id}")],
    ])
    try:
        await bot.send_message(
            tid,
            f"🤝 *Тебе предложили трейд!*\n\n"
            f"👤 От: @{my_username}\n\n"
            f"📤 Ты отдаёшь: *{full_name}*\n"
            f"📥 Ты получаешь: *{my_card}*\n\n"
            f"Подтвердить?",
            reply_markup=kb, parse_mode="Markdown"
        )
    except Exception:
        await call.answer("Не удалось отправить — партнёр должен написать боту в ЛС /start", show_alert=True)
        trade_games.pop(trade_id, None)
        return
    try:
        await call.message.edit_text(f"✅ Запрос отправлен @{g['partner_username']}!\n\nЖдём ответа...")
    except Exception:
        pass
    trade_games.pop(uid, None)
    await call.answer("Отправлено!")


@dp.callback_query(F.data.startswith("tr_acc_"))
async def tr_acc(call: types.CallbackQuery):
    data = call.data.replace("tr_acc_", "")
    g = trade_games.get(data)
    if not g:
        await call.answer("Трейд уже обработан.", show_alert=True)
        return
    if call.from_user.id != g["to_id"]:
        await call.answer("Это не твой трейд!", show_alert=True)
        return
    fid = g["from_id"]
    tid = g["to_id"]
    my_card = g["my_card"]
    his_card = g["his_card"]
    cur.execute("SELECT rowid FROM inventory WHERE user_id = ? AND card_name = ? LIMIT 1", (fid, my_card))
    r1 = cur.fetchone()
    cur.execute("SELECT rowid FROM inventory WHERE user_id = ? AND card_name = ? LIMIT 1", (tid, his_card))
    r2 = cur.fetchone()
    if not r1 or not r2:
        await call.message.edit_text("❌ Одна из карточек пропала. Трейд отменён.")
        trade_games.pop(data, None)
        await call.answer()
        return
    cur.execute("DELETE FROM inventory WHERE rowid = ?", (r1[0],))
    cur.execute("DELETE FROM inventory WHERE rowid = ?", (r2[0],))
    cur.execute("INSERT INTO inventory (user_id, card_name) VALUES (?, ?)", (tid, my_card))
    cur.execute("INSERT INTO inventory (user_id, card_name) VALUES (?, ?)", (fid, his_card))
    now = datetime.now().isoformat()
    cur.execute("UPDATE users SET last_trade = ? WHERE user_id = ?", (now, fid))
    cur.execute("UPDATE users SET last_trade = ? WHERE user_id = ?", (now, tid))
    db.commit()
    await call.message.edit_text(f"✅ *Трейд завершён!*\n\n📤 Ты отдал: {his_card}\n📥 Ты получил: {my_card}", parse_mode="Markdown")
    try:
        await bot.send_message(fid, f"✅ *Твой трейд принят!*\n\n📤 Ты отдал: {my_card}\n📥 Ты получил: {his_card}", parse_mode="Markdown")
    except Exception:
        pass
    trade_games.pop(data, None)
    await call.answer("Принято!")


@dp.callback_query(F.data.startswith("tr_dec_"))
async def tr_dec(call: types.CallbackQuery):
    data = call.data.replace("tr_dec_", "")
    g = trade_games.get(data)
    if not g:
        await call.answer("Трейд уже обработан.", show_alert=True)
        return
    if call.from_user.id != g["to_id"]:
        await call.answer("Это не твой трейд!", show_alert=True)
        return
    await call.message.edit_text("❌ Трейд отклонён.")
    try:
        await bot.send_message(g["from_id"], f"❌ *Трейд отклонён.*\n\n@{call.from_user.username or 'Игрок'} отказался.", parse_mode="Markdown")
    except Exception:
        pass
    trade_games.pop(data, None)
    await call.answer("Отклонено")


# ==================== /cancel ====================
@dp.message(Command("cancel"))
async def cancel_game(message: types.Message):
    uid = message.from_user.id
    cancelled = False
    for d in (color_games, miner_games, coin_games, wheel_games, trade_games, cards_view_games):
        if uid in d:
            del d[uid]
            cancelled = True
    if cancelled:
        await message.answer("❌ Отменено.")
    else:
        await message.answer("Нет активного действия.")


# ==================== ПРОФИЛЬ / ТОП / ПРОДАЖА / АПГРЕЙД ====================
@dp.message(Command("profile"))
async def profile(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        tu = args[1].lstrip("@").strip()
        cur.execute("SELECT user_id, username, balance, level, registered_at FROM users WHERE username = ?", (tu,))
        row = cur.fetchone()
        if not row:
            await message.answer(f"❌ @{tu} не найден.")
            return
        tid, tun, balance, level, reg = row
    else:
        tid = message.from_user.id
        tun = message.from_user.username
        balance, _, level, reg, _, _ = get_user(tid, tun)
    cur.execute("SELECT COUNT(*) FROM inventory WHERE user_id = ?", (tid,))
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM users WHERE balance > ?", (balance,))
    place = cur.fetchone()[0] + 1
    date_str = format_date_ru(reg)
    caption = (
        f"👤 Это пользователь @{tun or 'Игрок'}\n📅 С {date_str}\n\n"
        f"💰 Баланс: {balance} монет\n🏆 Место в топе: #{place}\n🎴 Карточек: {total}"
    )
    try:
        img = await make_profile_image(tid, tun, balance, place, level, total)
        photo = BufferedInputFile(img.read(), filename="profile.png")
        await message.answer_photo(photo, caption=caption)
    except Exception as e:
        await message.answer(caption + f"\n\nОшибка картинки: {e}")


@dp.message(Command("top"))
async def top(message: types.Message):
    cur.execute("SELECT username, balance FROM users ORDER BY balance DESC LIMIT 3")
    rows = cur.fetchall()
    if not rows:
        await message.answer("Пока никто.")
        return
    medals = ["🥇", "🥈", "🥉"]
    text = "🏆 *Топ-3:*\n\n"
    for i, (uname, bal) in enumerate(rows):
        name = f"@{uname}" if uname else f"Игрок #{i+1}"
        text += f"{medals[i]} *{name}*\n      💰 {bal} монет\n\n"
    await message.answer(text, parse_mode="Markdown")


@dp.message(Command("sell"))
async def sell(message: types.Message):
    uid = message.from_user.id
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Использование: /sell Название")
        return
    name = args[1].strip()
    cur.execute("SELECT rowid, card_name FROM inventory WHERE user_id = ? AND LOWER(card_name) = LOWER(?) LIMIT 1", (uid, name))
    row = cur.fetchone()
    if not row:
        await message.answer("❌ Нет такой карточки.")
        return
    real_name = row[1]
    hw = find_hw_card(real_name)
    cd = next((c for c in cards if c["name"].lower() == real_name.lower()), None)
    if hw and not cd:
        cur.execute("DELETE FROM inventory WHERE rowid = ?", (row[0],))
        cur.execute("UPDATE users SET hw_balance = hw_balance + ? WHERE user_id = ?", (hw["price"], uid))
        db.commit()
        await message.answer(f"✅ Продано: {hw['name']} за {hw['price']} 🍬")
        return
    if not cd:
        await message.answer("❌ Неизвестная.")
        return
    cur.execute("DELETE FROM inventory WHERE rowid = ?", (row[0],))
    cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (cd["price"], uid))
    db.commit()
    await message.answer(f"✅ Продано: {cd['name']} за {cd['price']} монет")


@dp.message(Command("sellall"))
async def sellall(message: types.Message):
    uid = message.from_user.id
    cur.execute("SELECT card_name, COUNT(*) FROM inventory WHERE user_id = ? GROUP BY card_name", (uid,))
    rows = cur.fetchall()
    if not rows:
        await message.answer("❌ Нет карточек.")
        return
    money_total = 0
    candy_total = 0
    text = "💰 *Будет продано:*\n\n"
    for name, cnt in rows:
        cd = next((c for c in cards if c["name"] == name), None)
        hw = find_hw_card(name)
        if cd:
            subtotal = cd["price"] * cnt
            money_total += subtotal
            text += f"• {name} × {cnt} = {subtotal} монет\n"
        elif hw:
            subtotal = hw["price"] * cnt
            candy_total += subtotal
            text += f"• {name} × {cnt} = {subtotal} 🍬\n"
    text += f"\n💵 *Монет: {money_total}*\n🍬 *Конфет: {candy_total}*"
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Да", callback_data="sellall_yes"),
        InlineKeyboardButton(text="❌ Нет", callback_data="sellall_no"),
    ]])
    sell_games[uid] = {"money": money_total, "candy": candy_total}
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")


@dp.callback_query(F.data == "sellall_yes")
async def sellall_yes(call: types.CallbackQuery):
    uid = call.from_user.id
    g = sell_games.pop(uid, None)
    if not g:
        await call.answer("Уже продано.", show_alert=True)
        return
    cur.execute("DELETE FROM inventory WHERE user_id = ?", (uid,))
    cur.execute("UPDATE users SET balance = balance + ?, hw_balance = hw_balance + ? WHERE user_id = ?", (g["money"], g["candy"], uid))
    db.commit()
    await call.message.edit_text(f"✅ Продано!\n💰 +{g['money']} монет\n🍬 +{g['candy']} конфет")
    await call.answer("Готово!")


@dp.callback_query(F.data == "sellall_no")
async def sellall_no(call: types.CallbackQuery):
    sell_games.pop(call.from_user.id, None)
    await call.message.edit_text("❌ Отменено.")
    await call.answer()


@dp.message(Command("upgrade"))
async def upgrade(message: types.Message):
    uid = message.from_user.id
    balance, _, level, _, _, _ = get_user(uid, message.from_user.username)
    if level >= MAX_LEVEL:
        await message.answer("⛔ Максимум 3.")
        return
    nl = level + 1
    price = UPGRADE_PRICES[nl]
    if balance < price:
        await message.answer(f"❌ Нужно {price}, у тебя {balance}.")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Да", callback_data=f"upg_yes_{nl}"),
        InlineKeyboardButton(text="❌ Нет", callback_data="upg_no"),
    ]])
    await message.answer(
        f"⬆️ *Улучшение до ур. {nl}*\n\nБудет выдавать {nl} карты за /card\n\n💰 Цена: {price}\n💳 У тебя: {balance}",
        reply_markup=kb, parse_mode="Markdown"
    )


@dp.callback_query(F.data.startswith("upg_"))
async def upg_cb(call: types.CallbackQuery):
    uid = call.from_user.id
    balance, _, level, _, _, _ = get_user(uid, call.from_user.username)
    if call.data == "upg_no":
        await call.message.edit_text("❌ Отменено.")
        await call.answer()
        return
    nl = int(call.data.split("_")[2])
    price = UPGRADE_PRICES[nl]
    if level >= nl:
        await call.answer("Уже куплено!", show_alert=True)
        return
    if nl != level + 1:
        await call.answer("Сначала купи предыдущий уровень.", show_alert=True)
        return
    if balance < price:
        await call.answer("Недостаточно монет!", show_alert=True)
        return
    cur.execute("UPDATE users SET balance = balance - ?, level = ? WHERE user_id = ?", (price, nl, uid))
    db.commit()
    await call.message.edit_text(f"✅ Улучшение! Теперь уровень {nl}.")
    await call.answer("Активировано!")


# ==================== СБРОС ИГРОКОВ (только для DEV_ID) ====================
# ВАЖНО: этот блок должен стоять ВЫШЕ обработчиков ввода числа и текста,
# иначе они перехватят команды.
def reset_user(uid, money_only=False):
    """money_only=True — обнуляет только монеты и конфеты.
    Иначе — полный сброс: карты, монеты, конфеты, уровень и кулдауны."""
    if money_only:
        cur.execute("UPDATE users SET balance = 0, hw_balance = 0 WHERE user_id = ?", (uid,))
    else:
        cur.execute(
            "UPDATE users SET balance = 0, hw_balance = 0, level = 1, "
            "last_card = NULL, last_daily = NULL, last_trade = NULL WHERE user_id = ?", (uid,))
        cur.execute("DELETE FROM inventory WHERE user_id = ?", (uid,))
    db.commit()
    for d in (color_games, miner_games, coin_games, wheel_games,
              trade_games, cards_view_games, sell_games):
        d.pop(uid, None)


def find_targets(tokens):
    ids, missing = [], []
    for t in tokens:
        t = t.lstrip("@")
        if t.isdigit():
            cur.execute("SELECT user_id FROM users WHERE user_id = ?", (int(t),))
        else:
            cur.execute("SELECT user_id FROM users WHERE LOWER(username) = LOWER(?)", (t,))
        row = cur.fetchone()
        if row:
            ids.append(row[0])
        else:
            missing.append(t)
    return ids, missing


@dp.message(Command("reset"))
async def reset_cmd(message: types.Message):
    if message.from_user.id != DEV_ID:
        return
    tokens = message.text.split()[1:]
    if not tokens:
        await message.answer(
            "Использование:\n"
            "/reset @user1 @user2 — полный сброс (карты, монеты, конфеты, уровень)\n"
            "/resetmoney @user — только монеты и конфеты\n"
            "/resetall — сбросить ВСЕХ"
        )
        return
    ids, missing = find_targets(tokens)
    for u in ids:
        reset_user(u)
    text = f"✅ Сброшено игроков: {len(ids)}"
    if missing:
        text += f"\n❌ Не найдены: {', '.join(map(str, missing))}"
    await message.answer(text)


@dp.message(Command("resetmoney"))
async def resetmoney_cmd(message: types.Message):
    if message.from_user.id != DEV_ID:
        return
    tokens = message.text.split()[1:]
    if not tokens:
        await message.answer("Использование: /resetmoney @user1 @user2")
        return
    ids, missing = find_targets(tokens)
    for u in ids:
        reset_user(u, money_only=True)
    text = f"✅ Монеты и конфеты обнулены у: {len(ids)}"
    if missing:
        text += f"\n❌ Не найдены: {', '.join(map(str, missing))}"
    await message.answer(text)


@dp.message(Command("resetall"))
async def resetall_cmd(message: types.Message):
    if message.from_user.id != DEV_ID:
        return
    cur.execute("SELECT COUNT(*) FROM users")
    n = cur.fetchone()[0]
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⚠️ ДА, обнулить всех", callback_data="resetall_yes"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="resetall_no"),
    ]])
    await message.answer(f"⚠️ Это удалит карты, монеты, конфеты и уровни у {n} игроков. Точно?", reply_markup=kb)


@dp.callback_query(F.data == "resetall_yes")
async def resetall_yes(call: types.CallbackQuery):
    if call.from_user.id != DEV_ID:
        await call.answer("Нет доступа", show_alert=True)
        return
    cur.execute("SELECT user_id FROM users")
    for (u,) in cur.fetchall():
        reset_user(u)
    await call.message.edit_text("✅ Все игроки обнулены.")
    await call.answer()


@dp.callback_query(F.data == "resetall_no")
async def resetall_no(call: types.CallbackQuery):
    if call.from_user.id != DEV_ID:
        await call.answer("Нет доступа", show_alert=True)
        return
    await call.message.edit_text("❌ Отменено.")
    await call.answer()


# ==================== ВВОД ЧИСЛА И ТЕКСТА ====================
# ВАЖНО: эти обработчики ДОЛЖНЫ быть в самом конце, после всех команд,
# иначе они перехватят сообщения раньше команд /profile, /top, /sell и т.д.
@dp.message(F.text.regexp(r"^\d+$"))
async def handle_number(message: types.Message):
    uid = message.from_user.id
    username = message.from_user.username or message.from_user.full_name or "Игрок"

    # ---------- Color Dice (с мерцанием перед каждым цветом) ----------
    game = color_games.get(uid)
    if game and game.get("state") == "wait_bet":
        bet = int(message.text)
        if bet <= 0:
            await message.answer("❌ Ставка > 0.")
            return
        balance, _, _, _, _, _ = get_user(uid, message.from_user.username)
        if balance < bet:
            await message.answer(f"❌ Не хватает. У тебя {balance}.")
            return
        cur.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (bet, uid))
        db.commit()
        chosen = game["color"]
        del color_games[uid]
        result = [random.choice(COLORS) for _ in range(4)]
        matches = sum(1 for c in result if c["code"] == chosen["code"])
        head = (
            f"🎲 *Color Dice* — @{username}\n"
            f"Твой цвет: {chosen['emoji']} {chosen['name']}\n"
            f"💰 Ставка: {bet}"
        )
        msg = await message.answer(f"{head}\n\n🎲 Крутим...", parse_mode="Markdown")
        await asyncio.sleep(0.8)
        progressive = []
        for c in result:
            # мерцание: эмодзи быстро меняются
            for _ in range(2):
                flick = random.choice(COLORS)["emoji"]
                await safe_edit(msg, f"{head}\n\n{' '.join(progressive + [flick])}", parse_mode="Markdown")
                await asyncio.sleep(0.4)
            # цвет фиксируется
            progressive.append(c["emoji"])
            await safe_edit(msg, f"{head}\n\n{' '.join(progressive)}", parse_mode="Markdown")
            await asyncio.sleep(0.6)
        shown = ' '.join(progressive)
        if matches == 1:
            win = bet * 2
            cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (win, uid))
            db.commit()
            rt = f"{head}\n\n{shown}\n\nСовпадений: {matches}\n🎉 *Выиграл {win} монет!* (×2)"
        elif matches == 4:
            win = bet * 4
            cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (win, uid))
            db.commit()
            rt = f"{head}\n\n{shown}\n\nСовпадений: {matches}\n🎉 *ДЖЕКПОТ! +{win}!* (×4)"
        else:
            rt = f"{head}\n\n{shown}\n\nСовпадений: {matches}\n❌ *Проиграл {bet} монет.*"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎲 Играть снова", callback_data=f"casino_color_{uid}")],
            [InlineKeyboardButton(text="🔙 Casino", callback_data=f"open_casino_{uid}")],
        ])
        await safe_edit(msg, rt, reply_markup=kb, parse_mode="Markdown")
        return

    # Минёр
    game = miner_games.get(uid)
    if game and game.get("state") == "wait_bet":
        bet = int(message.text)
        if bet <= 0:
            await message.answer("❌ Ставка > 0.")
            return
        balance, _, _, _, _, _ = get_user(uid, message.from_user.username)
        if balance < bet:
            await message.answer(f"❌ Не хватает. У тебя {balance}.")
            return
        cur.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (bet, uid))
        db.commit()
        mines_count = random.randint(2, 6)
        mines_set = set(random.sample(range(9), mines_count))
        miner_games[uid] = {"state": "playing", "bet": bet, "mines": mines_set, "opened": []}
        await message.answer(
            f"💣 *Минёр* — @{username}\n💰 Ставка: {bet}\n🟢 Открыто: 0\n📈 Множитель: ×1.0\n💵 Заберёшь: {bet}",
            reply_markup=miner_keyboard([], mines_set, uid), parse_mode="Markdown"
        )
        return

    # ---------- Колесо монстров (лента замедляется и встаёт на выпавшем) ----------
    game = wheel_games.get(uid)
    if game and game.get("state") == "wait_bet":
        bet = int(message.text)
        if bet <= 0:
            await message.answer("❌ Ставка > 0.")
            return
        balance, _, _, _, _, _ = get_user(uid, message.from_user.username)
        if balance < bet:
            await message.answer(f"❌ Не хватает. У тебя {balance}.")
            return
        cur.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (bet, uid))
        db.commit()
        del wheel_games[uid]
        seg = random.choices(WHEEL_SEGMENTS, weights=[s["weight"] for s in WHEEL_SEGMENTS])[0]
        wheel_head = f"👹 *Колесо монстров* — @{username}\n💰 Ставка: {bet}"
        msg = await message.answer(f"{wheel_head}\n\n🎡 Колесо раскручивается...", parse_mode="Markdown")
        await asyncio.sleep(0.6)
        ring = [s["emoji"] for s in WHEEL_SEGMENTS]
        n = len(ring)
        seg_idx = WHEEL_SEGMENTS.index(seg)
        delays = [0.35, 0.35, 0.4, 0.45, 0.55, 0.7, 0.9, 1.2]
        pos = (seg_idx - len(delays)) % n
        for d in delays:
            pos = (pos + 1) % n
            strip = " ".join(ring[(pos + k) % n] for k in range(-2, 3))
            await safe_edit(msg, f"{wheel_head}\n\n      ⬇️\n🎡 {strip}\n      ⬆️", parse_mode="Markdown")
            await asyncio.sleep(d)
        win = int(bet * seg["mult"])
        if win > 0:
            cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (win, uid))
            db.commit()
        head = (
            f"{wheel_head}\n\n"
            f"Выпал: {seg['emoji']} *{seg['name']}* (×{seg['mult']})\n\n"
        )
        if win > bet:
            result = f"🎉 *Выиграл {win} монет!* (+{win - bet})"
        elif win > 0:
            result = f"😬 *Вернулось {win}, потерял {bet - win}.*"
        else:
            result = f"💀 *Монстр забрал ставку: -{bet} монет.*"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👹 Крутить снова", callback_data=f"casino_wheel_{uid}")],
            [InlineKeyboardButton(text="🔙 Casino", callback_data=f"open_casino_{uid}")],
        ])
        await safe_edit(msg, head + result, reply_markup=kb, parse_mode="Markdown")
        return

    # ---------- Орёл и Решка (монетка крутится в воздухе) ----------
    game = coin_games.get(uid)
    if game and game.get("state") == "wait_bet":
        bet = int(message.text)
        if bet <= 0:
            await message.answer("❌ Ставка > 0.")
            return
        balance, _, _, _, _, _ = get_user(uid, message.from_user.username)
        if balance < bet:
            await message.answer(f"❌ Не хватает. У тебя {balance}.")
            return
        cur.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (bet, uid))
        db.commit()
        choice = game["choice"]
        del coin_games[uid]
        my_choice_emoji = "🦅" if choice == "heads" else "🪙"
        my_choice_name = "Орёл" if choice == "heads" else "Монета"
        coin_head = (
            f"🪙 *Орёл и Решка* — @{username}\n"
            f"Твой выбор: {my_choice_emoji} {my_choice_name}\n"
            f"💰 Ставка: {bet}"
        )
        msg = await message.answer(f"{coin_head}\n\nМонетку подбрасывают...", parse_mode="Markdown")
        await asyncio.sleep(0.6)
        for frame in ["🪙 ⬆️", "🪙\n⬆️", "🌀 🪙 🌀", "🪙\n⬇️", "🪙 ⬇️"]:
            await safe_edit(msg, f"{coin_head}\n\n{frame}", parse_mode="Markdown")
            await asyncio.sleep(0.5)
        result = random.choice(["heads", "tails"])
        result_emoji = "🦅" if result == "heads" else "🪙"
        result_name = "Орёл" if result == "heads" else "Монета"
        if result == choice:
            win = bet * 2
            cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (win, uid))
            db.commit()
            text = f"{coin_head}\n\nВыпало: {result_emoji} {result_name}\n\n🎉 *Победа! +{win} монет!* (×2)"
        else:
            text = f"{coin_head}\n\nВыпало: {result_emoji} {result_name}\n\n❌ *Проигрыш. -{bet} монет.*"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🪙 Играть снова", callback_data=f"casino_coin_{uid}")],
            [InlineKeyboardButton(text="🔙 Casino", callback_data=f"open_casino_{uid}")],
        ])
        await safe_edit(msg, text, reply_markup=kb, parse_mode="Markdown")
        return


@dp.message(F.text)
async def handle_text(message: types.Message):
    uid = message.from_user.id
    if message.text.startswith("/"):
        return
    # Поиск в /cards
    g = cards_view_games.get(uid)
    if g and g.get("state") == "wait_search":
        g["filter"] = message.text.strip()
        g["page"] = 0
        g["state"] = None
        await send_cards_page(message, uid)
        return
    # Поиск в трейде
    g = trade_games.get(uid)
    if g and g.get("state") == "wait_search_my":
        query = message.text.strip().lower()
        filtered = [n for n in g["my_cards"] if query in n.lower()]
        if not filtered:
            await message.answer("🔍 Ничего не найдено. Попробуй другое.")
            return
        g["my_cards"] = filtered
        g["page"] = 0
        g["state"] = None
        await send_trade_my_page(message, uid)
        return


# ==================== ЗАПУСК ====================
async def main():
    # заранее собираем видео выпадения в фоне, пока бот уже принимает команды
    prerender_task = asyncio.create_task(prerender_videos())
    try:
        await dp.start_polling(bot)
    finally:
        prerender_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
