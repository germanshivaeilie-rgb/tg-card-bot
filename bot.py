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

# ==== РђР”РњРРќ ====
ADMIN_IDS = {0}                 # РІРїРёС€Рё СЃСЋРґР° СЃРІРѕР№ Telegram ID (СѓР·РЅР°С‚СЊ Сѓ @userinfobot)
ADMIN_USERNAMES = {"xleb050"}   # Р·Р°РїР°СЃРЅРѕР№ РІР°СЂРёР°РЅС‚, РІ РЅРёР¶РЅРµРј СЂРµРіРёСЃС‚СЂРµ


def is_admin(user: types.User) -> bool:
    return user.id in ADMIN_IDS or (user.username or "").lower() in ADMIN_USERNAMES


FONT_PATH = "Roboto-Italic-VariableFont_wdth,wght.ttf"
BG_PATH = "ChatGPT Image 5 РѕРєС‚. 2026 Рі., 09_26_45.png"
BOSS_ALIVE = "ChatGPT Image 6 РѕРєС‚. 2026 Рі., 12_17_38.png"
BOSS_DEAD = "ChatGPT Image 6 РѕРєС‚. 2026 Рі., 12_19_03.png"
HW_BANNER = "ChatGPT Image 6 РѕРєС‚. 2026 Рі., 11_12_35.png"

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

RARITY_CHANCES = {
    "вљЄ РћР±С‹С‡РЅР°СЏ":      55,
    "рџ”· Р РµРґРєР°СЏ":       18,
    "рџ”® Р­РїРёС‡РµСЃРєР°СЏ":    10,
    "рџ‘‘ Р›РµРіРµРЅРґР°СЂРЅР°СЏ":  6,
    "в™ЈпёЏ РЎРµРєСЂРµС‚РЅР°СЏ":    3,
    "рџЊЊ Р‘РµСЃРєРѕРЅРµС‡РЅР°СЏ":  2,
}

cards = [
    {"name": "Р—Р°СЃРѕС…С€Р°СЏ Р»РёР»РёСЏ",          "rarity": "вљЄ РћР±С‹С‡РЅР°СЏ",     "price": 100,    "file": "Р—Р°СЃРѕС…С€Р°СЏ Р»РёР»РёСЏ РЅР° С‡С‘СЂРЅРѕРј С„РѕРЅРµ (1).png"},
    {"name": "РЁРѕРєРѕР»Р°РґРЅС‹Р№ РіР»Р°Р· СЂСѓР±СЂРёРєР°", "rarity": "вљЄ РћР±С‹С‡РЅР°СЏ",     "price": 150,    "file": "IMG_20261004_163909_865.jpg"},
    {"name": "РџРѕРµРґР°С‚РµР»СЊ С‡РёР¶РёРєР°",        "rarity": "рџ”· Р РµРґРєР°СЏ",      "price": 500,    "file": "IMG_20261004_205356_295.jpg"},
    {"name": "Р¤РѕРЅРє",                    "rarity": "рџ”· Р РµРґРєР°СЏ",      "price": 400,    "file": "ChatGPT Image 4 РѕРєС‚. 2026 Рі., 15_45_06.png"},
    {"name": "Р›РµСЂР°",                    "rarity": "рџ”· Р РµРґРєР°СЏ",      "price": 750,    "file": "IMG_20261005_193418_201.jpg"},
    {"name": "Р“СЂСѓСЃС‚РЅС‹Р№ С…Р»РµР±",           "rarity": "рџ”® Р­РїРёС‡РµСЃРєР°СЏ",   "price": 1000,   "file": "ChatGPT Image 22 СЃРµРЅС‚. 2026 Рі., 22_04_28.png"},
    {"name": "Р›СЏС€РєРё Р°СЃРµРєРё",             "rarity": "рџ”® Р­РїРёС‡РµСЃРєР°СЏ",   "price": 800,    "file": "IMG_20261005_143214_562.jpg"},
    {"name": "Р—РµР»С‘РЅР°СЏ С€Р»СЋС€РєР°",          "rarity": "рџ”® Р­РїРёС‡РµСЃРєР°СЏ",   "price": 1500,   "file": "IMG_20261005_152528_718.jpg"},
    {"name": "РўСЂСѓ РђРґР°РјСЃ",               "rarity": "рџ‘‘ Р›РµРіРµРЅРґР°СЂРЅР°СЏ", "price": 5000,   "file": "ChatGPT Image 3 РѕРєС‚. 2026 Рі., 20_39_20.png"},
    {"name": "Р”Р°РІР°Р»РєР°",                 "rarity": "рџ‘‘ Р›РµРіРµРЅРґР°СЂРЅР°СЏ", "price": 10000,  "file": "IMG_20261004_211521_420.jpg"},
    {"name": "MoggС„РѕРЅ",                 "rarity": "в™ЈпёЏ РЎРµРєСЂРµС‚РЅР°СЏ",   "price": 50000,  "file": "IMG_20261004_211400_997.jpg"},
    {"name": "РўРѕРї 1 РњРёРЅС‘СЂ",             "rarity": "рџ’  РЎРїРµС†РёР°Р»СЊРЅР°СЏ", "price": 50000,  "file": "Picsart_26-10-05_23-53-56-160.jpg"},
    {"name": "Р›СѓС‡С€РёР№ РР·СЂР°РµР»СЊ Р№РµРіСѓРґР°",   "rarity": "рџЊЊ Р‘РµСЃРєРѕРЅРµС‡РЅР°СЏ", "price": 500000, "file": "ChatGPT Image 5 РѕРєС‚. 2026 Рі., 15_32_46.png"},
    {"name": "РҐРµР»Р»РѕСѓРёРЅСЃРєРёР№ Р±РѕСЃСЃ",       "rarity": "рџ’  РЎРїРµС†РёР°Р»СЊРЅР°СЏ", "price": 100000, "file": "ChatGPT Image 6 РѕРєС‚. 2026 Рі., 12_19_03.png"},
]

HW_CARDS = {
    "pumpkin": {
        "рџЋѓ РўС‹РєРІРµРЅРЅР°СЏ": [
            {"name": "РћРіРЅРµРЅРЅР°СЏ Р›РµСЂР°",   "price": 250,  "file": "ChatGPT Image 6 РѕРєС‚. 2026 Рі., 11_30_41.png"},
            {"name": "РџРѕР¶РёСЂР°С‚РµР»СЊ С‚С‹РєРІ", "price": 500,  "file": "ChatGPT Image 6 РѕРєС‚. 2026 Рі., 11_26_06.png"},
            {"name": "РќРѕСЂР° СЃ С‚С‹РєРІР°РјРё",  "price": 1000, "file": "ChatGPT Image 6 РѕРєС‚. 2026 Рі., 11_19_50.png"},
        ],
        "рџ‘» РџСЂРёР·СЂР°С‡РЅР°СЏ": [
            {"name": "РџСЂРёР·СЂР°С‡РЅС‹Р№ СЂСѓР±СЂРёРє", "price": 1500, "file": "ChatGPT Image 6 РѕРєС‚. 2026 Рі., 11_23_00.png"},
        ],
        "рџ§™ Р’РµРґСЊРјРёРЅСЃРєР°СЏ": [
            {"name": "Р’РµРґСЊРјРёРЅСЃРєРёР№ Р•Р»СЏ", "price": 10000, "file": "ChatGPT Image 6 РѕРєС‚. 2026 Рі., 11_16_21.png"},
        ],
        "рџ§› Р’Р°РјРїРёСЂСЃРєР°СЏ": [
            {"name": "Р’Р°РјРїРёСЂСЃРєРёР№ С…Р»РµР±", "price": 20000, "file": "ChatGPT Image 6 РѕРєС‚. 2026 Рі., 10_48_44.png"},
        ],
    },
    "skeleton": {
        "рџ‘» РџСЂРёР·СЂР°С‡РЅР°СЏ": [
            {"name": "РџСЂРёР·СЂР°С‡РЅС‹Р№ СЂСѓР±СЂРёРє", "price": 1500, "file": "ChatGPT Image 6 РѕРєС‚. 2026 Рі., 11_23_00.png"},
            {"name": "РљРѕС‚Р°РєР±Р°СЃ",          "price": 3000, "file": "ChatGPT Image 6 РѕРєС‚. 2026 Рі., 14_07_30.png"},
            {"name": "РџСЂРёР·СЂР°Рє Р·Р°РµР·",      "price": 5000, "file": "ChatGPT Image 6 РѕРєС‚. 2026 Рі., 14_10_39.png"},
        ],
        "рџ§™ Р’РµРґСЊРјРёРЅСЃРєР°СЏ": [
            {"name": "Р’РµРґСЊРјРёРЅСЃРєРёР№ Р•Р»СЏ",   "price": 10000, "file": "ChatGPT Image 6 РѕРєС‚. 2026 Рі., 11_16_21.png"},
            {"name": "Р’РµРґСЊРјРёРЅСЃРєР°СЏ РєРѕС€РєР°", "price": 15000, "file": "ChatGPT Image 6 РѕРєС‚. 2026 Рі., 14_03_47.png"},
            {"name": "Р’РµРґСЊРјР° РЅРµР»СЏ",       "price": 17000, "file": "ChatGPT Image 6 РѕРєС‚. 2026 Рі., 14_23_18.png"},
        ],
        "рџ§› Р’Р°РјРїРёСЂСЃРєР°СЏ": [
            {"name": "Р’Р°РјРїРёСЂСЃРєРёР№ С…Р»РµР±",                 "price": 20000, "file": "ChatGPT Image 6 РѕРєС‚. 2026 Рі., 10_48_44.png"},
            {"name": "Рђ С…РѕС‚РµР»РѕСЃСЊ Р±С‹ РІРµРґСЊРјРёРЅСЃРєРёР№ Р¶РµР·Р»",  "price": 25000, "file": "ChatGPT Image 6 РѕРєС‚. 2026 Рі., 14_28_54.png"},
        ],
        "рџ’Ђ РЎРєРµР»РµС‚РЅР°СЏ": [
            {"name": "РљРѕСЃС‚СЏРЅРѕР№ Р“СѓР±РєР° Р±РѕР±",       "price": 30000, "file": "ChatGPT Image 6 РѕРєС‚. 2026 Рі., 14_36_53.png"},
            {"name": "РљРѕСЃС‚СЏРЅРѕР№ Р›РёС‚РІРёРЅ x РЎРїРёРґ",   "price": 40000, "file": "ChatGPT Image 6 РѕРєС‚. 2026 Рі., 14_42_20.png"},
        ],
        "рџ€ Р”РµРјРѕРЅРёС‡РµСЃРєР°СЏ": [
            {"name": "РљРѕР»Р»РµРєС†РёРѕРЅРµСЂ РґСѓС€", "price": 100000, "file": "ChatGPT Image 6 РѕРєС‚. 2026 Рі., 14_45_53.png"},
        ],
    },
    "ghost": {
        "рџ§™ Р’РµРґСЊРјРёРЅСЃРєР°СЏ": [
            {"name": "Р’РµРґСЊРјРёРЅСЃРєРёР№ Р•Р»СЏ",   "price": 10000, "file": "ChatGPT Image 6 РѕРєС‚. 2026 Рі., 11_16_21.png"},
            {"name": "Р’РµРґСЊРјРёРЅСЃРєР°СЏ РєРѕС€РєР°", "price": 15000, "file": "ChatGPT Image 6 РѕРєС‚. 2026 Рі., 14_03_47.png"},
            {"name": "Р’РµРґСЊРјР° РЅРµР»СЏ",       "price": 17000, "file": "ChatGPT Image 6 РѕРєС‚. 2026 Рі., 14_23_18.png"},
        ],
        "рџ§› Р’Р°РјРїРёСЂСЃРєР°СЏ": [
            {"name": "Р’Р°РјРїРёСЂСЃРєРёР№ С…Р»РµР±",                 "price": 20000, "file": "ChatGPT Image 6 РѕРєС‚. 2026 Рі., 10_48_44.png"},
            {"name": "Рђ С…РѕС‚РµР»РѕСЃСЊ Р±С‹ РІРµРґСЊРјРёРЅСЃРєРёР№ Р¶РµР·Р»",  "price": 25000, "file": "ChatGPT Image 6 РѕРєС‚. 2026 Рі., 14_28_54.png"},
        ],
        "рџ’Ђ РЎРєРµР»РµС‚РЅР°СЏ": [
            {"name": "РљРѕСЃС‚СЏРЅРѕР№ Р“СѓР±РєР° Р±РѕР±",       "price": 30000, "file": "ChatGPT Image 6 РѕРєС‚. 2026 Рі., 14_36_53.png"},
            {"name": "РљРѕСЃС‚СЏРЅРѕР№ Р›РёС‚РІРёРЅ x РЎРїРёРґ",   "price": 40000, "file": "ChatGPT Image 6 РѕРєС‚. 2026 Рі., 14_42_20.png"},
        ],
        "рџ€ Р”РµРјРѕРЅРёС‡РµСЃРєР°СЏ": [
            {"name": "РљРѕР»Р»РµРєС†РёРѕРЅРµСЂ РґСѓС€", "price": 100000, "file": "ChatGPT Image 6 РѕРєС‚. 2026 Рі., 14_45_53.png"},
        ],
        "рџ± РљРѕС€РјР°СЂРЅР°СЏ": [
            {"name": "РљРѕС€РјР°СЂРЅС‹Р№ Moggfone", "price": 500000, "file": "ChatGPT Image 6 РѕРєС‚. 2026 Рі., 15_28_10.png"},
        ],
    },
}

