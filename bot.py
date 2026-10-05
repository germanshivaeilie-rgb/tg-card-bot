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
COOLDOWN_MINUTES = 1

FONT_PATH = "Roboto-Italic-VariableFont_wdth,wght.ttf"
BG_PATH = "ChatGPT Image 5 окт. 2026 г., 09_26_45.png"

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

RARITY_CHANCES = {
    "⚪ Обычная":     60,
    "🔷 Редкая":      20,
    "🔮 Эпическая":   10,
    "👑 Легендарная": 6,
    "♣️ Секретная":   4,
}

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

    size = int(h * 0.55)
    if avatar is None:
        avatar = Image.new("RGBA", (size, size), (60, 60, 80, 255))
    else:
        avatar = avatar.resize((size, size))

    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    avatar.putalpha(mask)

    avatar_x = int(w * 0.075)
    avatar_y = (h - size) // 2
    bg.paste(avatar, (avatar_x, avatar_y), avatar)

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
        "/mycards — инвентарь\n"
        "/balance — баланс монет\n"
        "/sell — продать карточку\n"
        "/sellall — продать всё\n"
        "/upgrade — улучшение\n"
        "/profile — профиль с аватаркой\n"
        "/top — топ-3 игрока\n"
        "/trade @username Название — трейд\n"
        "/accept, /decline — принять/отклонить"
    )


@dp.message(Command("card"))
async def card(message: types.Message):
    uid = message.from_user.id
    username = message.from_user.username or message.from_user.full_name or "Игрок"
    balance, last, level = get_user(uid, message.from_user.username)

    if last:
        last_dt = datetime.fromisoformat(last)
        elapsed = datetime.now() - last_dt
        if elapsed < timedelta(minutes=COOLDOWN_MINUTES):
            left = timedelta(minutes=COOLDOWN_MINUTES) - elapsed
            await message.answer(f"⏳ Подожди ещё {format_cooldown(int(left.total_seconds()))}.")
            return

    for _ in range(level):
        c = roll_card()
        cur.execute("INSERT INTO inventory (user_id, card_name) VALUES (?, ?)", (uid, c["name"]))
        photo = FSInputFile(c["file"])
        caption = (
            f"@{username}, вам выпала:\n"
            f"🎴 {c['name']}\n"
            f"{c['rarity']} | 💰 Цена: {c['price']} монет"
        )
        await message.answer_photo(photo, caption=caption)

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
    cur.execute("SELECT COUNT(*) FROM users WHERE balance > ?", (balance,))
    place = cur.fetchone()[0] + 1

    try:
        img = await make_profile_image(uid, message.from_user.username, balance, place, level, total)
        photo = BufferedInputFile(img.read(), filename="profile.png")
        await message.answer_photo(photo)
    except Exception as e:
        await message.answer(
            f"👤 *Профиль*\n\n"
            f"💰 Баланс: {balance}\n⬆️ Уровень: {level}\n"
            f"🎴 Карт: {total}\n🏆 Место: #{place}\n\n"
            f"_Ошибка картинки: {e}_",
            parse_mode="Markdown"
        )


@dp.message(Command("top"))
async def top(message: types.Message):
    cur.execute("SELECT username, balance FROM users ORDER BY balance DESC LIMIT 3")
    rows = cur.fetchall()
    if not rows:
        await message.answer("Пока никто не играл.")
        return

    medals = ["🥇", "🥈", "🥉"]
    text = "🏆 *Топ-3 игрока по балансу:*\n\n"
    for i, (uname, bal) in enumerate(rows):
        name = f"@{uname}" if uname else f"Игрок #{i+1}"
        text += f"{medals[i]} *{name}*\n"
        text += f"      💰 Баланс: {bal} монет\n\n"

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


