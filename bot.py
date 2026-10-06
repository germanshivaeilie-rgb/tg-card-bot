import asyncio
import io
import os
import random
import sqlite3
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from aiogram.filters import Command
from PIL import Image, ImageDraw, ImageFont

BOT_TOKEN = os.getenv("BOT_TOKEN")
COOLDOWN_MINUTES = 15

FONT_PATH = "Roboto-Italic-VariableFont_wdth,wght.ttf"
BG_PATH = "ChatGPT Image 5 окт. 2026 г., 09_26_45.png"
BOSS_ALIVE = "ChatGPT Image 6 окт. 2026 г., 12_17_38.png"
BOSS_DEAD = "ChatGPT Image 6 окт. 2026 г., 12_19_03.png"
HW_BANNER = "ChatGPT Image 6 окт. 2026 г., 11_12_35.png"

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
        "😱 Кошмарная": [
            {"name": "Кошмарный Moggfone", "price": 500000, "file": "ChatGPT Image 6 окт. 2026 г., 15_28_10.png"},
        ],
    },
}

CASE_CHANCES = {
    "pumpkin": {
        "🎃 Тыквенная": 70,
        "👻 Призрачная": 25,
        "🧙 Ведьминская": 4,
        "🧛 Вампирская": 1,
    },
    "skeleton": {
        "👻 Призрачная": 35,
        "🧙 Ведьминская": 25,
        "🧛 Вампирская": 20,
        "💀 Скелетная": 15,
        "😈 Демоническая": 5,
    },
    "ghost": {
        "🧙 Ведьминская": 40,
        "🧛 Вампирская": 30,
        "💀 Скелетная": 18,
        "😈 Демоническая": 11.334,
        "😱 Кошмарная": 0.666,
    },
}

CASE_PRICES = {
    "pumpkin": 1000,
    "skeleton": 10000,
    "ghost": 100000,
}

HALLOWEEN_RATE_TO = 10
HALLOWEEN_RATE_BACK = 0.9

BOSS_MAX_HP = 100
PLAYER_MAX_HP = 100
BOSS_DAMAGE = 10
PLAYER_DAMAGE = 10
BOSS_ATTACK_EVERY = 3
BOSS_ATTACK_DAMAGE = 5
BOSS_COOLDOWN_MINUTES = 60
BOSS_REWARD_CANDY = 500

boss_games = {}
boss_cooldowns = {}
boss_lock = {"current": None}

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
hw_games = {}