CASE_CHANCES = {
    "pumpkin": {
        "рџЋѓ РўС‹РєРІРµРЅРЅР°СЏ": 70,
        "рџ‘» РџСЂРёР·СЂР°С‡РЅР°СЏ": 25,
        "рџ§™ Р’РµРґСЊРјРёРЅСЃРєР°СЏ": 4,
        "рџ§› Р’Р°РјРїРёСЂСЃРєР°СЏ": 1,
    },
    "skeleton": {
        "рџ‘» РџСЂРёР·СЂР°С‡РЅР°СЏ": 35,
        "рџ§™ Р’РµРґСЊРјРёРЅСЃРєР°СЏ": 25,
        "рџ§› Р’Р°РјРїРёСЂСЃРєР°СЏ": 20,
        "рџ’Ђ РЎРєРµР»РµС‚РЅР°СЏ": 15,
        "рџ€ Р”РµРјРѕРЅРёС‡РµСЃРєР°СЏ": 5,
    },
    "ghost": {
        "рџ§™ Р’РµРґСЊРјРёРЅСЃРєР°СЏ": 40,
        "рџ§› Р’Р°РјРїРёСЂСЃРєР°СЏ": 30,
        "рџ’Ђ РЎРєРµР»РµС‚РЅР°СЏ": 18,
        "рџ€ Р”РµРјРѕРЅРёС‡РµСЃРєР°СЏ": 11.334,
        "рџ± РљРѕС€РјР°СЂРЅР°СЏ": 0.666,
    },
}

CASE_PRICES = {
    "pumpkin": 1000,
    "skeleton": 10000,
    "ghost": 100000,
}

HALLOWEEN_RATE_TO = 10      # 1 рџЌ¬ = 10 РјРѕРЅРµС‚ (100 РјРѕРЅРµС‚ -> 10 рџЌ¬)
HALLOWEEN_RATE_BACK = 0.9   # РЅР°Р»РѕРі 10% РїСЂРё РѕР±СЂР°С‚РЅРѕРј РѕР±РјРµРЅРµ

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
    {"emoji": "рџ”µ", "name": "РЎРёРЅРёР№",       "code": "blue"},
    {"emoji": "рџ”ґ", "name": "РљСЂР°СЃРЅС‹Р№",     "code": "red"},
    {"emoji": "рџџЎ", "name": "Р–С‘Р»С‚С‹Р№",      "code": "yellow"},
    {"emoji": "рџџў", "name": "Р—РµР»С‘РЅС‹Р№",     "code": "green"},
    {"emoji": "рџџЈ", "name": "Р¤РёРѕР»РµС‚РѕРІС‹Р№",  "code": "purple"},
    {"emoji": "рџџ ", "name": "РћСЂР°РЅР¶РµРІС‹Р№",   "code": "orange"},
]

MINER_MULTIPLIERS = {
    1: 1.2, 2: 1.5, 3: 2.0, 4: 3.0,
    5: 5.0, 6: 8.0, 7: 15.0, 8: 30.0, 9: 100.0,
}

color_games = {}
miner_games = {}
hw_games = {}
coin_games = {}

COIN_SIDES = {"heads": "рџ¦… РћСЂС‘Р»", "tails": "рџЄ™ Р РµС€РєР°"}

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


def find_any_card(name):
    for c in cards:
        if c["name"].lower() == name.lower():
            return c
    return find_hw_card(name)


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
        return "РЅРµРёР·РІРµСЃС‚РЅРѕ"
    try:
        dt = datetime.fromisoformat(iso_str)
    except Exception:
        return "РЅРµРёР·РІРµСЃС‚РЅРѕ"
    months = ["СЏРЅРІР°СЂСЏ", "С„РµРІСЂР°Р»СЏ", "РјР°СЂС‚Р°", "Р°РїСЂРµР»СЏ", "РјР°СЏ", "РёСЋРЅСЏ",
              "РёСЋР»СЏ", "Р°РІРіСѓСЃС‚Р°", "СЃРµРЅС‚СЏР±СЂСЏ", "РѕРєС‚СЏР±СЂСЏ", "РЅРѕСЏР±СЂСЏ", "РґРµРєР°Р±СЂСЏ"]
    return f"{dt.day} {months[dt.month - 1]} {dt.year} РіРѕРґР°"


def format_cooldown(seconds_left):
    mins = seconds_left // 60
    secs = seconds_left % 60
    if mins > 0:
        return f"{mins} РјРёРЅ {secs} СЃРµРє"
    return f"{secs} СЃРµРє"


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
    draw.text((x, y), f"@{username or 'РРіСЂРѕРє'}", font=font_big, fill="white")
    draw.text((x, y + line), f"Р‘Р°Р»Р°РЅСЃ: {balance}", font=font_mid, fill="#FFD700")
    draw.text((x, y + line * 2), f"РЈСЂРѕРІРµРЅСЊ: {level}", font=font_mid, fill="#00E5FF")
    draw.text((x, y + line * 3), f"РљР°СЂС‚: {total_cards}", font=font_mid, fill="#CCCCCC")
    draw.text((x, y + line * 4), f"РњРµСЃС‚Рѕ: #{place}", font=font_mid, fill="#00FF99")
    output = io.BytesIO()
    bg.save(output, format="PNG")
    output.seek(0)
    return output


@dp.message(Command("start"))
async def start(message: types.Message):
    get_user(message.from_user.id, message.from_user.username)
    await message.answer(
        "рџЋґ РџСЂРёРІРµС‚! РЇ Р±РѕС‚-РєРѕР»Р»РµРєС†РёРѕРЅРµСЂ РєР°СЂС‚РѕС‡РµРє.\n\n"
        "/card вЂ” РІС‹Р±РёС‚СЊ РєР°СЂС‚РѕС‡РєСѓ\n"
        "/casino вЂ” рџЋ° Casino\n"
        "/halloween вЂ” рџЋѓ РҐРµР»Р»РѕСѓРёРЅ\n"
        "/mycards вЂ” РёРЅРІРµРЅС‚Р°СЂСЊ\n"
        "/balance вЂ” Р±Р°Р»Р°РЅСЃ\n"
        "/sell вЂ” РїСЂРѕРґР°С‚СЊ\n"
        "/sellall вЂ” РїСЂРѕРґР°С‚СЊ РІСЃС‘\n"
        "/upgrade вЂ” СѓР»СѓС‡С€РµРЅРёРµ\n"
        "/profile вЂ” РїСЂРѕС„РёР»СЊ\n"
        "/top вЂ” С‚РѕРї-3\n"
        "/trade @username РќР°Р·РІР°РЅРёРµ вЂ” С‚СЂРµР№Рґ\n"
        "/accept, /decline вЂ” С‚СЂРµР№Рґ"
    )


@dp.message(Command("card"))
async def card(message: types.Message):
    uid = message.from_user.id
    username = message.from_user.username or "РРіСЂРѕРє"
    balance, last, level, _, _ = get_user(uid, message.from_user.username)
    if last:
        last_dt = datetime.fromisoformat(last)
        elapsed = datetime.now() - last_dt
        if elapsed < timedelta(minutes=COOLDOWN_MINUTES):
            left = timedelta(minutes=COOLDOWN_MINUTES) - elapsed
            await message.answer(f"@{username}, С‚С‹ СѓР¶Рµ РєСЂСѓС‚РёР», РѕС‚РєСЂРѕР№ РїРѕР·Р¶Рµ.\nвЏі Р–РґР°С‚СЊ РµС‰С‘: {format_cooldown(int(left.total_seconds()))}")
            return
    cur.execute("UPDATE users SET last_card = ? WHERE user_id = ?", (datetime.now().isoformat(), uid))
    db.commit()
    for _ in range(level):
        c = roll_card()
        cur.execute("INSERT INTO inventory (user_id, card_name) VALUES (?, ?)", (uid, c["name"]))
        db.commit()
        cur.execute("SELECT rowid FROM inventory WHERE user_id = ? AND card_name = ? ORDER BY rowid DESC LIMIT 1", (uid, c["name"]))
        inv_id = cur.fetchone()[0]
        caption = f"@{username}, РІР°Рј РІС‹РїР°Р»Р°:\nрџЋґ {c['name']}\n{c['rarity']} | рџ’° Р¦РµРЅР°: {c['price']} РјРѕРЅРµС‚"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"рџ’° РџСЂРѕРґР°С‚СЊ: {c['name']} ({c['price']})", callback_data=f"sell_card_{inv_id}_{c['price']}")],
            [InlineKeyboardButton(text="рџЋ° Casino", callback_data=f"open_casino_{uid}")],
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
        await call.answer("вќЊ РЈР¶Рµ РїСЂРѕРґР°РЅР°.", show_alert=True)
        return
    cur.execute("DELETE FROM inventory WHERE rowid = ?", (inv_id,))
    cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (price, uid))
    db.commit()
    await call.message.edit_caption(caption=f"вњ… РџСЂРѕРґР°РЅРѕ: {row[0]} Р·Р° {price} РјРѕРЅРµС‚", reply_markup=None)
    await call.answer(f"РџРѕР»СѓС‡РµРЅРѕ {price} РјРѕРЅРµС‚!")