@dp.message(Command("sellall"))
async def sellall(message: types.Message):
    uid = message.from_user.id
    cur.execute("SELECT card_name, COUNT(*) FROM inventory WHERE user_id = ? GROUP BY card_name", (uid,))
    rows = cur.fetchall()
    if not rows:
        await message.answer("❌ У тебя нет карточек.")
        return
    total_sum = 0
    text = "💰 *Что будет продано:*\n\n"
    for name, cnt in rows:
        card_data = next((c for c in cards if c["name"] == name), None)
        if not card_data:
            continue
        subtotal = card_data["price"] * cnt
        total_sum += subtotal
        text += f"• {name} × {cnt} = {subtotal} монет\n"
    text += f"\n💵 *Итого: {total_sum} монет*"

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Подтвердить", callback_data="sellall_yes"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data="sellall_no"),
    ]])
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")


@dp.callback_query(F.data.startswith("sellall_"))
async def sellall_callback(call: types.CallbackQuery):
    uid = call.from_user.id
    if call.data == "sellall_no":
        await call.message.edit_text("❌ Продажа отменена.")
        await call.answer()
        return
    cur.execute("SELECT card_name, COUNT(*) FROM inventory WHERE user_id = ? GROUP BY card_name", (uid,))
    rows = cur.fetchall()
    if not rows:
        await call.answer("Инвентарь пуст!", show_alert=True)
        return
    total_sum = 0
    for name, cnt in rows:
        card_data = next((c for c in cards if c["name"] == name), None)
        if not card_data:
            continue
        total_sum += card_data["price"] * cnt
    cur.execute("DELETE FROM inventory WHERE user_id = ?", (uid,))
    cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (total_sum, uid))
    db.commit()
    await call.message.edit_text(f"✅ Продано всё за {total_sum} монет.")
    await call.answer("Готово!")


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
        InlineKeyboardButton(text="❌ Отклонить", callback_data="upg_no"),
    ]])
    await message.answer(
        f"⬆️ *Улучшение до уровня {next_level}*\n\n"
        f"Будет выдавать {next_level} карты за /card\n\n"
        f"💰 Цена: {price} монет\n💳 У тебя: {balance} монет",
        reply_markup=kb, parse_mode="Markdown"
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


@dp.message(Command("trade"))
async def trade(message: types.Message):
    uid = message.from_user.id
    sender_name = message.from_user.username or message.from_user.full_name
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
            f"🤝 *Тебе предложили трейд!*\n\n"
            f"👤 От: @{sender_name}\n"
            f"🎴 Карточка: *{card_name}*\n\n"
            f"Если согласен — /accept\n"
            f"Если нет — /decline",
            parse_mode="Markdown"
        )
    except Exception:
        pass


@dp.message(Command("accept"))
async def accept(message: types.Message):
    uid = message.from_user.id
    accepter_name = message.from_user.username or message.from_user.full_name
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
    await message.answer(f"✅ Ты принял трейд и получил карточку *{card_name}*.", parse_mode="Markdown")
    try:
        await bot.send_message(
            from_id,
            f"✅ *Твой трейд принят!*\n\n"
            f"👤 @{accepter_name} принял карточку *{card_name}*.",
            parse_mode="Markdown"
        )
    except Exception:
        pass


@dp.message(Command("decline"))
async def decline(message: types.Message):
    uid = message.from_user.id
    decliner_name = message.from_user.username or message.from_user.full_name
    cur.execute("SELECT rowid, from_id, card_name FROM trades WHERE to_id = ? ORDER BY rowid DESC LIMIT 1", (uid,))
    row = cur.fetchone()
    if not row:
        await message.answer("❌ Нет активных предложений.")
        return
    rowid, from_id, card_name = row
    cur.execute("DELETE FROM trades WHERE rowid = ?", (rowid,))
    db.commit()
    await message.answer(f"❌ Трейд на *{card_name}* отклонён.", parse_mode="Markdown")
    try:
        await bot.send_message(
            from_id,
            f"❌ *Твой трейд отклонён.*\n\n"
            f"👤 @{decliner_name} отказался от карточки *{card_name}*.",
            parse_mode="Markdown"
        )
    except Exception:
        pass


async def main():
    await dp.start_polling(bot)


asyncio.run(main())