db = sqlite3.connect("game.db")
cur = db.cursor()
cur.execute("""CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    balance INTEGER DEFAULT 0,
    last_card TEXT,
    level INTEGER DEFAULT 1,
    registered_at TEXT,
    hw_balance INTEGER DEFAULT 0
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

try:
    cur.execute("SELECT hw_balance FROM users LIMIT 1")
except sqlite3.OperationalError:
    cur.execute("ALTER TABLE users ADD COLUMN hw_balance INTEGER DEFAULT 0")
    db.commit()

try:
    cur.execute("SELECT registered_at FROM users LIMIT 1")
except sqlite3.OperationalError:
    cur.execute("ALTER TABLE users ADD COLUMN registered_at TEXT")
    db.commit()

today = datetime.now().isoformat()
cur.execute("UPDATE users SET registered_at = ? WHERE registered_at IS NULL", (today,))
db.commit()


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


def roll_hw_card(case_type):
    chances = CASE_CHANCES[case_type]
    cards_pool = HW_CARDS[case_type]
    total = sum(chances.values())
    r = random.uniform(0, total)
    upto = 0
    chosen = None
    for rarity, chance in chances.items():
        upto += chance
        if r <= upto:
            chosen = rarity
            break
    pool = cards_pool.get(chosen, [])
    if not pool:
        pool = list(cards_pool.values())[0]
    return random.choice(pool), chosen


def find_hw_card(name):
    for case_type, rarities in HW_CARDS.items():
        for rarity, lst in rarities.items():
            for c in lst:
                if c["name"].lower() == name.lower():
                    return c
    return None


def get_user(uid, username=None):
    cur.execute("SELECT balance, last_card, level, registered_at, hw_balance FROM users WHERE user_id = ?", (uid,))
    row = cur.fetchone()
    if not row:
        now = datetime.now().isoformat()
        cur.execute("INSERT INTO users (user_id, username, registered_at) VALUES (?, ?, ?)", (uid, username, now))
        db.commit()
        return 0, None, 1, now, 0
    if username:
        cur.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, uid))
        db.commit()
    return row[0], row[1], row[2], row[3], row[4]


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


@dp.message(Command("start"))
async def start(message: types.Message):
    get_user(message.from_user.id, message.from_user.username)
    await message.answer(
        "🎴 Привет! Я бот-коллекционер карточек.\n\n"
        "/card — выбить карточку\n"
        "/casino — 🎰 Casino\n"
        "/halloween — 🎃 Хеллоуин\n"
        "/mycards — инвентарь\n"
        "/balance — баланс\n"
        "/sell — продать\n"
        "/sellall — продать всё\n"
        "/upgrade — улучшение\n"
        "/profile — профиль\n"
        "/top — топ-3\n"
        "/trade @username Название — трейд\n"
        "/accept, /decline — трейд"
    )


@dp.message(Command("card"))
async def card(message: types.Message):
    uid = message.from_user.id
    username = message.from_user.username or "Игрок"
    balance, last, level, _, _ = get_user(uid, message.from_user.username)
    if last:
        last_dt = datetime.fromisoformat(last)
        elapsed = datetime.now() - last_dt
        if elapsed < timedelta(minutes=COOLDOWN_MINUTES):
            left = timedelta(minutes=COOLDOWN_MINUTES) - elapsed
            await message.answer(f"@{username}, ты уже крутил, открой позже.\n⏳ Ждать ещё: {format_cooldown(int(left.total_seconds()))}")
            return
    cur.execute("UPDATE users SET last_card = ? WHERE user_id = ?", (datetime.now().isoformat(), uid))
    db.commit()
    for _ in range(level):
        c = roll_card()
        cur.execute("INSERT INTO inventory (user_id, card_name) VALUES (?, ?)", (uid, c["name"]))
        db.commit()
        cur.execute("SELECT rowid FROM inventory WHERE user_id = ? AND card_name = ? ORDER BY rowid DESC LIMIT 1", (uid, c["name"]))
        inv_id = cur.fetchone()[0]
        caption = f"@{username}, вам выпала:\n🎴 {c['name']}\n{c['rarity']} | 💰 Цена: {c['price']} монет"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"💰 Продать: {c['name']} ({c['price']})", callback_data=f"sell_card_{inv_id}_{c['price']}")],
            [InlineKeyboardButton(text="🎰 Casino", callback_data=f"open_casino_{uid}")],
        ])
        photo = FSInputFile(c["file"])
        await message.answer_photo(photo, caption=caption, reply_markup=kb)


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
    cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (price, uid))
    db.commit()
    await call.message.edit_caption(caption=f"✅ Продано: {row[0]} за {price} монет", reply_markup=None)
    await call.answer(f"Получено {price} монет!")


@dp.message(Command("casino"))
async def casino_command(message: types.Message):
    uid = message.from_user.id
    username = message.from_user.username or message.from_user.full_name or "Игрок"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲 Color Dice", callback_data=f"casino_color_{uid}")],
        [InlineKeyboardButton(text="💣 Минёр", callback_data=f"casino_miner_{uid}")],
        [InlineKeyboardButton(text="🔙 Закрыть", callback_data=f"casino_close_{uid}")],
    ])
    await message.answer(f"🎰 *Casino* — @{username}\n\nВыбери игру:", reply_markup=kb, parse_mode="Markdown")


@dp.callback_query(F.data.startswith("open_casino_"))
async def open_casino(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Это не твоё меню!", show_alert=True)
        return
    username = call.from_user.username or call.from_user.full_name or "Игрок"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲 Color Dice", callback_data=f"casino_color_{uid}")],
        [InlineKeyboardButton(text="💣 Минёр", callback_data=f"casino_miner_{uid}")],
        [InlineKeyboardButton(text="🔙 Закрыть", callback_data=f"casino_close_{uid}")],
    ])
    await call.message.answer(f"🎰 *Casino* — @{username}\n\nВыбери игру:", reply_markup=kb, parse_mode="Markdown")
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
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲 Color Dice", callback_data=f"casino_color_{uid}")],
        [InlineKeyboardButton(text="💣 Минёр", callback_data=f"casino_miner_{uid}")],
        [InlineKeyboardButton(text="🔙 Закрыть", callback_data=f"casino_close_{uid}")],
    ])
    await call.message.edit_text(f"🎰 *Casino* — @{username}\n\nВыбери игру:", reply_markup=kb, parse_mode="Markdown")
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


@dp.message(Command("halloween"))
async def halloween_menu(message: types.Message):
    uid = message.from_user.id
    username = message.from_user.username or message.from_user.full_name or "Игрок"
    balance, _, _, _, hw = get_user(uid, message.from_user.username)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎃 КЕЙСЫ", callback_data=f"hw_cases_{uid}")],
        [InlineKeyboardButton(text="🎃 Хеллоуин-Босс", callback_data=f"hw_boss_{uid}")],
        [InlineKeyboardButton(text="💱 Конвертация", callback_data=f"hw_conv_{uid}")],
        [InlineKeyboardButton(text="🔙 Закрыть", callback_data=f"hw_close_{uid}")],
    ])
    caption = (
        f"🎃 *Хеллоуин* — @{username}\n\n"
        f"💀 Здравствуйте, смертные!\n"
        f"Встречайте Хеллоуин — время ужаса и карточек!\n\n"
        f"💰 Обычных монет: {balance}\n"
        f"🍬 Конфет: {hw}\n\n"
        f"*Выбирай:*"
    )
    try:
        photo = FSInputFile(HW_BANNER)
        await message.answer_photo(photo, caption=caption, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        await message.answer(caption, reply_markup=kb, parse_mode="Markdown")


@dp.callback_query(F.data.startswith("hw_close_"))
async def hw_close(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Не твоё меню!", show_alert=True)
        return
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.answer()


@dp.callback_query(F.data.startswith("hw_soon_"))
async def hw_soon(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Не твоё меню!", show_alert=True)
        return
    await call.answer("🔒 Скоро!", show_alert=True)


@dp.callback_query(F.data.startswith("hw_back_"))
async def hw_back(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Не твоё меню!", show_alert=True)
        return
    username = call.from_user.username or call.from_user.full_name or "Игрок"
    balance, _, _, _, hw = get_user(uid)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎃 КЕЙСЫ", callback_data=f"hw_cases_{uid}")],
        [InlineKeyboardButton(text="🎃 Хеллоуин-Босс", callback_data=f"hw_boss_{uid}")],
        [InlineKeyboardButton(text="💱 Конвертация", callback_data=f"hw_conv_{uid}")],
        [InlineKeyboardButton(text="🔙 Закрыть", callback_data=f"hw_close_{uid}")],
    ])
    caption = (
        f"🎃 *Хеллоуин* — @{username}\n\n"
        f"💰 Обычных монет: {balance}\n🍬 Конфет: {hw}\n\n"
        f"*Выбирай:*"
    )
    try:
        await call.message.delete()
        photo = FSInputFile(HW_BANNER)
        await call.message.answer_photo(photo, caption=caption, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        try:
            await call.message.edit_caption(caption=caption, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass
    await call.answer()


@dp.callback_query(F.data.startswith("hw_cases_"))
async def hw_cases_menu(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Не твоё меню!", show_alert=True)
        return
    username = call.from_user.username or call.from_user.full_name or "Игрок"
    balance, _, _, _, hw = get_user(uid)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎃 Тыквенный кейс — 1000 🍬", callback_data=f"hw_case_pumpkin_{uid}")],
        [InlineKeyboardButton(text="💀 Скелетный кейс — 10000 🍬", callback_data=f"hw_case_skeleton_{uid}")],
        [InlineKeyboardButton(text="👻 Призрачный кейс — 100000 🍬", callback_data=f"hw_case_ghost_{uid}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"hw_back_{uid}")],
    ])
    await call.message.edit_caption(
        caption=(
            f"🎃 *Кейсы Хеллоуина* — @{username}\n\n"
            f"🍬 У тебя: {hw} конфет\n\n"
            f"*Выбирай кейс:*"
        ),
        reply_markup=kb, parse_mode="Markdown"
    )
    await call.answer()


@dp.callback_query(F.data.startswith("hw_conv_"))
async def hw_convert_menu(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Не твоё меню!", show_alert=True)
        return
    username = call.from_user.username or call.from_user.full_name or "Игрок"
    balance, _, _, _, hw = get_user(uid)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💱 Монеты → 🍬 (100 = 10)", callback_data=f"hw_to_{uid}")],
        [InlineKeyboardButton(text="💱 🍬 → Монеты (10 = 9)", callback_data=f"hw_from_{uid}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"hw_back_{uid}")],
    ])
    await call.message.edit_caption(
        caption=(
            f"💱 *Конвертация* — @{username}\n\n"
            f"💰 Обычных: {balance}\n🍬 Конфет: {hw}\n\nЧто делаем?"
        ),
        reply_markup=kb, parse_mode="Markdown"
    )
    await call.answer()


@dp.callback_query(F.data.startswith("hw_to_"))
async def hw_convert_to(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Не твоё меню!", show_alert=True)
        return
    hw_games[uid] = {"state": "wait_amount_to"}
    await call.message.edit_caption(
        caption="💱 *Монеты → 🍬*\n\nКурс: 100 монет = 10 🍬\n\nНапиши, сколько *монет* обменять (кратно 100).\nПример: `100` → 10 🍬\n\nОтмена — /cancel",
        parse_mode="Markdown"
    )
    await call.answer()


@dp.callback_query(F.data.startswith("hw_from_"))
async def hw_convert_from(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Не твоё меню!", show_alert=True)
        return
    hw_games[uid] = {"state": "wait_amount_from"}
    await call.message.edit_caption(
        caption="💱 *🍬 → Монеты*\n\nКурс: 10 🍬 = 9 монет (налог 10%)\n\nНапиши, сколько *🍬* обменять (кратно 10).\nПример: `10` → 9 монет\n\nОтмена — /cancel",
        parse_mode="Markdown"
    )
    await call.answer()


CASE_NAMES = {
    "pumpkin": "🎃 Тыквенный",
    "skeleton": "💀 Скелетный",
    "ghost": "👻 Призрачный",
}


@dp.callback_query(F.data.startswith("hw_case_"))
async def hw_case_open_menu(call: types.CallbackQuery):
    parts = call.data.split("_")
    case_type = parts[2]
    uid = int(parts[3])
    if call.from_user.id != uid:
        await call.answer("Не твоё меню!", show_alert=True)
        return

    username = call.from_user.username or call.from_user.full_name or "Игрок"
    balance, _, _, _, hw = get_user(uid)
    price = CASE_PRICES[case_type]

    chances = CASE_CHANCES[case_type]
    chances_text = "\n".join([f"{r} — {c}%" for r, c in chances.items()])

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🎁 Открыть за {price} 🍬", callback_data=f"hw_open_{case_type}_{uid}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"hw_cases_{uid}")],
    ])
    await call.message.edit_caption(
        caption=(
            f"{CASE_NAMES[case_type]} *кейс* — @{username}\n\n"
            f"💰 Цена: {price} 🍬\n🍬 У тебя: {hw}\n\n"
            f"*Что выпадает:*\n{chances_text}"
        ),
        reply_markup=kb, parse_mode="Markdown"
    )
    await call.answer()


@dp.callback_query(F.data.startswith("hw_open_"))
async def hw_open_case(call: types.CallbackQuery):
    parts = call.data.split("_")
    case_type = parts[2]
    uid = int(parts[3])
    if call.from_user.id != uid:
        await call.answer("Не твоё меню!", show_alert=True)
        return

    username = call.from_user.username or call.from_user.full_name or "Игрок"
    balance, _, _, _, hw = get_user(uid)
    price = CASE_PRICES[case_type]

    if hw < price:
        await call.answer(f"❌ Нужно {price} 🍬, у тебя {hw}", show_alert=True)
        return

    cur.execute("UPDATE users SET hw_balance = hw_balance - ? WHERE user_id = ?", (price, uid))
    db.commit()
    card, rarity = roll_hw_card(case_type)
    cur.execute("INSERT INTO inventory (user_id, card_name) VALUES (?, ?)", (uid, card["name"]))
    db.commit()
    new_hw = hw - price

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Открыть ещё", callback_data=f"hw_open_{case_type}_{uid}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"hw_cases_{uid}")],
    ])

    try:
        photo = FSInputFile(card["file"])
        caption = (
            f"{CASE_NAMES[case_type]} *кейс* — @{username}\n\n"
            f"🎉 Тебе выпала карточка!\n\n"
            f"🎴 *{card['name']}*\nРедкость: {rarity}\n💰 Цена: {card['price']} 🍬\n\n"
            f"🍬 Осталось: {new_hw}"
        )
        await call.message.delete()
        await call.message.answer_photo(photo, caption=caption, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        await call.message.edit_caption(
            caption=f"🎉 Выпала: *{card['name']}* ({rarity}, {card['price']} 🍬)\n🍬 Осталось: {new_hw}",
            reply_markup=kb, parse_mode="Markdown"
        )
    await call.answer("🎁 Кейс открыт!")


def boss_round_info(round_num):
    if round_num == 1:
        return 4, 1
    elif round_num == 2:
        return 9, 2
    elif round_num == 3:
        return 12, 1
    elif round_num == 4:
        return 16, 4
    else:
        return 20, 2


def boss_render_text(game, uid):
    username = game["username"]
    boss_hp = game["boss_hp"]
    player_hp = game["player_hp"]
    round_num = game["round"]
    total_rounds = 5
    _, pumpkins_count = boss_round_info(round_num)
    found = len(game["found_pumpkins"])
    moves = game.get("moves", 0)
    next_attack = 3 - (moves % 3)
    if next_attack == 3:
        next_attack = 0
    if next_attack > 0:
        attack_info = f"⚔️ Атака босса через: {next_attack} ход(а)"
    else:
        attack_info = "⚔️ Босс атакует на следующем ходу!"
    return (
        f"🎃 *ХЕЛЛОУИН-БОСС* — @{username}\n\n"
        f"💀 Босс: {boss_hp}/{BOSS_MAX_HP} HP\n"
        f"❤️ Ты: {player_hp}/{PLAYER_MAX_HP} HP\n\n"
        f"📍 Раунд {round_num}/{total_rounds}\n"
        f"🎃 Найдено тыкв: {found}/{pumpkins_count}\n"
        f"{attack_info}\n\n"
        f"*Правила:*\n"
        f"🎃 Тыква → боссу −10 HP\n"
        f"❌ Промах → тебе −10 HP\n"
        f"⚔️ Каждые 3 хода → тебе −5 HP"
    )


def boss_build_kb(game):
    cells = game["cells"]
    opened = game["opened"]
    pumpkins = game["pumpkins"]
    buttons = []
    row = []
    for i in range(cells):
        if i in opened:
            if i in pumpkins:
                row.append(InlineKeyboardButton(text="🎃", callback_data="boss_noop"))
            else:
                row.append(InlineKeyboardButton(text="❌", callback_data="boss_noop"))
        else:
            row.append(InlineKeyboardButton(text="🍬", callback_data=f"boss_cell_{i}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="🏳️ Сдаться", callback_data="boss_surrender")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@dp.callback_query(F.data.regexp(r"^hw_boss_\d+$"))
async def hw_boss_start(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Не твоё меню!", show_alert=True)
        return

    if uid in boss_cooldowns:
        elapsed = datetime.now() - boss_cooldowns[uid]
        if elapsed < timedelta(minutes=BOSS_COOLDOWN_MINUTES):
            left = timedelta(minutes=BOSS_COOLDOWN_MINUTES) - elapsed
            await call.answer(f"⏳ Кулдаун: {format_cooldown(int(left.total_seconds()))}", show_alert=True)
            return

    if boss_lock["current"] is not None and boss_lock["current"] != uid:
        await call.answer("⏳ Кто-то уже сражается с боссом! Подожди.", show_alert=True)
        return

    username = call.from_user.username or call.from_user.full_name or "Игрок"
    cells, pumpkins_count = boss_round_info(1)
    pumpkins = set(random.sample(range(cells), pumpkins_count))

    boss_games[uid] = {
        "boss_hp": BOSS_MAX_HP,
        "player_hp": PLAYER_MAX_HP,
        "round": 1,
        "opened": [],
        "found_pumpkins": set(),
        "pumpkins": pumpkins,
        "cells": cells,
        "pumpkins_count": pumpkins_count,
        "username": username,
        "moves": 0,
    }
    boss_lock["current"] = uid
    kb = boss_build_kb(boss_games[uid])

    try:
        photo = FSInputFile(BOSS_ALIVE)
        await call.message.delete()
        await call.message.answer_photo(
            photo,
            caption=boss_render_text(boss_games[uid], uid),
            reply_markup=kb, parse_mode="Markdown"
        )
    except Exception:
        try:
            await call.message.edit_caption(
                caption=boss_render_text(boss_games[uid], uid),
                reply_markup=kb, parse_mode="Markdown"
            )
        except Exception:
            pass
    await call.answer("⚔️ Бой начался!")


@dp.callback_query(F.data == "boss_noop")
async def boss_noop(call: types.CallbackQuery):
    await call.answer("Уже открыто.")


@dp.callback_query(F.data.startswith("boss_cell_"))
async def boss_cell(call: types.CallbackQuery):
    parts = call.data.split("_")
    idx = int(parts[2])
    uid = call.from_user.id

    game = boss_games.get(uid)
    if not game:
        await call.answer("Игра не активна.", show_alert=True)
        return
    if idx in game["opened"]:
        await call.answer("Уже открыто.")
        return

    game["opened"].append(idx)
    game["moves"] += 1

    boss_attacked = False
    if game["moves"] % BOSS_ATTACK_EVERY == 0:
        game["player_hp"] -= BOSS_ATTACK_DAMAGE
        boss_attacked = True
        if game["player_hp"] <= 0:
            boss_lock["current"] = None
            boss_cooldowns[uid] = datetime.now()
            cur.execute("SELECT hw_balance FROM users WHERE user_id = ?", (uid,))
            row = cur.fetchone()
            hw = row[0] if row else 0
            lost = hw // 2
            cur.execute("UPDATE users SET hw_balance = hw_balance - ? WHERE user_id = ?", (lost, uid))
            db.commit()
            del boss_games[uid]
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data=f"hw_boss_done_{uid}")]
            ])
            try:
                photo = FSInputFile(BOSS_ALIVE)
                await call.message.delete()
                await call.message.answer_photo(
                    photo,
                    caption=(
                        f"💀 *БОСС ДОБИЛ ТЕБЯ!*\n\n"
                        f"❤️ Ты: 0/{PLAYER_MAX_HP} HP\n"
                        f"💀 Босс: {game['boss_hp']}/{BOSS_MAX_HP} HP\n\n"
                        f"🍬 Потеряно: {lost} конфет (50%)\n\n"
                        f"⏳ Кулдаун: 1 час"
                    ),
                    reply_markup=kb, parse_mode="Markdown"
                )
            except Exception:
                pass
            await call.answer("💀 Босс тебя добил!")
            return

    if idx in game["pumpkins"]:
        game["found_pumpkins"].add(idx)
        game["boss_hp"] -= BOSS_DAMAGE
        if game["boss_hp"] < 0:
            game["boss_hp"] = 0

        if game["boss_hp"] <= 0:
            boss_lock["current"] = None
            boss_cooldowns[uid] = datetime.now()
            cur.execute("INSERT INTO inventory (user_id, card_name) VALUES (?, ?)", (uid, "Хеллоуинский босс"))
            cur.execute("UPDATE users SET hw_balance = hw_balance + ? WHERE user_id = ?", (BOSS_REWARD_CANDY, uid))
            db.commit()
            del boss_games[uid]
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data=f"hw_boss_done_{uid}")]
            ])
            try:
                photo = FSInputFile(BOSS_DEAD)
                await call.message.delete()
                await call.message.answer_photo(
                    photo,
                    caption=(
                        f"🎉 *ПОЗДРАВЛЯЮ, ВЫ ПОБЕДИЛИ БОССА!*\n\n"
                        f"💀 Босс: 0/{BOSS_MAX_HP} HP\n\n"
                        f"🎴 Получена карточка: *Хеллоуинский босс*\n"
                        f"💠 Специальная | 💰 100 000 монет\n\n"
                        f"🍬 +{BOSS_REWARD_CANDY} конфет\n\n"
                        f"⏳ Кулдаун: 1 час"
                    ),
                    reply_markup=kb, parse_mode="Markdown"
                )
            except Exception:
                pass
            await call.answer("🎉 БОСС ПОВЕРЖЕН!")
            return

        if len(game["found_pumpkins"]) >= game["pumpkins_count"]:
            if game["round"] >= 5:
                game["round"] = 5
                cells, pc = boss_round_info(5)
                game["cells"] = cells
                game["pumpkins_count"] = pc
                game["pumpkins"] = set(random.sample(range(cells), pc))
                game["opened"] = []
                game["found_pumpkins"] = set()
            else:
                game["round"] += 1
                cells, pc = boss_round_info(game["round"])
                game["cells"] = cells
                game["pumpkins_count"] = pc
                game["pumpkins"] = set(random.sample(range(cells), pc))
                game["opened"] = []
                game["found_pumpkins"] = set()

        kb = boss_build_kb(game)
        try:
            await call.message.edit_caption(
                caption=boss_render_text(game, uid),
                reply_markup=kb, parse_mode="Markdown"
            )
        except Exception:
            pass
        msg = f"🎃 Тыква! Босс −{BOSS_DAMAGE} HP"
        if boss_attacked:
            msg += f" | ⚔️ Босс −{BOSS_ATTACK_DAMAGE} тебе!"
        await call.answer(msg)
        return
    else:
        game["player_hp"] -= PLAYER_DAMAGE
        if game["player_hp"] <= 0:
            boss_lock["current"] = None
            boss_cooldowns[uid] = datetime.now()
            cur.execute("SELECT hw_balance FROM users WHERE user_id = ?", (uid,))
            row = cur.fetchone()
            hw = row[0] if row else 0
            lost = hw // 2
            cur.execute("UPDATE users SET hw_balance = hw_balance - ? WHERE user_id = ?", (lost, uid))
            db.commit()
            del boss_games[uid]
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data=f"hw_boss_done_{uid}")]
            ])
            try:
                photo = FSInputFile(BOSS_ALIVE)
                await call.message.delete()
                await call.message.answer_photo(
                    photo,
                    caption=(
                        f"💀 *ТЫ ПАЛ В БОЮ*\n\n"
                        f"❤️ Ты: 0/{PLAYER_MAX_HP} HP\n"
                        f"💀 Босс: {game['boss_hp']}/{BOSS_MAX_HP} HP\n\n"
                        f"🍬 Потеряно: {lost} конфет (50%)\n\n"
                        f"⏳ Кулдаун: 1 час"
                    ),
                    reply_markup=kb, parse_mode="Markdown"
                )
            except Exception:
                pass
            await call.answer("💀 Ты проиграл!")
            return

        kb = boss_build_kb(game)
        try:
            await call.message.edit_caption(
                caption=boss_render_text(game, uid),
                reply_markup=kb, parse_mode="Markdown"
            )
        except Exception:
            pass
        msg = f"❌ Промах! Тебе −{PLAYER_DAMAGE} HP"
        if boss_attacked:
            msg += f" | ⚔️ Босс ещё −{BOSS_ATTACK_DAMAGE}!"
        await call.answer(msg)
        return


@dp.callback_query(F.data == "boss_surrender")
async def boss_surrender(call: types.CallbackQuery):
    uid = call.from_user.id
    game = boss_games.get(uid)
    if not game:
        await call.answer("Нет активной игры.")
        return
    boss_lock["current"] = None
    boss_cooldowns[uid] = datetime.now()
    del boss_games[uid]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"hw_boss_done_{uid}")]
    ])
    try:
        await call.message.edit_caption(
            caption="🏳️ *Ты сдался!*\n\n⏳ Кулдаун: 1 час",
            reply_markup=kb, parse_mode="Markdown"
        )
    except Exception:
        pass
    await call.answer("Сдался")


@dp.callback_query(F.data.startswith("hw_boss_done_"))
async def hw_boss_done(call: types.CallbackQuery):
    uid = int(call.data.split("_")[3])
    if call.from_user.id != uid:
        await call.answer("Не твоё меню!", show_alert=True)
        return
    username = call.from_user.username or call.from_user.full_name or "Игрок"
    balance, _, _, _, hw = get_user(uid)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎃 КЕЙСЫ", callback_data=f"hw_cases_{uid}")],
        [InlineKeyboardButton(text="🎃 Хеллоуин-Босс", callback_data=f"hw_boss_{uid}")],
        [InlineKeyboardButton(text="💱 Конвертация", callback_data=f"hw_conv_{uid}")],
        [InlineKeyboardButton(text="🔙 Закрыть", callback_data=f"hw_close_{uid}")],
    ])
    caption = (
        f"🎃 *Хеллоуин* — @{username}\n\n"
        f"💰 Обычных монет: {balance}\n🍬 Конфет: {hw}\n\n"
        f"*Выбирай:*"
    )
    try:
        await call.message.delete()
        photo = FSInputFile(HW_BANNER)
        await call.message.answer_photo(photo, caption=caption, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        pass
    await call.answer()


# ==== /cancel ====
@dp.message(Command("cancel"))
async def cancel_game(message: types.Message):
    uid = message.from_user.id
    cancelled = False
    if uid in color_games:
        del color_games[uid]
        cancelled = True
    if uid in miner_games:
        del miner_games[uid]
        cancelled = True
    if uid in hw_games:
        del hw_games[uid]
        cancelled = True
    if uid in boss_games:
        boss_lock["current"] = None
        boss_cooldowns[uid] = datetime.now()
        del boss_games[uid]
        cancelled = True
    if cancelled:
        await message.answer("❌ Отменено.")
    else:
        await message.answer("Нет активного действия.")


@dp.message(F.text.regexp(r"^\d+$"))
async def handle_bet(message: types.Message):
    uid = message.from_user.id
    username = message.from_user.username or message.from_user.full_name or "Игрок"

    hw_game = hw_games.get(uid)
    if hw_game and hw_game.get("state") == "wait_amount_to":
        amount = int(message.text)
        if amount <= 0 or amount % 100 != 0:
            await message.answer("❌ Сумма кратна 100.")
            return
        balance, _, _, _, hw = get_user(uid, message.from_user.username)
        if balance < amount:
            await message.answer(f"❌ Не хватает. У тебя {balance}, нужно {amount}.")
            return
        hw_get = amount // 10
        cur.execute("UPDATE users SET balance = balance - ?, hw_balance = hw_balance + ? WHERE user_id = ?", (amount, hw_get, uid))
        db.commit()
        del hw_games[uid]
        await message.answer(f"✅ Обмен!\n💰 -{amount}\n🍬 +{hw_get}")
        return

    if hw_game and hw_game.get("state") == "wait_amount_from":
        amount = int(message.text)
        if amount <= 0 or amount % 10 != 0:
            await message.answer("❌ Кратно 10.")
            return
        balance, _, _, _, hw = get_user(uid, message.from_user.username)
        if hw < amount:
            await message.answer(f"❌ Не хватает 🍬. У тебя {hw}, нужно {amount}.")
            return
        money_get = int(amount * HALLOWEEN_RATE_BACK)
        cur.execute("UPDATE users SET hw_balance = hw_balance - ?, balance = balance + ? WHERE user_id = ?", (amount, money_get, uid))
        db.commit()
        del hw_games[uid]
        await message.answer(f"✅ Обмен!\n🍬 -{amount}\n💰 +{money_get} (налог 10%)")
        return

    game = color_games.get(uid)
    if game and game.get("state") == "wait_bet":
        bet = int(message.text)
        if bet <= 0:
            await message.answer("❌ Ставка > 0.")
            return
        balance, _, _, _, _ = get_user(uid, message.from_user.username)
        if balance < bet:
            await message.answer(f"❌ Не хватает. У тебя {balance}, нужно {bet}.")
            return
        cur.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (bet, uid))
        db.commit()
        chosen = game["color"]
        del color_games[uid]
        result = [random.choice(COLORS) for _ in range(4)]
        matches = sum(1 for c in result if c["code"] == chosen["code"])
        msg = await message.answer(f"🎲 Крутим...\n\n{chosen['emoji']}")
        await asyncio.sleep(0.9)
        progressive = []
        for c in result:
            progressive.append(c["emoji"])
            text = f"🎲 *Color Dice* — @{username}\nТвой цвет: {chosen['emoji']} {chosen['name']}\n💰 Ставка: {bet}\n\n{' '.join(progressive)}"
            await msg.edit_text(text, parse_mode="Markdown")
            await asyncio.sleep(0.9)
        if matches == 1:
            win = bet * 2
            cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (win, uid))
            db.commit()
            rt = f"🎲 *Color Dice* — @{username}\nТвой цвет: {chosen['emoji']} {chosen['name']}\n💰 Ставка: {bet}\n\n{' '.join(progressive)}\n\nСовпадений: {matches}\n🎉 *Выиграл {win} монет!* (×2)"
        elif matches == 4:
            win = bet * 4
            cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (win, uid))
            db.commit()
            rt = f"🎲 *Color Dice* — @{username}\nТвой цвет: {chosen['emoji']} {chosen['name']}\n💰 Ставка: {bet}\n\n{' '.join(progressive)}\n\nСовпадений: {matches}\n🎉 *ДЖЕКПОТ! +{win}!* (×4)"
        else:
            rt = f"🎲 *Color Dice* — @{username}\nТвой цвет: {chosen['emoji']} {chosen['name']}\n💰 Ставка: {bet}\n\n{' '.join(progressive)}\n\nСовпадений: {matches}\n❌ *Проиграл {bet} монет.*"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎲 Играть снова", callback_data=f"casino_color_{uid}")],
            [InlineKeyboardButton(text="🔙 Casino", callback_data=f"open_casino_{uid}")],
        ])
        await msg.edit_text(rt, reply_markup=kb, parse_mode="Markdown")
        return

    game = miner_games.get(uid)
    if game and game.get("state") == "wait_bet":
        bet = int(message.text)
        if bet <= 0:
            await message.answer("❌ Ставка > 0.")
            return
        balance, _, _, _, _ = get_user(uid, message.from_user.username)
        if balance < bet:
            await message.answer(f"❌ Не хватает. У тебя {balance}, нужно {bet}.")
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


@dp.message(Command("balance"))
async def balance_cmd(message: types.Message):
    balance, _, _, _, hw = get_user(message.from_user.id, message.from_user.username)
    await message.answer(f"💰 Обычных: {balance}\n🍬 Конфет: {hw}")


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
        balance, _, level, reg, _ = get_user(tid, tun)
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
        await message.answer(caption + f"\n\n_Ошибка: {e}_", parse_mode="Markdown")


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
    cur.execute("SELECT rowid FROM inventory WHERE user_id = ? AND card_name = ? LIMIT 1", (uid, name))
    row = cur.fetchone()
    if not row:
        await message.answer("❌ Нет такой карточки.")
        return
    hw_card = find_hw_card(name)
    card_data = next((c for c in cards if c["name"].lower() == name.lower()), None)
    if hw_card:
        cur.execute("DELETE FROM inventory WHERE rowid = ?", (row[0],))
        cur.execute("UPDATE users SET hw_balance = hw_balance + ? WHERE user_id = ?", (hw_card["price"], uid))
        db.commit()
        await message.answer(f"✅ Продано: {hw_card['name']} за {hw_card['price']} 🍬")
        return
    if not card_data:
        await message.answer("❌ Неизвестная.")
        return
    cur.execute("DELETE FROM inventory WHERE rowid = ?", (row[0],))
    cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (card_data["price"], uid))
    db.commit()
    await message.answer(f"✅ Продано: {card_data['name']} за {card_data['price']} монет")


@dp.message(Command("sellall"))
async def sellall(message: types.Message):
    uid = message.from_user.id
    cur.execute("SELECT card_name, COUNT(*) FROM inventory WHERE user_id = ? GROUP BY card_name", (uid,))
    rows = cur.fetchall()
    if not rows:
        await message.answer("❌ Нет карточек.")
        return
    total_sum = 0
    text = "💰 *Будет продано:*\n\n"
    for name, cnt in rows:
        cd = next((c for c in cards if c["name"] == name), None)
        if not cd:
            continue
        subtotal = cd["price"] * cnt
        total_sum += subtotal
        text += f"• {name} × {cnt} = {subtotal} монет\n"
    text += f"\n💵 *Итого: {total_sum} монет*\n\n_Хеллоуинские карточки не продаются через /sellall — используй /sell Название._"
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Да", callback_data="sellall_yes"),
        InlineKeyboardButton(text="❌ Нет", callback_data="sellall_no"),
    ]])
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")


@dp.callback_query(F.data.startswith("sellall_"))
async def sellall_cb(call: types.CallbackQuery):
    uid = call.from_user.id
    if call.data == "sellall_no":
        await call.message.edit_text("❌ Отменено.")
        await call.answer()
        return
    cur.execute("SELECT card_name, COUNT(*) FROM inventory WHERE user_id = ? GROUP BY card_name", (uid,))
    rows = cur.fetchall()
    if not rows:
        await call.answer("Пусто!", show_alert=True)
        return
    total_sum = 0
    for name, cnt in rows:
        cd = next((c for c in cards if c["name"] == name), None)
        if not cd:
            continue
        total_sum += cd["price"] * cnt
        cur.execute("DELETE FROM inventory WHERE user_id = ? AND card_name = ?", (uid, name))
    cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (total_sum, uid))
    db.commit()
    await call.message.edit_text(f"✅ Продано за {total_sum} монет.")
    await call.answer("Готово!")


@dp.message(Command("upgrade"))
async def upgrade(message: types.Message):
    uid = message.from_user.id
    balance, _, level, _, _ = get_user(uid, message.from_user.username)
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
    balance, _, level, _, _ = get_user(uid, call.from_user.username)
    if call.data == "upg_no":
        await call.message.edit_text("❌ Отменено.")
        await call.answer()
        return
    nl = int(call.data.split("_")[2])
    price = UPGRADE_PRICES[nl]
    if level >= nl:
        await call.answer("Уже куплено!", show_alert=True)
        return
    if balance < price:
        await call.answer("Недостаточно монет!", show_alert=True)
        return
    cur.execute("UPDATE users SET balance = balance - ?, level = ? WHERE user_id = ?", (price, nl, uid))
    db.commit()
    await call.message.edit_text(f"✅ Улучшение! Теперь уровень {nl}.")
    await call.answer("Активировано!")


@dp.message(Command("trade"))
async def trade(message: types.Message):
    uid = message.from_user.id
    sn = message.from_user.username or message.from_user.full_name
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("Использование: /trade @username Название")
        return
    tu = args[1].lstrip("@")
    cn = args[2].strip()
    cur.execute("SELECT user_id, username FROM users WHERE username = ?", (tu,))
    row = cur.fetchone()
    if not row:
        await message.answer("❌ Не найден.")
        return
    tid, tun = row
    if tid == uid:
        await message.answer("❌ Себе нельзя.")
        return
    cur.execute("SELECT rowid FROM inventory WHERE user_id = ? AND card_name = ? LIMIT 1", (uid, cn))
    if not cur.fetchone():
        await message.answer(f"❌ Нет карточки «{cn}».")
        return
    cur.execute("INSERT INTO trades (from_id, to_id, card_name) VALUES (?, ?, ?)", (uid, tid, cn))
    db.commit()
    await message.answer(f"✅ Отправлено @{tun}.")
    try:
        await bot.send_message(tid, f"🤝 *Трейд!*\n\n👤 От: @{sn}\n🎴 *{cn}*\n\n/accept — принять\n/decline — отклонить", parse_mode="Markdown")
    except Exception:
        pass


@dp.message(Command("accept"))
async def accept(message: types.Message):
    uid = message.from_user.id
    an = message.from_user.username or message.from_user.full_name
    cur.execute("SELECT rowid, from_id, card_name FROM trades WHERE to_id = ? ORDER BY rowid DESC LIMIT 1", (uid,))
    row = cur.fetchone()
    if not row:
        await message.answer("❌ Нет предложений.")
        return
    rowid, fid, cn = row
    cur.execute("SELECT rowid FROM inventory WHERE user_id = ? AND card_name = ? LIMIT 1", (fid, cn))
    src = cur.fetchone()
    if not src:
        cur.execute("DELETE FROM trades WHERE rowid = ?", (rowid,))
        db.commit()
        await message.answer("❌ У отправителя нет карточки.")
        return
    cur.execute("DELETE FROM inventory WHERE rowid = ?", (src[0],))
    cur.execute("INSERT INTO inventory (user_id, card_name) VALUES (?, ?)", (uid, cn))
    cur.execute("DELETE FROM trades WHERE rowid = ?", (rowid,))
    db.commit()
    await message.answer(f"✅ Принял *{cn}*.", parse_mode="Markdown")
    try:
        await bot.send_message(fid, f"✅ *Трейд принят!*\n\n👤 @{an} принял *{cn}*.", parse_mode="Markdown")
    except Exception:
        pass


@dp.message(Command("decline"))
async def decline(message: types.Message):
    uid = message.from_user.id
    dn = message.from_user.username or message.from_user.full_name
    cur.execute("SELECT rowid, from_id, card_name FROM trades WHERE to_id = ? ORDER BY rowid DESC LIMIT 1", (uid,))
    row = cur.fetchone()
    if not row:
        await message.answer("❌ Нет предложений.")
        return
    rowid, fid, cn = row
    cur.execute("DELETE FROM trades WHERE rowid = ?", (rowid,))
    db.commit()
    await message.answer(f"❌ Отклонил *{cn}*.", parse_mode="Markdown")
    try:
        await bot.send_message(fid, f"❌ *Трейд отклонён.*\n\n👤 @{dn} отказался от *{cn}*.", parse_mode="Markdown")
    except Exception:
        pass


async def main():
    await dp.start_polling(bot)


asyncio.run(main())