def casino_kb(uid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="рџЋІ Color Dice", callback_data=f"casino_color_{uid}")],
        [InlineKeyboardButton(text="рџ’Ј РњРёРЅС‘СЂ", callback_data=f"casino_miner_{uid}")],
        [InlineKeyboardButton(text="рџЄ™ РћСЂС‘Р» Рё СЂРµС€РєР°", callback_data=f"casino_coin_{uid}")],
        [InlineKeyboardButton(text="рџ”™ Р—Р°РєСЂС‹С‚СЊ", callback_data=f"casino_close_{uid}")],
    ])


@dp.message(Command("casino"))
async def casino_command(message: types.Message):
    uid = message.from_user.id
    username = message.from_user.username or message.from_user.full_name or "РРіСЂРѕРє"
    kb = casino_kb(uid)
    await message.answer(f"рџЋ° *Casino* вЂ” @{username}\n\nР’С‹Р±РµСЂРё РёРіСЂСѓ:", reply_markup=kb, parse_mode="Markdown")


@dp.callback_query(F.data.startswith("open_casino_"))
async def open_casino(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Р­С‚Рѕ РЅРµ С‚РІРѕС‘ РјРµРЅСЋ!", show_alert=True)
        return
    username = call.from_user.username or call.from_user.full_name or "РРіСЂРѕРє"
    kb = casino_kb(uid)
    await call.message.answer(f"рџЋ° *Casino* вЂ” @{username}\n\nР’С‹Р±РµСЂРё РёРіСЂСѓ:", reply_markup=kb, parse_mode="Markdown")
    await call.answer()


@dp.callback_query(F.data.startswith("casino_close_"))
async def casino_close(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("РќРµ С‚РІРѕС‘ РјРµРЅСЋ!", show_alert=True)
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
        await call.answer("РќРµ С‚РІРѕС‘ РјРµРЅСЋ!", show_alert=True)
        return
    username = call.from_user.username or call.from_user.full_name or "РРіСЂРѕРє"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="рџ”µ РЎРёРЅРёР№", callback_data=f"col_blue_{uid}"), InlineKeyboardButton(text="рџ”ґ РљСЂР°СЃРЅС‹Р№", callback_data=f"col_red_{uid}")],
        [InlineKeyboardButton(text="рџџЎ Р–С‘Р»С‚С‹Р№", callback_data=f"col_yellow_{uid}"), InlineKeyboardButton(text="рџџў Р—РµР»С‘РЅС‹Р№", callback_data=f"col_green_{uid}")],
        [InlineKeyboardButton(text="рџџЈ Р¤РёРѕР»РµС‚РѕРІС‹Р№", callback_data=f"col_purple_{uid}"), InlineKeyboardButton(text="рџџ  РћСЂР°РЅР¶РµРІС‹Р№", callback_data=f"col_orange_{uid}")],
    ])
    await call.message.edit_text(
        f"рџЋІ *Color Dice* вЂ” @{username}\n\nРџСЂР°РІРёР»Р°:\nрџЋ‰ 1 СЃРѕРІРїР°РґРµРЅРёРµ в†’ Г—2\nрџЋ‰ 4 СЃРѕРІРїР°РґРµРЅРёСЏ в†’ Г—4\nвќЊ 0, 2, 3 в†’ РїСЂРѕРёРіСЂС‹С€\n\nР’С‹Р±РµСЂРё С†РІРµС‚:",
        reply_markup=kb, parse_mode="Markdown"
    )
    await call.answer()


@dp.callback_query(F.data.startswith("col_"))
async def color_chosen(call: types.CallbackQuery):
    parts = call.data.split("_")
    if len(parts) < 3:
        await call.answer("РћС€РёР±РєР°", show_alert=True)
        return
    code = parts[1]
    uid = int(parts[2])
    if call.from_user.id != uid:
        await call.answer("РќРµ С‚РІРѕСЏ РёРіСЂР°!", show_alert=True)
        return
    chosen = next((c for c in COLORS if c["code"] == code), None)
    if not chosen:
        await call.answer("РћС€РёР±РєР° С†РІРµС‚Р°", show_alert=True)
        return
    color_games[uid] = {"color": chosen, "state": "wait_bet"}
    await call.message.edit_text(
        f"рџЋІ РўРІРѕР№ С†РІРµС‚: {chosen['emoji']} {chosen['name']}\n\nрџ’° РќР°РїРёС€Рё СЃСѓРјРјСѓ СЃС‚Р°РІРєРё С‡РёСЃР»РѕРј (РЅР°РїСЂРёРјРµСЂ 100).\nРћС‚РјРµРЅР° вЂ” /cancel"
    )
    await call.answer()


# ==== РћР РЃР› Р Р Р•РЁРљРђ ====
@dp.callback_query(F.data.startswith("casino_coin_"))
async def casino_coin(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("РќРµ С‚РІРѕС‘ РјРµРЅСЋ!", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="рџ¦… РћСЂС‘Р»", callback_data=f"coinside_heads_{uid}"),
         InlineKeyboardButton(text="рџЄ™ Р РµС€РєР°", callback_data=f"coinside_tails_{uid}")],
        [InlineKeyboardButton(text="рџ”™ РќР°Р·Р°Рґ", callback_data=f"casino_back_{uid}")],
    ])
    await call.message.edit_text(
        "рџЄ™ *РћСЂС‘Р» Рё СЂРµС€РєР°*\n\nРЈРіР°РґР°Р» вЂ” Г—2, РЅРµ СѓРіР°РґР°Р» вЂ” С‚РµСЂСЏРµС€СЊ СЃС‚Р°РІРєСѓ.\n\nР’С‹Р±РµСЂРё СЃС‚РѕСЂРѕРЅСѓ:",
        reply_markup=kb, parse_mode="Markdown"
    )
    await call.answer()


@dp.callback_query(F.data.startswith("coinside_"))
async def coin_side_chosen(call: types.CallbackQuery):
    parts = call.data.split("_")
    side = parts[1]
    uid = int(parts[2])
    if call.from_user.id != uid:
        await call.answer("РќРµ С‚РІРѕСЏ РёРіСЂР°!", show_alert=True)
        return
    if side not in COIN_SIDES:
        await call.answer("РћС€РёР±РєР°", show_alert=True)
        return
    coin_games[uid] = {"side": side, "state": "wait_bet"}
    await call.message.edit_text(
        f"рџЄ™ РўРІРѕСЏ СЃС‚РѕСЂРѕРЅР°: {COIN_SIDES[side]}\n\nрџ’° РќР°РїРёС€Рё СЃСѓРјРјСѓ СЃС‚Р°РІРєРё С‡РёСЃР»РѕРј (РЅР°РїСЂРёРјРµСЂ 100).\nРћС‚РјРµРЅР° вЂ” /cancel"
    )
    await call.answer()


@dp.callback_query(F.data.startswith("casino_miner_"))
async def casino_miner(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("РќРµ С‚РІРѕС‘ РјРµРЅСЋ!", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="рџ’° РЎРґРµР»Р°С‚СЊ СЃС‚Р°РІРєСѓ", callback_data=f"miner_bet_{uid}")],
        [InlineKeyboardButton(text="рџ”™ РќР°Р·Р°Рґ", callback_data=f"casino_back_{uid}")],
    ])
    await call.message.edit_text(
        "рџ’Ј *РњРёРЅС‘СЂ*\n\nрџ“‹ *РџСЂР°РІРёР»Р°:*\nвЂў 9 РєР»РµС‚РѕРє\nвЂў РЎРїСЂСЏС‚Р°РЅРѕ 2-6 РјРёРЅ\nвЂў РћС‚РєСЂС‹РІР°Р№ РєР»РµС‚РєРё\nвЂў РџРѕРїР°РґС‘С€СЊ вЂ” С‚РµСЂСЏРµС€СЊ СЃС‚Р°РІРєСѓ\nвЂў РћС‚РєСЂС‹Р» РІСЃРµ Р±РµР·РѕРїР°СЃРЅС‹Рµ вЂ” РІС‹РёРіСЂС‹С€\n\n"
        "рџ“€ *РњРЅРѕР¶РёС‚РµР»Рё:*\n1 в†’ Г—1.2\n2 в†’ Г—1.5\n3 в†’ Г—2\n4 в†’ Г—3\n5 в†’ Г—5\n6 в†’ Г—8\n7 в†’ Г—15\n8 в†’ Г—30\n\n"
        "рџЋЃ РћС‚РєСЂС‹Р» РІСЃРµ Р±РµР·РѕРїР°СЃРЅС‹Рµ РїСЂРё 3+ РјРёРЅР°С… вЂ” РєР°СЂС‚РѕС‡РєР° В«РўРѕРї 1 РњРёРЅС‘СЂВ» (рџ’ )!",
        reply_markup=kb, parse_mode="Markdown"
    )
    await call.answer()


