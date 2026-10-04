import asyncio
import os
import random
import sqlite3
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.types import FSInputFile
from aiogram.filters import Command

BOT_TOKEN = os.getenv("BOT_TOKEN")
COOLDOWN_MINUTES = 60

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

cards = [
    {"name": "Вялая лилия",     "rarity": "⚪ Обычная",    "price": 1,     "file": "cards/1.jpg", "chance": 70},
    {"name": "Шоколадный глаз", "rarity": "🟢 Необычная",  "price": 100,   "file": "cards/2.jpg", "chance": 25},
    {"name": "Секретная",       "rarity": "🔴 Секретная",  "price": 67000, "file": "cards/3.jpg", "chance": 5},
]

db = sqlite3.connect("game.db")
cur = db.cursor()
cur.execute("""CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    balance INTEGER DEFAULT 0,
    last_card TEXT
)""")
cur.execute("""CREATE TABLE IF NOT EXISTS inventory (
    user_id INTEGER,
    card_name TEXT
)""")
db.commit()


def roll_card():
    total = sum(c["chance"] for c in cards)
    r = random.uniform(0, total)
    upto = 0
    for c in cards:
        upto += c["chance"]
        if r <= upto:
            return c
    return cards[0]


def get_user(uid):
    cur.execute("SELECT balance, last_card FROM users WHERE user_id = ?", (uid,))
    row = cur.fetchone()
    if not row:
        cur.execute("INSERT INTO users (user_id) VALUES (?)", (uid,))
        db.commit()
        return 0, None
    return row[0], row[1]


@dp.message(Command("start"))
async def start(message: types.Message):
    get_user(message.from_user.id)
    await message.answer(
        "🎴 Привет! Я бот-коллекционер карточек.\n\n"
        "/card — выбить карточку\n"
        "/mycards — мой инвентарь\n"
        "/balance — баланс монет\n"
        "/sell <название> — продать карточку"
    )


@dp.message(Command("card"))
async def card(message: types.Message):
    uid = message.from_user.id
    balance, last = get_user(uid)

    if last:
        last_dt = datetime.fromisoformat(last)
        if datetime.now() - last_dt < timedelta(minutes=COOLDOWN_MINUTES):
            left = timedelta(minutes=COOLDOWN_MINUTES) - (datetime.now() - last_dt)
            mins = int(left.total_seconds() // 60)
            await message.answer(f"⏳ Подожди ещё {mins} мин.")
            return

    c = roll_card()
    cur.execute("INSERT INTO inventory (user_id, card_name) VALUES (?, ?)", (uid, c["name"]))
    cur.execute("UPDATE users SET last_card = ? WHERE user_id = ?", (datetime.now().isoformat(), uid))
    db.commit()

    photo = FSInputFile(c["file"])
    caption = f"🎴 *{c['name']}*\nРедкость: {c['rarity']}\n💰 Цена: {c['price']} монет"
    await message.answer_photo(photo, caption=caption, parse_mode="Markdown")


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
    balance, _ = get_user(message.from_user.id)
    await message.answer(f"💰 У тебя {balance} монет")


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


async def main():
    await dp.start_polling(bot)


asyncio.run(main())
