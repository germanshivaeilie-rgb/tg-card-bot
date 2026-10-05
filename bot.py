import asyncio
import os
import random
import sqlite3
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

BOT_TOKEN = os.getenv("BOT_TOKEN")
COOLDOWN_MINUTES = 1  # 1 минута

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# ==== ШАНСЫ РЕДКОСТЕЙ (в сумме 100) ====
RARITY_CHANCES = {
    "⚪ Обычная":     60,
    "🔷 Редкая":      20,
    "🔮 Эпическая":   10,
    "👑 Легендарная": 6,
    "♣️ Секретная":   4,  # суммарно на все секретные
}

# ==== КАРТОЧКИ (без "chance" — он теперь у редкости) ====
cards = [
    {"name": "Засохшая лилия",        "rarity": "⚪ Обычная",     "price": 100,   "file": "Засохшая лилия на чёрном фоне (1).png"},
    {"name": "Поедатель чижика",      "rarity": "🔷 Редкая",      "price": 500,   "file": "IMG_20261004_205356_295.jpg"},
    {"name": "Грустный хлеб",         "rarity": "🔮 Эпическая",   "price": 1000,  "file": "ChatGPT Image 22 сент. 2026 г., 22_04_28.png"},
    {"name": "Новая легендарка",      "rarity": "👑 Легендарная", "price": 10000, "file": "IMG_20261004_211521_420.jpg"},
    {"name": "Секретный трансформер", "rarity": "♣️ Секретная",   "price": 67000, "file": "ChatGPT Image 27 сент. 2026 г., 13_10_10.png"},
    {"name": "Moggфон",               "rarity": "♣️ Секретная",   "price": 50000, "file": "IMG_20261004_211400_997.jpg"},
]

UPGRADE_PRICES = {2: 100, 3: 1000}
MAX_LEVEL = 3