@dp.callback_query(F.data.startswith("casino_back_"))
async def casino_back(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("РќРµ С‚РІРѕС‘ РјРµРЅСЋ!", show_alert=True)
        return
    username = call.from_user.username or call.from_user.full_name or "РРіСЂРѕРє"
    kb = casino_kb(uid)
    await call.message.edit_text(f"рџЋ° *Casino* вЂ” @{username}\n\nР’С‹Р±РµСЂРё РёРіСЂСѓ:", reply_markup=kb, parse_mode="Markdown")
    await call.answer()


@dp.callback_query(F.data.startswith("miner_bet_"))
async def miner_bet_request(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("РќРµ С‚РІРѕС‘ РјРµРЅСЋ!", show_alert=True)
        return
    miner_games[uid] = {"state": "wait_bet"}
    await call.message.edit_text(
        "рџ’Ј *РњРёРЅС‘СЂ*\n\nрџ’° РќР°РїРёС€Рё СЃСѓРјРјСѓ СЃС‚Р°РІРєРё С‡РёСЃР»РѕРј (РЅР°РїСЂРёРјРµСЂ 100).\nРћС‚РјРµРЅР° вЂ” /cancel",
        parse_mode="Markdown"
    )
    await call.answer()


def render_miner_field(opened, mines_set, reveal_all=False):
    row = []
    for i in range(9):
        if i in opened:
            row.append("рџџў")
        elif reveal_all and i in mines_set:
            row.append("рџ’Ј")
        else:
            row.append("рџџ¦")
    return row


def miner_keyboard(opened, mines_set, uid):
    buttons = []
    row1 = []
    for i in range(9):
        if i in opened:
            row1.append(InlineKeyboardButton(text="рџџў", callback_data=f"miner_noop_{i}_{uid}"))
        else:
            row1.append(InlineKeyboardButton(text="рџџ¦", callback_data=f"miner_open_{i}_{uid}"))
    buttons.append(row1)
    buttons.append([InlineKeyboardButton(text="рџ’° Р—Р°Р±СЂР°С‚СЊ", callback_data=f"miner_cashout_{uid}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@dp.callback_query(F.data.startswith("miner_noop_"))
async def miner_noop(call: types.CallbackQuery):
    parts = call.data.split("_")
    uid = int(parts[3])
    if call.from_user.id != uid:
        await call.answer("РќРµ С‚РІРѕСЏ РёРіСЂР°!", show_alert=True)
        return
    await call.answer("РЈР¶Рµ РѕС‚РєСЂС‹С‚Рѕ.")


@dp.callback_query(F.data.startswith("miner_open_"))
async def miner_open(call: types.CallbackQuery):
    parts = call.data.split("_")
    idx = int(parts[2])
    uid = int(parts[3])
    if call.from_user.id != uid:
        await call.answer("РќРµ С‚РІРѕСЏ РёРіСЂР°!", show_alert=True)
        return
    username = call.from_user.username or call.from_user.full_name or "РРіСЂРѕРє"
    game = miner_games.get(uid)
    if not game or game.get("state") != "playing":
        await call.answer("РРіСЂР° РЅРµ Р°РєС‚РёРІРЅР°.", show_alert=True)
        return
    if idx in game["opened"]:
        await call.answer("РЈР¶Рµ РѕС‚РєСЂС‹С‚Рѕ.")
        return
    if idx in game["mines"]:
        game["state"] = "finished"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="рџЋ° РРіСЂР°С‚СЊ СЃРЅРѕРІР°", callback_data=f"casino_miner_{uid}")],
            [InlineKeyboardButton(text="рџ”™ Casino", callback_data=f"open_casino_{uid}")],
        ])
        await call.message.edit_text(
            f"рџ’Ј *РњРёРЅС‘СЂ* вЂ” @{username}\n\nрџ’° РЎС‚Р°РІРєР°: {game['bet']}\nрџ’Ґ РџРѕРїР°Р» РЅР° РјРёРЅСѓ!\n\n"
            f"{' '.join(render_miner_field(game['opened'], game['mines'], reveal_all=True))}\n\n"
            f"вќЊ *РџСЂРѕРёРіСЂР°Р» {game['bet']} РјРѕРЅРµС‚.*",
            reply_markup=kb, parse_mode="Markdown"
        )
        del miner_games[uid]
        await call.answer("рџ’Ґ Р‘СѓРј!")
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
            cur.execute("INSERT INTO inventory (user_id, card_name) VALUES (?, ?)", (uid, "РўРѕРї 1 РњРёРЅС‘СЂ"))
            special_card = True
        db.commit()
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="рџЋ° РРіСЂР°С‚СЊ СЃРЅРѕРІР°", callback_data=f"casino_miner_{uid}")],
            [InlineKeyboardButton(text="рџ”™ Casino", callback_data=f"open_casino_{uid}")],
        ])
        text = (
            f"рџ’Ј *РњРёРЅС‘СЂ* вЂ” @{username}\n\nрџ’° РЎС‚Р°РІРєР°: {game['bet']}\nрџЋ‰ Р’СЃРµ Р±РµР·РѕРїР°СЃРЅС‹Рµ РѕС‚РєСЂС‹С‚С‹!\nрџ“€ РњРЅРѕР¶РёС‚РµР»СЊ: Г—{multiplier}\n\n"
            f"{' '.join(render_miner_field(game['opened'], game['mines'], reveal_all=True))}\n\nрџ’° *Р’С‹РёРіСЂС‹С€: {win} РјРѕРЅРµС‚!*"
        )
        if special_card:
            text += "\n\nрџ’  *Р’Р«РџРђР›Рђ РљРђР РўРћР§РљРђ В«РўРѕРї 1 РњРёРЅС‘СЂВ»!*"
        await call.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        if special_card:
            try:
                cd = next((c for c in cards if c["name"] == "РўРѕРї 1 РњРёРЅС‘СЂ"), None)
                if cd:
                    photo = FSInputFile(cd["file"])
                    await call.message.answer_photo(photo, caption=f"рџЋЃ *РќР°РіСЂР°РґР°!*\n\nрџЋґ {cd['name']}\n{cd['rarity']} | рџ’° {cd['price']}", parse_mode="Markdown")
            except Exception:
                pass
        del miner_games[uid]
        await call.answer("рџЋ‰ РџРѕР±РµРґР°!")
        return
    await call.message.edit_text(
        f"рџ’Ј *РњРёРЅС‘СЂ* вЂ” @{username}\nрџ’° РЎС‚Р°РІРєР°: {game['bet']}\nрџџў РћС‚РєСЂС‹С‚Рѕ: {count}\nрџ“€ РњРЅРѕР¶РёС‚РµР»СЊ: Г—{multiplier}\nрџ’µ Р—Р°Р±РµСЂС‘С€СЊ: {potential}",
        reply_markup=miner_keyboard(game["opened"], game["mines"], uid), parse_mode="Markdown"
    )
    await call.answer(f"РћС‚РєСЂС‹С‚Рѕ: {count} | Г—{multiplier}")


@dp.callback_query(F.data.startswith("miner_cashout_"))
async def miner_cashout(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("РќРµ С‚РІРѕСЏ РёРіСЂР°!", show_alert=True)
        return
    username = call.from_user.username or call.from_user.full_name or "РРіСЂРѕРє"
    game = miner_games.get(uid)
    if not game or game.get("state") != "playing":
        await call.answer("РРіСЂР° РЅРµ Р°РєС‚РёРІРЅР°.", show_alert=True)
        return
    count = len(game["opened"])
    if count == 0:
        await call.answer("РћС‚РєСЂРѕР№ С…РѕС‚СЏ Р±С‹ РѕРґРЅСѓ РєР»РµС‚РєСѓ!", show_alert=True)
        return
    multiplier = MINER_MULTIPLIERS.get(count, 30.0)
    win = int(game["bet"] * multiplier)
    cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (win, uid))
    db.commit()
    game["state"] = "finished"
    del miner_games[uid]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="рџЋ° РРіСЂР°С‚СЊ СЃРЅРѕРІР°", callback_data=f"casino_miner_{uid}")],
        [InlineKeyboardButton(text="рџ”™ Casino", callback_data=f"open_casino_{uid}")],
    ])
    await call.message.edit_text(
        f"рџ’Ј *РњРёРЅС‘СЂ* вЂ” @{username}\n\nрџ’° РЎС‚Р°РІРєР°: {game['bet']}\nрџџў РћС‚РєСЂС‹С‚Рѕ: {count}\nрџ“€ РњРЅРѕР¶РёС‚РµР»СЊ: Г—{multiplier}\n\nвњ… *Р—Р°Р±СЂР°Р» {win} РјРѕРЅРµС‚!*",
        reply_markup=kb, parse_mode="Markdown"
    )
    await call.answer(f"РџРѕР»СѓС‡РµРЅРѕ {win}!")


@dp.message(Command("halloween"))
async def halloween_menu(message: types.Message):
    uid = message.from_user.id
    username = message.from_user.username or message.from_user.full_name or "РРіСЂРѕРє"
    balance, _, _, _, hw = get_user(uid, message.from_user.username)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="рџЋѓ РљР•Р™РЎР«", callback_data=f"hw_cases_{uid}")],
        [InlineKeyboardButton(text="рџЋѓ РҐРµР»Р»РѕСѓРёРЅ-Р‘РѕСЃСЃ", callback_data=f"hw_boss_{uid}")],
        [InlineKeyboardButton(text="рџ’± РљРѕРЅРІРµСЂС‚Р°С†РёСЏ", callback_data=f"hw_conv_{uid}")],
        [InlineKeyboardButton(text="рџ”™ Р—Р°РєСЂС‹С‚СЊ", callback_data=f"hw_close_{uid}")],
    ])
    caption = (
        f"рџЋѓ *РҐРµР»Р»РѕСѓРёРЅ* вЂ” @{username}\n\n"
        f"рџ’Ђ Р—РґСЂР°РІСЃС‚РІСѓР№С‚Рµ, СЃРјРµСЂС‚РЅС‹Рµ!\n"
        f"Р’СЃС‚СЂРµС‡Р°Р№С‚Рµ РҐРµР»Р»РѕСѓРёРЅ вЂ” РІСЂРµРјСЏ СѓР¶Р°СЃР° Рё РєР°СЂС‚РѕС‡РµРє!\n\n"
        f"рџ’° РћР±С‹С‡РЅС‹С… РјРѕРЅРµС‚: {balance}\n"
        f"рџЌ¬ РљРѕРЅС„РµС‚: {hw}\n\n"
        f"*Р’С‹Р±РёСЂР°Р№:*"
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
        await call.answer("РќРµ С‚РІРѕС‘ РјРµРЅСЋ!", show_alert=True)
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
        await call.answer("РќРµ С‚РІРѕС‘ РјРµРЅСЋ!", show_alert=True)
        return
    await call.answer("рџ”’ РЎРєРѕСЂРѕ!", show_alert=True)


@dp.callback_query(F.data.startswith("hw_back_"))
async def hw_back(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("РќРµ С‚РІРѕС‘ РјРµРЅСЋ!", show_alert=True)
        return
    username = call.from_user.username or call.from_user.full_name or "РРіСЂРѕРє"
    balance, _, _, _, hw = get_user(uid)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="рџЋѓ РљР•Р™РЎР«", callback_data=f"hw_cases_{uid}")],
        [InlineKeyboardButton(text="рџЋѓ РҐРµР»Р»РѕСѓРёРЅ-Р‘РѕСЃСЃ", callback_data=f"hw_boss_{uid}")],
        [InlineKeyboardButton(text="рџ’± РљРѕРЅРІРµСЂС‚Р°С†РёСЏ", callback_data=f"hw_conv_{uid}")],
        [InlineKeyboardButton(text="рџ”™ Р—Р°РєСЂС‹С‚СЊ", callback_data=f"hw_close_{uid}")],
    ])
    caption = (
        f"рџЋѓ *РҐРµР»Р»РѕСѓРёРЅ* вЂ” @{username}\n\n"
        f"рџ’° РћР±С‹С‡РЅС‹С… РјРѕРЅРµС‚: {balance}\nрџЌ¬ РљРѕРЅС„РµС‚: {hw}\n\n"
        f"*Р’С‹Р±РёСЂР°Р№:*"
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
        await call.answer("РќРµ С‚РІРѕС‘ РјРµРЅСЋ!", show_alert=True)
        return
    username = call.from_user.username or call.from_user.full_name or "РРіСЂРѕРє"
    balance, _, _, _, hw = get_user(uid)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="рџЋѓ РўС‹РєРІРµРЅРЅС‹Р№ РєРµР№СЃ вЂ” 1000 рџЌ¬", callback_data=f"hw_case_pumpkin_{uid}")],
        [InlineKeyboardButton(text="рџ’Ђ РЎРєРµР»РµС‚РЅС‹Р№ РєРµР№СЃ вЂ” 10000 рџЌ¬", callback_data=f"hw_case_skeleton_{uid}")],
        [InlineKeyboardButton(text="рџ‘» РџСЂРёР·СЂР°С‡РЅС‹Р№ РєРµР№СЃ вЂ” 100000 рџЌ¬", callback_data=f"hw_case_ghost_{uid}")],
        [InlineKeyboardButton(text="рџ”™ РќР°Р·Р°Рґ", callback_data=f"hw_back_{uid}")],
    ])
    await call.message.edit_caption(
        caption=(
            f"рџЋѓ *РљРµР№СЃС‹ РҐРµР»Р»РѕСѓРёРЅР°* вЂ” @{username}\n\n"
            f"рџЌ¬ РЈ С‚РµР±СЏ: {hw} РєРѕРЅС„РµС‚\n\n"
            f"*Р’С‹Р±РёСЂР°Р№ РєРµР№СЃ:*"
        ),
        reply_markup=kb, parse_mode="Markdown"
    )
    await call.answer()


