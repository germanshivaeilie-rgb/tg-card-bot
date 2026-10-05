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
    {"name": "Топ 1 Минёр",             "rarity": "♣️ Секретная",   "price": 200000, "file": "Picsart_26-10-05_23-53-56-160.jpg"},
    {"name": "Лучший Израель йегуда",   "rarity": "🌌 Бесконечная", "price": 500000, "file": "ChatGPT Image 5 окт. 2026 г., 15_32_46.png"},
]

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

db = sqlite3.connect("game.db")
cur = db.cursor()
cur.execute("""CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    balance INTEGER DEFAULT 0,
    last_card TEXT,
    level INTEGER DEFAULT 1,
    registered_at TEXT
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


def get_user(uid, username=None):
    cur.execute("SELECT balance, last_card, level, registered_at FROM users WHERE user_id = ?", (uid,))
    row = cur.fetchone()
    if not row:
        now = datetime.now().isoformat()
        cur.execute("INSERT INTO users (user_id, username, registered_at) VALUES (?, ?, ?)", (uid, username, now))
        db.commit()
        return 0, None, 1, now
    if username:
        cur.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, uid))
        db.commit()
    return row[0], row[1], row[2], row[3]


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
        "/casino — 🎰 Casino (Color Dice + Минёр)\n"
        "/mycards — инвентарь\n"
        "/balance — баланс монет\n"
        "/sell — продать карточку\n"
        "/sellall — продать всё\n"
        "/upgrade — улучшение\n"
        "/profile — профиль (можно /profile @username)\n"
        "/top — топ-3 игрока\n"
        "/trade @username Название — трейд\n"
        "/accept, /decline — принять/отклонить"
    )


@dp.message(Command("card"))
async def card(message: types.Message):
    uid = message.from_user.id
    username = message.from_user.username or "Игрок"
    balance, last, level, _ = get_user(uid, message.from_user.username)

    if last:
        last_dt = datetime.fromisoformat(last)
        elapsed = datetime.now() - last_dt
        if elapsed < timedelta(minutes=COOLDOWN_MINUTES):
            left = timedelta(minutes=COOLDOWN_MINUTES) - elapsed
            await message.answer(
                f"@{username}, ты уже крутил, открой позже.\n"
                f"⏳ Ждать ещё: {format_cooldown(int(left.total_seconds()))}"
            )
            return

    cur.execute("UPDATE users SET last_card = ? WHERE user_id = ?", (datetime.now().isoformat(), uid))
    db.commit()

    for _ in range(level):
        c = roll_card()
        cur.execute("INSERT INTO inventory (user_id, card_name) VALUES (?, ?)", (uid, c["name"]))
        db.commit()

        cur.execute("SELECT rowid FROM inventory WHERE user_id = ? AND card_name = ? ORDER BY rowid DESC LIMIT 1", (uid, c["name"]))
        inv_id = cur.fetchone()[0]

        caption = (
            f"@{username}, вам выпала:\n"
            f"🎴 {c['name']}\n"
            f"{c['rarity']} | 💰 Цена: {c['price']} монет"
        )

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"💰 Продать: {c['name']} ({c['price']})",
                callback_data=f"sell_card_{inv_id}_{c['price']}"
            )],
            [InlineKeyboardButton(
                text="🎰 Casino",
                callback_data=f"open_casino_{uid}"
            )],
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
        await call.answer("❌ Эта карточка уже продана.", show_alert=True)
        return

    cur.execute("DELETE FROM inventory WHERE rowid = ?", (inv_id,))
    cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (price, uid))
    db.commit()

    await call.message.edit_caption(
        caption=f"✅ Продано: {row[0]} за {price} монет",
        reply_markup=None
    )
    await call.answer(f"Получено {price} монет!")


# ==== CASINO ====
@dp.message(Command("casino"))
async def casino_command(message: types.Message):
    uid = message.from_user.id
    username = message.from_user.username or message.from_user.full_name or "Игрок"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲 Color Dice", callback_data=f"casino_color_{uid}")],
        [InlineKeyboardButton(text="💣 Минёр", callback_data=f"casino_miner_{uid}")],
        [InlineKeyboardButton(text="🔙 Закрыть", callback_data=f"casino_close_{uid}")],
    ])
    await message.answer(
        f"🎰 *Casino* — @{username}\n\n"
        f"Выбери игру:",
        reply_markup=kb,
        parse_mode="Markdown"
    )


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
    await call.message.answer(
        f"🎰 *Casino* — @{username}\n\n"
        f"Выбери игру:",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    await call.answer()


@dp.callback_query(F.data.startswith("casino_close_"))
async def casino_close(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Это не твоё меню!", show_alert=True)
        return
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.answer()


# ==== COLOR DICE ====
@dp.callback_query(F.data.startswith("casino_color_"))
async def casino_color(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Это не твоё меню!", show_alert=True)
        return
    username = call.from_user.username or call.from_user.full_name or "Игрок"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔵 Синий",       callback_data=f"col_blue_{uid}"),
            InlineKeyboardButton(text="🔴 Красный",     callback_data=f"col_red_{uid}"),
        ],
        [
            InlineKeyboardButton(text="🟡 Жёлтый",      callback_data=f"col_yellow_{uid}"),
            InlineKeyboardButton(text="🟢 Зелёный",     callback_data=f"col_green_{uid}"),
        ],
        [
            InlineKeyboardButton(text="🟣 Фиолетовый",  callback_data=f"col_purple_{uid}"),
            InlineKeyboardButton(text="🟠 Оранжевый",   callback_data=f"col_orange_{uid}"),
        ],
    ])
    await call.message.edit_text(
        f"🎲 *Color Dice* — @{username}\n\n"
        "Правила:\n"
        "🎉 1 совпадение → выигрыш ×2\n"
        "🎉 4 совпадения → выигрыш ×4\n"
        "❌ 0, 2, 3 совпадения → проигрыш\n\n"
        "Выбери цвет:",
        reply_markup=kb,
        parse_mode="Markdown"
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
        await call.answer("Это не твоя игра!", show_alert=True)
        return

    chosen = next((c for c in COLORS if c["code"] == code), None)
    if not chosen:
        await call.answer("Ошибка цвета", show_alert=True)
        return

    color_games[uid] = {"color": chosen, "state": "wait_bet"}

    await call.message.edit_text(
        f"🎲 Твой цвет: {chosen['emoji']} {chosen['name']}\n\n"
        f"💰 Напиши сумму ставки числом (например 100).\n"
        f"Отмена — /cancel"
    )
    await call.answer()


# ==== MINER ====
@dp.callback_query(F.data.startswith("casino_miner_"))
async def casino_miner(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Это не твоё меню!", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Сделать ставку", callback_data=f"miner_bet_{uid}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"casino_back_{uid}")],
    ])
    await call.message.edit_text(
        "💣 *Минёр*\n\n"
        "📋 *Правила:*\n"
        "• Поле из 9 клеток\n"
        "• Спрятано 2-6 мин\n"
        "• Открывай клетки и увеличивай множитель\n"
        "• Попадёшь на мину — теряешь ставку\n"
        "• Жми «💰 Забрать», чтобы забрать выигрыш\n\n"
        "📈 *Множители:*\n"
        "1 клетка → ×1.2\n"
        "2 клетки → ×1.5\n"
        "3 клетки → ×2\n"
        "4 клетки → ×3\n"
        "5 клеток → ×5\n"
        "6 клеток → ×8\n"
        "7 клеток → ×15\n"
        "8 клеток → ×30\n\n"
        "🎁 *Особый приз:* если выпадет 6 мин и ты откроешь все 3 безопасные клетки — получишь секретную карточку «Топ 1 Минёр»!",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    await call.answer()


@dp.callback_query(F.data.startswith("casino_back_"))
async def casino_back(call: types.CallbackQuery):
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
    await call.message.edit_text(
        f"🎰 *Casino* — @{username}\n\n"
        f"Выбери игру:",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    await call.answer()


@dp.callback_query(F.data.startswith("miner_bet_"))
async def miner_bet_request(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Это не твоё меню!", show_alert=True)
        return
    miner_games[uid] = {"state": "wait_bet"}
    await call.message.edit_text(
        "💣 *Минёр*\n\n"
        "💰 Напиши сумму ставки числом (например 100).\n"
        "Отмена — /cancel",
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
        await call.answer("Это не твоя игра!", show_alert=True)
        return
    await call.answer("Эта клетка уже открыта.")


@dp.callback_query(F.data.startswith("miner_open_"))
async def miner_open(call: types.CallbackQuery):
    parts = call.data.split("_")
    idx = int(parts[2])
    uid = int(parts[3])
    if call.from_user.id != uid:
        await call.answer("Это не твоя игра!", show_alert=True)
        return

    game = miner_games.get(uid)
    if not game or game.get("state") != "playing":
        await call.answer("Игра не активна.", show_alert=True)
        return

    if idx in game["opened"]:
        await call.answer("Уже открыто.")
        return

    if idx in game["mines"]:
        game["state"] = "finished"
        await call.message.edit_text(
            f"💣 *Минёр*\n\n"
            f"💰 Ставка: {game['bet']} монет\n"
            f"💥 Ты попал на мину!\n\n"
            f"{' '.join(render_miner_field(game['opened'], game['mines'], reveal_all=True))}\n\n"
            f"❌ *Ты проиграл {game['bet']} монет.*",
            parse_mode="Markdown"
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
        if len(game["mines"]) == 6 and count == 3:
            cur.execute("INSERT INTO inventory (user_id, card_name) VALUES (?, ?)", (uid, "Топ 1 Минёр"))
            special_card = True

        db.commit()

        text = (
            f"💣 *Минёр*\n\n"
            f"💰 Ставка: {game['bet']} монет\n"
            f"🎉 Ты открыл все безопасные клетки!\n"
            f"📈 Множитель: ×{multiplier}\n\n"
            f"{' '.join(render_miner_field(game['opened'], game['mines'], reveal_all=True))}\n\n"
            f"💰 *Выигрыш: {win} монет!*"
        )
        if special_card:
            text += "\n\n🎁 *ТЕБЕ ВЫПАЛА СЕКРЕТНАЯ КАРТОЧКА «Топ 1 Минёр»!*"

        await call.message.edit_text(text, parse_mode="Markdown")

        if special_card:
            try:
                card_data = next((c for c in cards if c["name"] == "Топ 1 Минёр"), None)
                if card_data:
                    photo = FSInputFile(card_data["file"])
                    await bot.send_photo(
                        uid,
                        photo,
                        caption=(
                            f"🎁 *Секретная награда!*\n\n"
                            f"🎴 {card_data['name']}\n"
                            f"{card_data['rarity']} | 💰 Цена: {card_data['price']} монет"
                        ),
                        parse_mode="Markdown"
                    )
            except Exception:
                pass

        del miner_games[uid]
        await call.answer("🎉 Победа!")
        return

    await call.message.edit_text(
        f"💣 *Минёр*\n"
        f"💰 Ставка: {game['bet']} монет\n"
        f"🟢 Открыто: {count}\n"
        f"📈 Множитель: ×{multiplier}\n"
        f"💵 Заберёшь: {potential} монет",
        reply_markup=miner_keyboard(game["opened"], game["mines"], uid),
        parse_mode="Markdown"
    )
    await call.answer(f"Открыто: {count} | ×{multiplier}")


@dp.callback_query(F.data.startswith("miner_cashout_"))
async def miner_cashout(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Это не твоя игра!", show_alert=True)
        return

    game = miner_games.get(uid)
    if not game or game.get("state") != "playing":
        await call.answer("Игра не активна.", show_alert=True)
        return

    count = len(game["opened"])
    if count == 0:
        await call.answer("Сначала открой хотя бы одну клетку!", show_alert=True)
        return

    multiplier = MINER_MULTIPLIERS.get(count, 30.0)
    win = int(game["bet"] * multiplier)

    cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (win, uid))
    db.commit()

    game["state"] = "finished"
    del miner_games[uid]

    await call.message.edit_text(
        f"💣 *Минёр*\n\n"
        f"💰 Ставка: {game['bet']} монет\n"
        f"🟢 Открыто: {count}\n"
        f"📈 Множитель: ×{multiplier}\n\n"
        f"✅ *Ты забрал {win} монет!*",
        parse_mode="Markdown"
    )
    await call.answer(f"Получено {win} монет!")


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
    if cancelled:
        await message.answer("❌ Игра отменена.")
    else:
        await message.answer("У тебя нет активной игры.")


# ==== Ввод ставки (число) ====
@dp.message(F.text.regexp(r"^\d+$"))
async def handle_bet(message: types.Message):
    uid = message.from_user.id

    # Color Dice
    game = color_games.get(uid)
    if game and game.get("state") == "wait_bet":
        bet = int(message.text)
        if bet <= 0:
            await message.answer("❌ Ставка должна быть больше 0.")
            return
        balance, _, _, _ = get_user(uid, message.from_user.username)
        if balance < bet:
            await message.answer(f"❌ Не хватает монет. У тебя {balance}, нужно {bet}.")
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
            text = (
                f"🎲 Твой цвет: {chosen['emoji']} {chosen['name']}\n"
                f"💰 Ставка: {bet} монет\n\n"
                f"{' '.join(progressive)}"
            )
            await msg.edit_text(text)
            await asyncio.sleep(0.9)

        if matches == 1:
            win = bet * 2
            cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (win, uid))
            db.commit()
            result_text = (
                f"🎲 Твой цвет: {chosen['emoji']} {chosen['name']}\n"
                f"💰 Ставка: {bet} монет\n\n"
                f"{' '.join(progressive)}\n\n"
                f"Совпадений: {matches}\n"
                f"🎉 *Поздравляю, ты выиграл {win} монет!* (×2)"
            )
        elif matches == 4:
            win = bet * 4
            cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (win, uid))
            db.commit()
            result_text = (
                f"🎲 Твой цвет: {chosen['emoji']} {chosen['name']}\n"
                f"💰 Ставка: {bet} монет\n\n"
                f"{' '.join(progressive)}\n\n"
                f"Совпадений: {matches}\n"
                f"🎉 *ДЖЕКПОТ! Ты выиграл {win} монет!* (×4)"
            )
        else:
            result_text = (
                f"🎲 Твой цвет: {chosen['emoji']} {chosen['name']}\n"
                f"💰 Ставка: {bet} монет\n\n"
                f"{' '.join(progressive)}\n\n"
                f"Совпадений: {matches}\n"
                f"❌ *Увы, ты проиграл {bet} монет.*"
            )
        await msg.edit_text(result_text, parse_mode="Markdown")
        return

    # Минёр
    game = miner_games.get(uid)
    if game and game.get("state") == "wait_bet":
        bet = int(message.text)
        if bet <= 0:
            await message.answer("❌ Ставка должна быть больше 0.")
            return
        balance, _, _, _ = get_user(uid, message.from_user.username)
        if balance < bet:
            await message.answer(f"❌ Не хватает монет. У тебя {balance}, нужно {bet}.")
            return

        cur.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (bet, uid))
        db.commit()

        mines_count = random.randint(2, 6)
        mines_set = set(random.sample(range(9), mines_count))

        miner_g