# ==== БАЗА ДАННЫХ ====
db = sqlite3.connect("game.db")
cur = db.cursor()
cur.execute("""CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    balance INTEGER DEFAULT 0,
    last_card TEXT,
    level INTEGER DEFAULT 1
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


def roll_card():
    """Выбирает редкость по шансам, потом случайную карту внутри неё."""
    # 1. Выбираем редкость
    total = sum(RARITY_CHANCES.values())
    r = random.uniform(0, total)
    upto = 0
    chosen_rarity = None
    for rarity, chance in RARITY_CHANCES.items():
        upto += chance
        if r <= upto:
            chosen_rarity = rarity
            break

    # 2. Среди карт этой редкости выбираем случайную
    pool = [c for c in cards if c["rarity"] == chosen_rarity]
    if not pool:
        pool = cards  # на всякий случай
    return random.choice(pool)


def get_user(uid, username=None):
    cur.execute("SELECT balance, last_card, level FROM users WHERE user_id = ?", (uid,))
    row = cur.fetchone()
    if not row:
        cur.execute("INSERT INTO users (user_id, username) VALUES (?, ?)", (uid, username))
        db.commit()
        return 0, None, 1
    if username:
        cur.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, uid))
        db.commit()
    return row[0], row[1], row[2]


def format_cooldown(seconds_left):
    mins = seconds_left // 60
    secs = seconds_left % 60
    if mins > 0:
        return f"{mins} мин {secs} сек"
    return f"{secs} сек"


@dp.message(Command("start"))
async def start(message: types.Message):
    get_user(message.from_user.id, message.from_user.username)
    await message.answer(
        "🎴 Привет! Я бот-коллекционер карточек.\n\n"
        "/card — выбить карточку\n"
        "/mycards — инвентарь\n"
        "/balance — баланс монет\n"
        "/sell <название> — продать карточку\n"
        "/upgrade — купить улучшение\n"
        "/profile — профиль\n"
        "/top — топ-3 игрока\n"
        "/trade @username НазваниеКарты — предложить обмен\n"
        "/accept, /decline — принять/отклонить трейд"
    )


@dp.message(Command("card"))
async def card(message: types.Message):
    uid = message.from_user.id
    balance, last, level = get_user(uid, message.from_user.username)

    if last:
        last_dt = datetime.fromisoformat(last)
        elapsed = datetime.now() - last_dt
        if elapsed < timedelta(minutes=COOLDOWN_MINUTES):
            left = timedelta(minutes=COOLDOWN_MINUTES) - elapsed
            seconds_left = int(left.total_seconds())
            await message.answer(f"⏳ Подожди ещё {format_cooldown(seconds_left)}.")
            return

    count = level
    for _ in range(count):
        c = roll_card()
        cur.execute("INSERT INTO inventory (user_id, card_name) VALUES (?, ?)", (uid, c["name"]))
        photo = FSInputFile(c["file"])
        caption = f"🎴 *{c['name']}*\nРедкость: {c['rarity']}\n💰 Цена: {c['price']} монет"
        await message.answer_photo(photo, caption=caption, parse_mode="Markdown")

    cur.execute("UPDATE users SET last_card = ? WHERE user_id = ?", (datetime.now().isoformat(), uid))
    db.commit()


@dp.message(Command("mycards"))
async def mycards(message: types.Message):
    uid = message.from_user.id
    cur.execute("SELECT card_name FROM inventory WHERE user_id = ?", (uid,))
    rows = cur.fetchall()
    if not rows:
        await message.answer("У тебя пока нет карточек. Напиши /card")
        return
    counts = {}
    for (name,) in rows:
        counts[name] = counts.get(name, 0) + 1
    text = "🎒 *Твой инвентарь:*\n\n"
    for name, cnt in counts.items():
        text += f"• {name} × {cnt}\n"
    await message.answer(text, parse_mode="Markdown")


@dp.message(Command("balance"))
async def balance_cmd(message: types.Message):
    balance, _, _ = get_user(message.from_user.id, message.from_user.username)
    await message.answer(f"💰 У тебя {balance} монет")


@dp.message(Command("profile"))
async def profile(message: types.Message):
    uid = message.from_user.id
    balance, _, level = get_user(uid, message.from_user.username)
    cur.execute("SELECT COUNT(*) FROM inventory WHERE user_id = ?", (uid,))
    total = cur.fetchone()[0]
    await message.answer(
        f"👤 *Профиль*\n\n"
        f"💰 Баланс: {balance} монет\n"
        f"⬆️ Уровень: {level} (карт за /card: {level})\n"
        f"🎴 Карт в инвентаре: {total}",
        parse_mode="Markdown"
    )


@dp.message(Command("top"))
async def top(message: types.Message):
    cur.execute("SELECT username, balance FROM users ORDER BY balance DESC LIMIT 3")
    rows = cur.fetchall()
    if not rows:
        await message.answer("Пока никто не играл.")
        return
    text = "🏆 *Топ-3 игрока по балансу:*\n\n"
    medals = ["🥇", "🥈", "🥉"]
    for i, (uname, bal) in enumerate(rows):
        name = f"@{uname}" if uname else "Аноним"
        text += f"{medals[i]} {name} — {bal} монет\n"
    await message.answer(text, parse_mode="Markdown")


@dp.message(Command("sell"))
async def sell(message: types.Message):
    uid = message.from_user.id
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Использование: /sell Название карточки")
        return
    name = args[1].strip()
    cur.execute("SELECT rowid FROM inventory WHERE user_id = ? AND card_name = ? LIMIT 1", (uid, name))
    row = cur.fetchone()
    if not row:
        await message.answer("❌ Такой карточки у тебя нет.")
        return
    card_data = next((c for c in cards if c["name"].lower() == name.lower()), None)
    if not card_data:
        await message.answer("❌ Неизвестная карточка.")
        return
    cur.execute("DELETE FROM inventory WHERE rowid = ?", (row[0],))
    cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (card_data["price"], uid))
    db.commit()
    await message.answer(f"✅ Продано: {card_data['name']} за {card_data['price']} монет")


# ==== АПГРЕЙД ====
@dp.message(Command("upgrade"))
async def upgrade(message: types.Message):
    uid = message.from_user.id
    balance, _, level = get_user(uid, message.from_user.username)

    if level >= MAX_LEVEL:
        await message.answer("⛔ У тебя уже максимальный уровень (3).")
        return

    next_level = level + 1
    price = UPGRADE_PRICES[next_level]

    if balance < price:
        await message.answer(f"❌ Не хватает монет. Нужно {price}, у тебя {balance}.")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"upg_yes_{next_level}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"upg_no"),
    ]])

    await message.answer(
        f"⬆️ *Улучшение до уровня {next_level}*\n\n"
        f"Будет выдавать {next_level} карты за /card\n\n"
        f"💰 Цена: {price} монет\n"
        f"💳 У тебя: {balance} монет",
        reply_markup=kb,
        parse_mode="Markdown"
    )


@dp.callback_query(F.data.startswith("upg_"))
async def upgrade_callback(call: types.CallbackQuery):
    uid = call.from_user.id
    balance, _, level = get_user(uid, call.from_user.username)

    if call.data == "upg_no":
        await call.message.edit_text("❌ Улучшение отменено.")
        await call.answer()
        return

    next_level = int(call.data.split("_")[2])
    price = UPGRADE_PRICES[next_level]

    if level >= next_level:
        await call.answer("Ты уже купил это улучшение!", show_alert=True)
        return
    if balance < price:
        await call.answer("Недостаточно монет!", show_alert=True)
        return

    cur.execute("UPDATE users SET balance = balance - ?, level = ? WHERE user_id = ?", (price, next_level, uid))
    db.commit()
    await call.message.edit_text(f"✅ Улучшение куплено! Теперь ты уровня {next_level} — выпадает {next_level} карты за /card.")
    await call.answer("Улучшение активировано!")


# ==== ТРЕЙДЫ ====
@dp.message(Command("trade"))
async def trade(message: types.Message):
    uid = message.from_user.id
    args = message.text.split(maxsplit=2)

    if len(args) < 3:
        await message.answer("Использование: /trade @username НазваниеКарты")
        return

    target_username = args[1].lstrip("@")
    card_name = args[2].strip()

    cur.execute("SELECT user_id, username FROM users WHERE username = ?", (target_username,))
    row = cur.fetchone()
    if not row:
        await message.answer("❌ Игрок не найден. Он должен хоть раз написать боту.")
        return

    target_id, target_uname = row
    if target_id == uid:
        await message.answer("❌ Нельзя торговать с самим собой.")
        return

    cur.execute("SELECT rowid FROM inventory WHERE user_id = ? AND card_name = ? LIMIT 1", (uid, card_name))
    if not cur.fetchone():
        await message.answer(f"❌ У тебя нет карточки «{card_name}».")
        return

    cur.execute("INSERT INTO trades (from_id, to_id, card_name) VALUES (?, ?, ?)", (uid, target_id, card_name))
    db.commit()

    await message.answer(f"✅ Предложение отправлено @{target_uname}.")
    try:
        await bot.send_message(
            target_id,
            f"🎁 @{message.from_user.username or 'Игрок'} предлагает тебе карточку «{card_name}».\n\n"
            f"Принять: /accept\nОтклонить: /decline"
        )
    except Exception:
        pass


@dp.message(Command("accept"))
async def accept(message: types.Message):
    uid = message.from_user.id
    cur.execute("SELECT rowid, from_id, card_name FROM trades WHERE to_id = ? ORDER BY rowid DESC LIMIT 1", (uid,))
    row = cur.fetchone()
    if not row:
        await message.answer("❌ Нет активных предложений.")
        return
    rowid, from_id, card_name = row

    cur.execute("SELECT rowid FROM inventory WHERE user_id = ? AND card_name = ? LIMIT 1", (from_id, card_name))
    src = cur.fetchone()
    if not src:
        cur.execute("DELETE FROM trades WHERE rowid = ?", (rowid,))
        db.commit()
        await message.answer("❌ У отправителя уже нет этой карточки.")
        return

    cur.execute("DELETE FROM inventory WHERE rowid = ?", (src[0],))
    cur.execute("INSERT INTO inventory (user_id, card_name) VALUES (?, ?)", (uid, card_name))
    cur.execute("DELETE FROM trades WHERE rowid = ?", (rowid,))
    db.commit()

    await message.answer(f"✅ Ты получил карточку «{card_name}».")
    try:
        await bot.send_message(from_id, f"✅ @{message.from_user.username or 'Игрок'} принял твой трейд «{card_name}».")
    except Exception:
        pass


@dp.message(Command("decline"))
async def decline(message: types.Message):
    uid = message.from_user.id
    cur.execute("SELECT rowid, from_id, card_name FROM trades WHERE to_id = ? ORDER BY rowid DESC LIMIT 1", (uid,))
    row = cur.fetchone()
    if not row:
        await message.answer("❌ Нет активных предложений.")
        return
    rowid, from_id, card_name = row
    cur.execute("DELETE FROM trades WHERE rowid = ?", (rowid,))
    db.commit()
    await message.answer("❌ Трейд отклонён.")
    try:
        await bot.send_message(from_id, f"❌ Трейд «{card_name}» отклонён.")
    except Exception:
        pass


async def main():
    await dp.start_polling(bot)


asyncio.run(main())