@dp.callback_query(F.data.startswith("hw_conv_"))
async def hw_convert_menu(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("РќРµ С‚РІРѕС‘ РјРµРЅСЋ!", show_alert=True)
        return
    username = call.from_user.username or call.from_user.full_name or "РРіСЂРѕРє"
    balance, _, _, _, hw = get_user(uid)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="рџ’± РњРѕРЅРµС‚С‹ в†’ рџЌ¬ (100 = 10)", callback_data=f"hw_to_{uid}")],
        [InlineKeyboardButton(text="рџ’± рџЌ¬ в†’ РњРѕРЅРµС‚С‹ (10 = 90)", callback_data=f"hw_from_{uid}")],
        [InlineKeyboardButton(text="рџ”™ РќР°Р·Р°Рґ", callback_data=f"hw_back_{uid}")],
    ])
    await call.message.edit_caption(
        caption=(
            f"рџ’± *РљРѕРЅРІРµСЂС‚Р°С†РёСЏ* вЂ” @{username}\n\n"
            f"рџ’° РћР±С‹С‡РЅС‹С…: {balance}\nрџЌ¬ РљРѕРЅС„РµС‚: {hw}\n\nР§С‚Рѕ РґРµР»Р°РµРј?"
        ),
        reply_markup=kb, parse_mode="Markdown"
    )
    await call.answer()


@dp.callback_query(F.data.startswith("hw_to_"))
async def hw_convert_to(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("РќРµ С‚РІРѕС‘ РјРµРЅСЋ!", show_alert=True)
        return
    hw_games[uid] = {"state": "wait_amount_to"}
    await call.message.edit_caption(
        caption="рџ’± *РњРѕРЅРµС‚С‹ в†’ рџЌ¬*\n\nРљСѓСЂСЃ: 100 РјРѕРЅРµС‚ = 10 рџЌ¬\n\nРќР°РїРёС€Рё, СЃРєРѕР»СЊРєРѕ *РјРѕРЅРµС‚* РѕР±РјРµРЅСЏС‚СЊ (РєСЂР°С‚РЅРѕ 100).\nРџСЂРёРјРµСЂ: `100` в†’ 10 рџЌ¬\n\nРћС‚РјРµРЅР° вЂ” /cancel",
        parse_mode="Markdown"
    )
    await call.answer()


@dp.callback_query(F.data.startswith("hw_from_"))
async def hw_convert_from(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("РќРµ С‚РІРѕС‘ РјРµРЅСЋ!", show_alert=True)
        return
    hw_games[uid] = {"state": "wait_amount_from"}
    await call.message.edit_caption(
        caption="рџ’± *рџЌ¬ в†’ РњРѕРЅРµС‚С‹*\n\nРљСѓСЂСЃ: 10 рџЌ¬ = 90 РјРѕРЅРµС‚ (РЅР°Р»РѕРі 10%)\n\nРќР°РїРёС€Рё, СЃРєРѕР»СЊРєРѕ *рџЌ¬* РѕР±РјРµРЅСЏС‚СЊ (РєСЂР°С‚РЅРѕ 10).\nРџСЂРёРјРµСЂ: `10` в†’ 90 РјРѕРЅРµС‚\n\nРћС‚РјРµРЅР° вЂ” /cancel",
        parse_mode="Markdown"
    )
    await call.answer()


CASE_NAMES = {
    "pumpkin": "рџЋѓ РўС‹РєРІРµРЅРЅС‹Р№",
    "skeleton": "рџ’Ђ РЎРєРµР»РµС‚РЅС‹Р№",
    "ghost": "рџ‘» РџСЂРёР·СЂР°С‡РЅС‹Р№",
}


@dp.callback_query(F.data.startswith("hw_case_"))
async def hw_case_open_menu(call: types.CallbackQuery):
    parts = call.data.split("_")
    case_type = parts[2]
    uid = int(parts[3])
    if call.from_user.id != uid:
        await call.answer("РќРµ С‚РІРѕС‘ РјРµРЅСЋ!", show_alert=True)
        return

    username = call.from_user.username or call.from_user.full_name or "РРіСЂРѕРє"
    balance, _, _, _, hw = get_user(uid)
    price = CASE_PRICES[case_type]

    chances = CASE_CHANCES[case_type]
    chances_text = "\n".join([f"{r} вЂ” {c}%" for r, c in chances.items()])

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"рџЋЃ РћС‚РєСЂС‹С‚СЊ Р·Р° {price} рџЌ¬", callback_data=f"hw_open_{case_type}_{uid}")],
        [InlineKeyboardButton(text="рџ”™ РќР°Р·Р°Рґ", callback_data=f"hw_cases_{uid}")],
    ])
    await call.message.edit_caption(
        caption=(
            f"{CASE_NAMES[case_type]} *РєРµР№СЃ* вЂ” @{username}\n\n"
            f"рџ’° Р¦РµРЅР°: {price} рџЌ¬\nрџЌ¬ РЈ С‚РµР±СЏ: {hw}\n\n"
            f"*Р§С‚Рѕ РІС‹РїР°РґР°РµС‚:*\n{chances_text}"
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
        await call.answer("РќРµ С‚РІРѕС‘ РјРµРЅСЋ!", show_alert=True)
        return

    username = call.from_user.username or call.from_user.full_name or "РРіСЂРѕРє"
    balance, _, _, _, hw = get_user(uid)
    price = CASE_PRICES[case_type]

    if hw < price:
        await call.answer(f"вќЊ РќСѓР¶РЅРѕ {price} рџЌ¬, Сѓ С‚РµР±СЏ {hw}", show_alert=True)
        return

    cur.execute("UPDATE users SET hw_balance = hw_balance - ? WHERE user_id = ?", (price, uid))
    db.commit()
    card, rarity = roll_hw_card(case_type)
    cur.execute("INSERT INTO inventory (user_id, card_name) VALUES (?, ?)", (uid, card["name"]))
    db.commit()
    new_hw = hw - price

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="рџЋЃ РћС‚РєСЂС‹С‚СЊ РµС‰С‘", callback_data=f"hw_open_{case_type}_{uid}")],
        [InlineKeyboardButton(text="рџ”™ РќР°Р·Р°Рґ", callback_data=f"hw_cases_{uid}")],
    ])

    try:
        photo = FSInputFile(card["file"])
        caption = (
            f"{CASE_NAMES[case_type]} *РєРµР№СЃ* вЂ” @{username}\n\n"
            f"рџЋ‰ РўРµР±Рµ РІС‹РїР°Р»Р° РєР°СЂС‚РѕС‡РєР°!\n\n"
            f"рџЋґ *{card['name']}*\nР РµРґРєРѕСЃС‚СЊ: {rarity}\nрџ’° Р¦РµРЅР°: {card['price']} рџЌ¬\n\n"
            f"рџЌ¬ РћСЃС‚Р°Р»РѕСЃСЊ: {new_hw}"
        )
        await call.message.delete()
        await call.message.answer_photo(photo, caption=caption, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        await call.message.edit_caption(
            caption=f"рџЋ‰ Р’С‹РїР°Р»Р°: *{card['name']}* ({rarity}, {card['price']} рџЌ¬)\nрџЌ¬ РћСЃС‚Р°Р»РѕСЃСЊ: {new_hw}",
            reply_markup=kb, parse_mode="Markdown"
        )
    await call.answer("рџЋЃ РљРµР№СЃ РѕС‚РєСЂС‹С‚!")


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
        attack_info = f"вљ”пёЏ РђС‚Р°РєР° Р±РѕСЃСЃР° С‡РµСЂРµР·: {next_attack} С…РѕРґ(Р°)"
    else:
        attack_info = "вљ”пёЏ Р‘РѕСЃСЃ Р°С‚Р°РєСѓРµС‚ РЅР° СЃР»РµРґСѓСЋС‰РµРј С…РѕРґСѓ!"
    return (
        f"рџЋѓ *РҐР•Р›Р›РћРЈРРќ-Р‘РћРЎРЎ* вЂ” @{username}\n\n"
        f"рџ’Ђ Р‘РѕСЃСЃ: {boss_hp}/{BOSS_MAX_HP} HP\n"
        f"вќ¤пёЏ РўС‹: {player_hp}/{PLAYER_MAX_HP} HP\n\n"
        f"рџ“Ќ Р Р°СѓРЅРґ {round_num}/{total_rounds}\n"
        f"рџЋѓ РќР°Р№РґРµРЅРѕ С‚С‹РєРІ: {found}/{pumpkins_count}\n"
        f"{attack_info}\n\n"
        f"*РџСЂР°РІРёР»Р°:*\n"
        f"рџЋѓ РўС‹РєРІР° в†’ Р±РѕСЃСЃСѓ в€’10 HP\n"
        f"вќЊ РџСЂРѕРјР°С… в†’ С‚РµР±Рµ в€’10 HP\n"
        f"вљ”пёЏ РљР°Р¶РґС‹Рµ 3 С…РѕРґР° в†’ С‚РµР±Рµ в€’5 HP"
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
                row.append(InlineKeyboardButton(text="рџЋѓ", callback_data="boss_noop"))
            else:
                row.append(InlineKeyboardButton(text="вќЊ", callback_data="boss_noop"))
        else:
            row.append(InlineKeyboardButton(text="рџЌ¬", callback_data=f"boss_cell_{i}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="рџЏіпёЏ РЎРґР°С‚СЊСЃСЏ", callback_data="boss_surrender")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@dp.callback_query(F.data.regexp(r"^hw_boss_\d+$"))
async def hw_boss_start(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("РќРµ С‚РІРѕС‘ РјРµРЅСЋ!", show_alert=True)
        return

    if uid in boss_cooldowns:
        elapsed = datetime.now() - boss_cooldowns[uid]
        if elapsed < timedelta(minutes=BOSS_COOLDOWN_MINUTES):
            left = timedelta(minutes=BOSS_COOLDOWN_MINUTES) - elapsed
            await call.answer(f"вЏі РљСѓР»РґР°СѓРЅ: {format_cooldown(int(left.total_seconds()))}", show_alert=True)
            return

    if boss_lock["current"] is not None and boss_lock["current"] != uid:
        await call.answer("вЏі РљС‚Рѕ-С‚Рѕ СѓР¶Рµ СЃСЂР°Р¶Р°РµС‚СЃСЏ СЃ Р±РѕСЃСЃРѕРј! РџРѕРґРѕР¶РґРё.", show_alert=True)
        return

    username = call.from_user.username or call.from_user.full_name or "РРіСЂРѕРє"
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
    await call.answer("вљ”пёЏ Р‘РѕР№ РЅР°С‡Р°Р»СЃСЏ!")


@dp.callback_query(F.data == "boss_noop")
async def boss_noop(call: types.CallbackQuery):
    await call.answer("РЈР¶Рµ РѕС‚РєСЂС‹С‚Рѕ.")


@dp.callback_query(F.data.startswith("boss_cell_"))
async def boss_cell(call: types.CallbackQuery):
    parts = call.data.split("_")
    idx = int(parts[2])
    uid = call.from_user.id

    game = boss_games.get(uid)
    if not game:
        await call.answer("РРіСЂР° РЅРµ Р°РєС‚РёРІРЅР°.", show_alert=True)
        return
    if idx in game["opened"]:
        await call.answer("РЈР¶Рµ РѕС‚РєСЂС‹С‚Рѕ.")
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
                [InlineKeyboardButton(text="рџ”™ РќР°Р·Р°Рґ", callback_data=f"hw_boss_done_{uid}")]
            ])
            try:
                photo = FSInputFile(BOSS_ALIVE)
                await call.message.delete()
                await call.message.answer_photo(
                    photo,
                    caption=(
                        f"рџ’Ђ *Р‘РћРЎРЎ Р”РћР‘РР› РўР•Р‘РЇ!*\n\n"
                        f"вќ¤пёЏ РўС‹: 0/{PLAYER_MAX_HP} HP\n"
                        f"рџ’Ђ Р‘РѕСЃСЃ: {game['boss_hp']}/{BOSS_MAX_HP} HP\n\n"
                        f"рџЌ¬ РџРѕС‚РµСЂСЏРЅРѕ: {lost} РєРѕРЅС„РµС‚ (50%)\n\n"
                        f"вЏі РљСѓР»РґР°СѓРЅ: 1 С‡Р°СЃ"
                    ),
                    reply_markup=kb, parse_mode="Markdown"
                )
            except Exception:
                pass
            await call.answer("рџ’Ђ Р‘РѕСЃСЃ С‚РµР±СЏ РґРѕР±РёР»!")
            return

    if idx in game["pumpkins"]:
        game["found_pumpkins"].add(idx)
        game["boss_hp"] -= BOSS_DAMAGE
        if game["boss_hp"] < 0:
            game["boss_hp"] = 0

        if game["boss_hp"] <= 0:
            boss_lock["current"] = None
            boss_cooldowns[uid] = datetime.now()
            cur.execute("INSERT INTO inventory (user_id, card_name) VALUES (?, ?)", (uid, "РҐРµР»Р»РѕСѓРёРЅСЃРєРёР№ Р±РѕСЃСЃ"))
            cur.execute("UPDATE users SET hw_balance = hw_balance + ? WHERE user_id = ?", (BOSS_REWARD_CANDY, uid))
            db.commit()
            del boss_games[uid]
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="рџ”™ РќР°Р·Р°Рґ", callback_data=f"hw_boss_done_{uid}")]
            ])
            try:
                photo = FSInputFile(BOSS_DEAD)
                await call.message.delete()
                await call.message.answer_photo(
                    photo,
                    caption=(
                        f"рџЋ‰ *РџРћР—Р”Р РђР’Р›РЇР®, Р’Р« РџРћР‘Р•Р”РР›Р Р‘РћРЎРЎРђ!*\n\n"
                        f"рџ’Ђ Р‘РѕСЃСЃ: 0/{BOSS_MAX_HP} HP\n\n"
                        f"рџЋґ РџРѕР»СѓС‡РµРЅР° РєР°СЂС‚РѕС‡РєР°: *РҐРµР»Р»РѕСѓРёРЅСЃРєРёР№ Р±РѕСЃСЃ*\n"
                        f"рџ’  РЎРїРµС†РёР°Р»СЊРЅР°СЏ | рџ’° 100 000 РјРѕРЅРµС‚\n\n"
                        f"рџЌ¬ +{BOSS_REWARD_CANDY} РєРѕРЅС„РµС‚\n\n"
                        f"вЏі РљСѓР»РґР°СѓРЅ: 1 С‡Р°СЃ"
                    ),
                    reply_markup=kb, parse_mode="Markdown"
                )
            except Exception:
                pass
            await call.answer("рџЋ‰ Р‘РћРЎРЎ РџРћР’Р•Р Р–Р•Рќ!")
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
        msg = f"рџЋѓ РўС‹РєРІР°! Р‘РѕСЃСЃ в€’{BOSS_DAMAGE} HP"
        if boss_attacked:
            msg += f" | вљ”пёЏ Р‘РѕСЃСЃ в€’{BOSS_ATTACK_DAMAGE} С‚РµР±Рµ!"
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
                [InlineKeyboardButton(text="рџ”™ РќР°Р·Р°Рґ", callback_data=f"hw_boss_done_{uid}")]
            ])
            try:
                photo = FSInputFile(BOSS_ALIVE)
                await call.message.delete()
                await call.message.answer_photo(
                    photo,
                    caption=(
                        f"рџ’Ђ *РўР« РџРђР› Р’ Р‘РћР®*\n\n"
                        f"вќ¤пёЏ РўС‹: 0/{PLAYER_MAX_HP} HP\n"
                        f"рџ’Ђ Р‘РѕСЃСЃ: {game['boss_hp']}/{BOSS_MAX_HP} HP\n\n"
                        f"рџЌ¬ РџРѕС‚РµСЂСЏРЅРѕ: {lost} РєРѕРЅС„РµС‚ (50%)\n\n"
                        f"вЏі РљСѓР»РґР°СѓРЅ: 1 С‡Р°СЃ"
                    ),
                    reply_markup=kb, parse_mode="Markdown"
                )
            except Exception:
                pass
            await call.answer("рџ’Ђ РўС‹ РїСЂРѕРёРіСЂР°Р»!")
            return

        kb = boss_build_kb(game)
        try:
            await call.message.edit_caption(
                caption=boss_render_text(game, uid),
                reply_markup=kb, parse_mode="Markdown"
            )
        except Exception:
            pass
        msg = f"вќЊ РџСЂРѕРјР°С…! РўРµР±Рµ в€’{PLAYER_DAMAGE} HP"
        if boss_attacked:
            msg += f" | вљ”пёЏ Р‘РѕСЃСЃ РµС‰С‘ в€’{BOSS_ATTACK_DAMAGE}!"
        await call.answer(msg)
        return


@dp.callback_query(F.data == "boss_surrender")
async def boss_surrender(call: types.CallbackQuery):
    uid = call.from_user.id
    game = boss_games.get(uid)
    if not game:
        await call.answer("РќРµС‚ Р°РєС‚РёРІРЅРѕР№ РёРіСЂС‹.")
        return
    boss_lock["current"] = None
    boss_cooldowns[uid] = datetime.now()
    del boss_games[uid]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="рџ”™ РќР°Р·Р°Рґ", callback_data=f"hw_boss_done_{uid}")]
    ])
    try:
        await call.message.edit_caption(
            caption="рџЏіпёЏ *РўС‹ СЃРґР°Р»СЃСЏ!*\n\nвЏі РљСѓР»РґР°СѓРЅ: 1 С‡Р°СЃ",
            reply_markup=kb, parse_mode="Markdown"
        )
    except Exception:
        pass
    await call.answer("РЎРґР°Р»СЃСЏ")


@dp.callback_query(F.data.startswith("hw_boss_done_"))
async def hw_boss_done(call: types.CallbackQuery):
    uid = int(call.data.split("_")[3])
    if call.from_user.id != uid:
        await call.answer("РќРµ С‚РІРѕС‘ РјРµРЅСЋ!", show_alert=True)
        return
    username = call.from_user.username or call.from_user.full_name or "РРіСЂРѕРє"
    balance, _, _, _, hw = get_user(uid)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="рџЋѓ РљР•Р™РЎР«", callback_data=f"hw_cases_{uid}")],
        [InlineKeyboardButton(text="рџЋѓ РҐРµР»Р»РѕСѓРёРЅ-Р‘РѕСЃСЃ", callback_data=f"hw_boss_{uid}")],
        [InlineKeyboardButton(text="рџ’± РљРѕРЅРІРµСЂС‚Р°С†РёСЏ", callback_data=f"hw_conv_{uid}")],
        [InlineKeyboardButton(text="рџ”™ Р—Р°РєСЂС‹С‚СЊ", callback_data=f"hw_close_{uid}")],
    ])
    caption = (
        f"рџЋѓ *РҐРµР»Р»РѕСѓРёРЅ* вЂ” @{username}\n\n"
        f"рџ’° РћР±С‹С‡РЅС‹С… РјРѕРЅРµС‚: {balance}\nрџЌ¬ РљРѕРЅС„РµС‚: {hw}\n\n"
        f"*Р’С‹Р±РёСЂР°Р№:*"
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
    if uid in coin_games:
        del coin_games[uid]
        cancelled = True
    if uid in boss_games:
        boss_lock["current"] = None
        boss_cooldowns[uid] = datetime.now()
        del boss_games[uid]
        cancelled = True
    if cancelled:
        await message.answer("вќЊ РћС‚РјРµРЅРµРЅРѕ.")
    else:
        await message.answer("РќРµС‚ Р°РєС‚РёРІРЅРѕРіРѕ РґРµР№СЃС‚РІРёСЏ.")


@dp.message(F.text.regexp(r"^\d+$"))
async def handle_bet(message: types.Message):
    uid = message.from_user.id
    username = message.from_user.username or message.from_user.full_name or "РРіСЂРѕРє"

    hw_game = hw_games.get(uid)
    if hw_game and hw_game.get("state") == "wait_amount_to":
        amount = int(message.text)
        if amount <= 0 or amount % 100 != 0:
            await message.answer("вќЊ РЎСѓРјРјР° РєСЂР°С‚РЅР° 100.")
            return
        balance, _, _, _, hw = get_user(uid, message.from_user.username)
        if balance < amount:
            await message.answer(f"вќЊ РќРµ С…РІР°С‚Р°РµС‚. РЈ С‚РµР±СЏ {balance}, РЅСѓР¶РЅРѕ {amount}.")
            return
        hw_get = amount // 10
        cur.execute("UPDATE users SET balance = balance - ?, hw_balance = hw_balance + ? WHERE user_id = ?", (amount, hw_get, uid))
        db.commit()
        del hw_games[uid]
        await message.answer(f"вњ… РћР±РјРµРЅ!\nрџ’° -{amount}\nрџЌ¬ +{hw_get}")
        return

    if hw_game and hw_game.get("state") == "wait_amount_from":
        amount = int(message.text)
        if amount <= 0 or amount % 10 != 0:
            await message.answer("вќЊ РљСЂР°С‚РЅРѕ 10.")
            return
        balance, _, _, _, hw = get_user(uid, message.from_user.username)
        if hw < amount:
            await message.answer(f"вќЊ РќРµ С…РІР°С‚Р°РµС‚ рџЌ¬. РЈ С‚РµР±СЏ {hw}, РЅСѓР¶РЅРѕ {amount}.")
            return
        money_get = int(amount * HALLOWEEN_RATE_TO * HALLOWEEN_RATE_BACK)  # 10 рџЌ¬ -> 90 РјРѕРЅРµС‚
        cur.execute("UPDATE users SET hw_balance = hw_balance - ?, balance = balance + ? WHERE user_id = ?", (amount, money_get, uid))
        db.commit()
        del hw_games[uid]
        await message.answer(f"вњ… РћР±РјРµРЅ!\nрџЌ¬ -{amount}\nрџ’° +{money_get} (РЅР°Р»РѕРі 10%)")
        return

    game = coin_games.get(uid)
    if game and game.get("state") == "wait_bet":
        bet = int(message.text)
        if bet <= 0:
            await message.answer("вќЊ РЎС‚Р°РІРєР° > 0.")
            return
        balance, _, _, _, _ = get_user(uid, message.from_user.username)
        if balance < bet:
            await message.answer(f"вќЊ РќРµ С…РІР°С‚Р°РµС‚. РЈ С‚РµР±СЏ {balance}, РЅСѓР¶РЅРѕ {bet}.")
            return
        cur.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (bet, uid))
        db.commit()
        chosen = game["side"]
        del coin_games[uid]
        msg = await message.answer("рџЄ™ РџРѕРґР±СЂР°СЃС‹РІР°РµРј РјРѕРЅРµС‚Сѓ...")
        await asyncio.sleep(1.2)
        result = random.choice(["heads", "tails"])
        if result == chosen:
            win = bet * 2
            cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (win, uid))
            db.commit()
            rt = (f"рџЄ™ *РћСЂС‘Р» Рё СЂРµС€РєР°* вЂ” @{username}\nРўРІРѕСЏ СЃС‚РѕСЂРѕРЅР°: {COIN_SIDES[chosen]}\nрџ’° РЎС‚Р°РІРєР°: {bet}\n\n"
                  f"Р’С‹РїР°Р»Рѕ: {COIN_SIDES[result]}\nрџЋ‰ *Р’С‹РёРіСЂР°Р» {win} РјРѕРЅРµС‚!* (Г—2)")
        else:
            rt = (f"рџЄ™ *РћСЂС‘Р» Рё СЂРµС€РєР°* вЂ” @{username}\nРўРІРѕСЏ СЃС‚РѕСЂРѕРЅР°: {COIN_SIDES[chosen]}\nрџ’° РЎС‚Р°РІРєР°: {bet}\n\n"
                  f"Р’С‹РїР°Р»Рѕ: {COIN_SIDES[result]}\nвќЊ *РџСЂРѕРёРіСЂР°Р» {bet} РјРѕРЅРµС‚.*")
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="рџЄ™ РРіСЂР°С‚СЊ СЃРЅРѕРІР°", callback_data=f"casino_coin_{uid}")],
            [InlineKeyboardButton(text="рџ”™ Casino", callback_data=f"open_casino_{uid}")],
        ])
        await msg.edit_text(rt, reply_markup=kb, parse_mode="Markdown")
        return

    game = color_games.get(uid)
    if game and game.get("state") == "wait_bet":
        bet = int(message.text)
        if bet <= 0:
            await message.answer("вќЊ РЎС‚Р°РІРєР° > 0.")
            return
        balance, _, _, _, _ = get_user(uid, message.from_user.username)
        if balance < bet:
            await message.answer(f"вќЊ РќРµ С…РІР°С‚Р°РµС‚. РЈ С‚РµР±СЏ {balance}, РЅСѓР¶РЅРѕ {bet}.")
            return
        cur.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (bet, uid))
        db.commit()
        chosen = game["color"]
        del color_games[uid]
        result = [random.choice(COLORS) for _ in range(4)]
        matches = sum(1 for c in result if c["code"] == chosen["code"])
        msg = await message.answer(f"рџЋІ РљСЂСѓС‚РёРј...\n\n{chosen['emoji']}")
        await asyncio.sleep(0.9)
        progressive = []
        for c in result:
            progressive.append(c["emoji"])
            text = f"рџЋІ *Color Dice* вЂ” @{username}\nРўРІРѕР№ С†РІРµС‚: {chosen['emoji']} {chosen['name']}\nрџ’° РЎС‚Р°РІРєР°: {bet}\n\n{' '.join(progressive)}"
            await msg.edit_text(text, parse_mode="Markdown")
            await asyncio.sleep(0.9)
        if matches == 1:
            win = bet * 2
            cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (win, uid))
            db.commit()
            rt = f"рџЋІ *Color Dice* вЂ” @{username}\nРўРІРѕР№ С†РІРµС‚: {chosen['emoji']} {chosen['name']}\nрџ’° РЎС‚Р°РІРєР°: {bet}\n\n{' '.join(progressive)}\n\nРЎРѕРІРїР°РґРµРЅРёР№: {matches}\nрџЋ‰ *Р’С‹РёРіСЂР°Р» {win} РјРѕРЅРµС‚!* (Г—2)"
        elif matches == 4:
            win = bet * 4
            cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (win, uid))
            db.commit()
            rt = f"рџЋІ *Color Dice* вЂ” @{username}\nРўРІРѕР№ С†РІРµС‚: {chosen['emoji']} {chosen['name']}\nрџ’° РЎС‚Р°РІРєР°: {bet}\n\n{' '.join(progressive)}\n\nРЎРѕРІРїР°РґРµРЅРёР№: {matches}\nрџЋ‰ *Р”Р–Р•РљРџРћРў! +{win}!* (Г—4)"
        else:
            rt = f"рџЋІ *Color Dice* вЂ” @{username}\nРўРІРѕР№ С†РІРµС‚: {chosen['emoji']} {chosen['name']}\nрџ’° РЎС‚Р°РІРєР°: {bet}\n\n{' '.join(progressive)}\n\nРЎРѕРІРїР°РґРµРЅРёР№: {matches}\nвќЊ *РџСЂРѕРёРіСЂР°Р» {bet} РјРѕРЅРµС‚.*"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="рџЋІ РРіСЂР°С‚СЊ СЃРЅРѕРІР°", callback_data=f"casino_color_{uid}")],
            [InlineKeyboardButton(text="рџ”™ Casino", callback_data=f"open_casino_{uid}")],
        ])
        await msg.edit_text(rt, reply_markup=kb, parse_mode="Markdown")
        return

    game = miner_games.get(uid)
    if game and game.get("state") == "wait_bet":
        bet = int(message.text)
        if bet <= 0:
            await message.answer("вќЊ РЎС‚Р°РІРєР° > 0.")
            return
        balance, _, _, _, _ = get_user(uid, message.from_user.username)
        if balance < bet:
            await message.answer(f"вќЊ РќРµ С…РІР°С‚Р°РµС‚. РЈ С‚РµР±СЏ {balance}, РЅСѓР¶РЅРѕ {bet}.")
            return
        cur.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (bet, uid))
        db.commit()
        mines_count = random.randint(2, 6)
        mines_set = set(random.sample(range(9), mines_count))
        miner_games[uid] = {"state": "playing", "bet": bet, "mines": mines_set, "opened": []}
        await message.answer(
            f"рџ’Ј *РњРёРЅС‘СЂ* вЂ” @{username}\nрџ’° РЎС‚Р°РІРєР°: {bet}\nрџџў РћС‚РєСЂС‹С‚Рѕ: 0\nрџ“€ РњРЅРѕР¶РёС‚РµР»СЊ: Г—1.0\nрџ’µ Р—Р°Р±РµСЂС‘С€СЊ: {bet}",
            reply_markup=miner_keyboard([], mines_set, uid), parse_mode="Markdown"
        )
        return


@dp.message(Command("mycards"))
async def mycards(message: types.Message):
    uid = message.from_user.id
    cur.execute("SELECT card_name FROM inventory WHERE user_id = ?", (uid,))
    rows = cur.fetchall()
    if not rows:
        await message.answer("РџСѓСЃС‚Рѕ. РќР°РїРёС€Рё /card")
        return
    counts = {}
    for (name,) in rows:
        counts[name] = counts.get(name, 0) + 1
    text = "рџЋ’ *РРЅРІРµРЅС‚Р°СЂСЊ:*\n\n"
    for name, cnt in counts.items():
        text += f"вЂў {name} Г— {cnt}\n"
    await message.answer(text, parse_mode="Markdown")


@dp.message(Command("balance"))
async def balance_cmd(message: types.Message):
    balance, _, _, _, hw = get_user(message.from_user.id, message.from_user.username)
    await message.answer(f"рџ’° РћР±С‹С‡РЅС‹С…: {balance}\nрџЌ¬ РљРѕРЅС„РµС‚: {hw}")


@dp.message(Command("profile"))
async def profile(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        tu = args[1].lstrip("@").strip()
        cur.execute("SELECT user_id, username, balance, level, registered_at FROM users WHERE username = ?", (tu,))
        row = cur.fetchone()
        if not row:
            await message.answer(f"вќЊ @{tu} РЅРµ РЅР°Р№РґРµРЅ.")
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
        f"рџ‘¤ Р­С‚Рѕ РїРѕР»СЊР·РѕРІР°С‚РµР»СЊ @{tun or 'РРіСЂРѕРє'}\nрџ“… РЎ {date_str}\n\n"
        f"рџ’° Р‘Р°Р»Р°РЅСЃ: {balance} РјРѕРЅРµС‚\nрџЏ† РњРµСЃС‚Рѕ РІ С‚РѕРїРµ: #{place}\nрџЋґ РљР°СЂС‚РѕС‡РµРє: {total}"
    )
    try:
        img = await make_profile_image(tid, tun, balance, place, level, total)
        photo = BufferedInputFile(img.read(), filename="profile.png")
        await message.answer_photo(photo, caption=caption)
    except Exception as e:
        await message.answer(caption + f"\n\n_РћС€РёР±РєР°: {e}_", parse_mode="Markdown")


@dp.message(Command("top"))
async def top(message: types.Message):
    cur.execute("SELECT username, balance FROM users ORDER BY balance DESC LIMIT 3")
    rows = cur.fetchall()
    if not rows:
        await message.answer("РџРѕРєР° РЅРёРєС‚Рѕ.")
        return
    medals = ["рџҐ‡", "рџҐ€", "рџҐ‰"]
    text = "рџЏ† *РўРѕРї-3:*\n\n"
    for i, (uname, bal) in enumerate(rows):
        name = f"@{uname}" if uname else f"РРіСЂРѕРє #{i+1}"
        text += f"{medals[i]} *{name}*\n      рџ’° {bal} РјРѕРЅРµС‚\n\n"
    await message.answer(text, parse_mode="Markdown")


@dp.message(Command("sell"))
async def sell(message: types.Message):
    uid = message.from_user.id
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("РСЃРїРѕР»СЊР·РѕРІР°РЅРёРµ: /sell РќР°Р·РІР°РЅРёРµ")
        return
    name = args[1].strip()
    cur.execute("SELECT rowid FROM inventory WHERE user_id = ? AND card_name = ? LIMIT 1", (uid, name))
    row = cur.fetchone()
    if not row:
        await message.answer("вќЊ РќРµС‚ С‚Р°РєРѕР№ РєР°СЂС‚РѕС‡РєРё.")
        return
    hw_card = find_hw_card(name)
    card_data = next((c for c in cards if c["name"].lower() == name.lower()), None)
    if hw_card:
        cur.execute("DELETE FROM inventory WHERE rowid = ?", (row[0],))
        cur.execute("UPDATE users SET hw_balance = hw_balance + ? WHERE user_id = ?", (hw_card["price"], uid))
        db.commit()
        await message.answer(f"вњ… РџСЂРѕРґР°РЅРѕ: {hw_card['name']} Р·Р° {hw_card['price']} рџЌ¬")
        return
    if not card_data:
        await message.answer("вќЊ РќРµРёР·РІРµСЃС‚РЅР°СЏ.")
        return
    cur.execute("DELETE FROM inventory WHERE rowid = ?", (row[0],))
    cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (card_data["price"], uid))
    db.commit()
    await message.answer(f"вњ… РџСЂРѕРґР°РЅРѕ: {card_data['name']} Р·Р° {card_data['price']} РјРѕРЅРµС‚")


@dp.message(Command("sellall"))
async def sellall(message: types.Message):
    uid = message.from_user.id
    cur.execute("SELECT card_name, COUNT(*) FROM inventory WHERE user_id = ? GROUP BY card_name", (uid,))
    rows = cur.fetchall()
    if not rows:
        await message.answer("вќЊ РќРµС‚ РєР°СЂС‚РѕС‡РµРє.")
        return
    total_sum = 0
    text = "рџ’° *Р‘СѓРґРµС‚ РїСЂРѕРґР°РЅРѕ:*\n\n"
    for name, cnt in rows:
        cd = next((c for c in cards if c["name"] == name), None)
        if not cd:
            continue
        subtotal = cd["price"] * cnt
        total_sum += subtotal
        text += f"вЂў {name} Г— {cnt} = {subtotal} РјРѕРЅРµС‚\n"
    text += f"\nрџ’µ *РС‚РѕРіРѕ: {total_sum} РјРѕРЅРµС‚*\n\n_РҐРµР»Р»РѕСѓРёРЅСЃРєРёРµ РєР°СЂС‚РѕС‡РєРё РЅРµ РїСЂРѕРґР°СЋС‚СЃСЏ С‡РµСЂРµР· /sellall вЂ” РёСЃРїРѕР»СЊР·СѓР№ /sell РќР°Р·РІР°РЅРёРµ._"
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="вњ… Р”Р°", callback_data="sellall_yes"),
        InlineKeyboardButton(text="вќЊ РќРµС‚", callback_data="sellall_no"),
    ]])
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")


@dp.callback_query(F.data.startswith("sellall_"))
async def sellall_cb(call: types.CallbackQuery):
    uid = call.from_user.id
    if call.data == "sellall_no":
        await call.message.edit_text("вќЊ РћС‚РјРµРЅРµРЅРѕ.")
        await call.answer()
        return
    cur.execute("SELECT card_name, COUNT(*) FROM inventory WHERE user_id = ? GROUP BY card_name", (uid,))
    rows = cur.fetchall()
    if not rows:
        await call.answer("РџСѓСЃС‚Рѕ!", show_alert=True)
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
    await call.message.edit_text(f"вњ… РџСЂРѕРґР°РЅРѕ Р·Р° {total_sum} РјРѕРЅРµС‚.")
    await call.answer("Р“РѕС‚РѕРІРѕ!")


@dp.message(Command("upgrade"))
async def upgrade(message: types.Message):
    uid = message.from_user.id
    balance, _, level, _, _ = get_user(uid, message.from_user.username)
    if level >= MAX_LEVEL:
        await message.answer("в›” РњР°РєСЃРёРјСѓРј 3.")
        return
    nl = level + 1
    price = UPGRADE_PRICES[nl]
    if balance < price:
        await message.answer(f"вќЊ РќСѓР¶РЅРѕ {price}, Сѓ С‚РµР±СЏ {balance}.")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="вњ… Р”Р°", callback_data=f"upg_yes_{nl}"),
        InlineKeyboardButton(text="вќЊ РќРµС‚", callback_data="upg_no"),
    ]])
    await message.answer(
        f"в¬†пёЏ *РЈР»СѓС‡С€РµРЅРёРµ РґРѕ СѓСЂ. {nl}*\n\nР‘СѓРґРµС‚ РІС‹РґР°РІР°С‚СЊ {nl} РєР°СЂС‚С‹ Р·Р° /card\n\nрџ’° Р¦РµРЅР°: {price}\nрџ’і РЈ С‚РµР±СЏ: {balance}",
        reply_markup=kb, parse_mode="Markdown"
    )


@dp.callback_query(F.data.startswith("upg_"))
async def upg_cb(call: types.CallbackQuery):
    uid = call.from_user.id
    balance, _, level, _, _ = get_user(uid, call.from_user.username)
    if call.data == "upg_no":
        await call.message.edit_text("вќЊ РћС‚РјРµРЅРµРЅРѕ.")
        await call.answer()
        return
    nl = int(call.data.split("_")[2])
    price = UPGRADE_PRICES[nl]
    if level >= nl:
        await call.answer("РЈР¶Рµ РєСѓРїР»РµРЅРѕ!", show_alert=True)
        return
    if balance < price:
        await call.answer("РќРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ РјРѕРЅРµС‚!", show_alert=True)
        return
    cur.execute("UPDATE users SET balance = balance - ?, level = ? WHERE user_id = ?", (price, nl, uid))
    db.commit()
    await call.message.edit_text(f"вњ… РЈР»СѓС‡С€РµРЅРёРµ! РўРµРїРµСЂСЊ СѓСЂРѕРІРµРЅСЊ {nl}.")
    await call.answer("РђРєС‚РёРІРёСЂРѕРІР°РЅРѕ!")


@dp.message(Command("trade"))
async def trade(message: types.Message):
    uid = message.from_user.id
    sn = message.from_user.username or message.from_user.full_name
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("РСЃРїРѕР»СЊР·РѕРІР°РЅРёРµ: /trade @username РќР°Р·РІР°РЅРёРµ")
        return
    tu = args[1].lstrip("@")
    cn = args[2].strip()
    cur.execute("SELECT user_id, username FROM users WHERE username = ?", (tu,))
    row = cur.fetchone()
    if not row:
        await message.answer("вќЊ РќРµ РЅР°Р№РґРµРЅ.")
        return
    tid, tun = row
    if tid == uid:
        await message.answer("вќЊ РЎРµР±Рµ РЅРµР»СЊР·СЏ.")
        return
    cur.execute("SELECT rowid FROM inventory WHERE user_id = ? AND card_name = ? LIMIT 1", (uid, cn))
    if not cur.fetchone():
        await message.answer(f"вќЊ РќРµС‚ РєР°СЂС‚РѕС‡РєРё В«{cn}В».")
        return
    cur.execute("INSERT INTO trades (from_id, to_id, card_name) VALUES (?, ?, ?)", (uid, tid, cn))
    db.commit()
    await message.answer(f"вњ… РћС‚РїСЂР°РІР»РµРЅРѕ @{tun}.")
    try:
        await bot.send_message(tid, f"рџ¤ќ *РўСЂРµР№Рґ!*\n\nрџ‘¤ РћС‚: @{sn}\nрџЋґ *{cn}*\n\n/accept вЂ” РїСЂРёРЅСЏС‚СЊ\n/decline вЂ” РѕС‚РєР»РѕРЅРёС‚СЊ", parse_mode="Markdown")
    except Exception:
        pass


@dp.message(Command("accept"))
async def accept(message: types.Message):
    uid = message.from_user.id
    an = message.from_user.username or message.from_user.full_name
    cur.execute("SELECT rowid, from_id, card_name FROM trades WHERE to_id = ? ORDER BY rowid DESC LIMIT 1", (uid,))
    row = cur.fetchone()
    if not row:
        await message.answer("вќЊ РќРµС‚ РїСЂРµРґР»РѕР¶РµРЅРёР№.")
        return
    rowid, fid, cn = row
    cur.execute("SELECT rowid FROM inventory WHERE user_id = ? AND card_name = ? LIMIT 1", (fid, cn))
    src = cur.fetchone()
    if not src:
        cur.execute("DELETE FROM trades WHERE rowid = ?", (rowid,))
        db.commit()
        await message.answer("вќЊ РЈ РѕС‚РїСЂР°РІРёС‚РµР»СЏ РЅРµС‚ РєР°СЂС‚РѕС‡РєРё.")
        return
    cur.execute("DELETE FROM inventory WHERE rowid = ?", (src[0],))
    cur.execute("INSERT INTO inventory (user_id, card_name) VALUES (?, ?)", (uid, cn))
    cur.execute("DELETE FROM trades WHERE rowid = ?", (rowid,))
    db.commit()
    await message.answer(f"вњ… РџСЂРёРЅСЏР» *{cn}*.", parse_mode="Markdown")
    try:
        await bot.send_message(fid, f"вњ… *РўСЂРµР№Рґ РїСЂРёРЅСЏС‚!*\n\nрџ‘¤ @{an} РїСЂРёРЅСЏР» *{cn}*.", parse_mode="Markdown")
    except Exception:
        pass


@dp.message(Command("decline"))
async def decline(message: types.Message):
    uid = message.from_user.id
    dn = message.from_user.username or message.from_user.full_name
    cur.execute("SELECT rowid, from_id, card_name FROM trades WHERE to_id = ? ORDER BY rowid DESC LIMIT 1", (uid,))
    row = cur.fetchone()
    if not row:
        await message.answer("вќЊ РќРµС‚ РїСЂРµРґР»РѕР¶РµРЅРёР№.")
        return
    rowid, fid, cn = row
    cur.execute("DELETE FROM trades WHERE rowid = ?", (rowid,))
    db.commit()
    await message.answer(f"вќЊ РћС‚РєР»РѕРЅРёР» *{cn}*.", parse_mode="Markdown")
    try:
        await bot.send_message(fid, f"вќЊ *РўСЂРµР№Рґ РѕС‚РєР»РѕРЅС‘РЅ.*\n\nрџ‘¤ @{dn} РѕС‚РєР°Р·Р°Р»СЃСЏ РѕС‚ *{cn}*.", parse_mode="Markdown")
    except Exception:
        pass


# ==== /give (С‚РѕР»СЊРєРѕ РґР»СЏ Р°РґРјРёРЅР°) ====
@dp.message(Command("give"))
async def give(message: types.Message):
    if not is_admin(message.from_user):
        return  # РјРѕР»С‡Р° РёРіРЅРѕСЂРёСЂСѓРµРј РґР»СЏ РѕСЃС‚Р°Р»СЊРЅС‹С…
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("РСЃРїРѕР»СЊР·РѕРІР°РЅРёРµ: /give РќР°Р·РІР°РЅРёРµ РєР°СЂС‚РѕС‡РєРё")
        return
    card_data = find_any_card(args[1].strip())
    if not card_data:
        await message.answer("вќЊ РўР°РєРѕР№ РєР°СЂС‚РѕС‡РєРё РЅРµС‚.")
        return
    uid = message.from_user.id
    get_user(uid, message.from_user.username)
    cur.execute("INSERT INTO inventory (user_id, card_name) VALUES (?, ?)", (uid, card_data["name"]))
    db.commit()
    await message.answer(f"вњ… Р’С‹РґР°РЅРѕ: {card_data['name']}")


async def main():
    await dp.start_polling(bot)


asyncio.run(main())
