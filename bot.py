import os
import logging

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

ACTION_COMMANDS = {
    # Старые
    "выпить":            "🍺 Выпил с {user}",
    "заморозить":        "❄️ Заморозил {user}",
    "трахнуть":          "😏 Трахнул {user}",
    "кончить":           "💦 Кончил на {user}",
    "принять участие":   "🫂 Принял участие с {user}",
    "убиться":           "💀 Убил {user}",
    "брызнуть":          "💧 Брызнул на {user}",
    "набухаться":        "🍻 Набухался с {user}",
    "разрубить":         "🪓 Разрубил {user}",
    "отсексафонить":     "🎷 Отсексафонил {user}",
    "напердеть":         "💨 Напердел на {user}",
    "нарисовать":        "🎨 Нарисовал {user}",
    "обмануть":          "🎭 Обманул {user}",
    "взломать":          "💻 Взломал {user}",
    # Новые
    "дать наркоты":      "💊 Дал наркоты {user}",
    "покурить":          "🚬 Покурил с {user}",
    "оплодотворить":     "🧬 Оплодотворил {user}",
    "осеменить":         "🌱 Осеменил {user}",
    "напоить":           "🍷 Напоил {user}",
    "убить":             "🔪 Убил {user}",
    "задушить":          "🤏 Задушил {user}",
    "застрелить":        "🔫 Застрелил {user}",
    "простить":          "🕊 Простил {user}",
    "отомстить":         "😈 Отомстил {user}",
    "перепрыгнуть":      "🦘 Перепрыгнул {user}",
    "жмякнуть":          "👆 Жмякнул {user}",
    "потрогать":         "🤚 Потрогал {user}",
    "изнасиловать":      "💀 Изнасиловал {user}",
    "извиниться":        "🙏 Извинился перед {user}",
    "нокаутировать":     "💫 Нокаутировал {user}",
    "ударить":           "👊 Ударил {user}",
}


@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "👋 Бот активен.\n\n"
        "Команды-действия (работают для всех):\n"
        "Напиши реплаем на сообщение или @username.\n\n"
        "Например:\n"
        "• Выпить @username\n"
        "• Реплай + Ударить"
    )


@dp.message(F.text)
async def action_command(message: types.Message):
    text = message.text.strip()
    if not text:
        return
    if text.startswith("/"):
        return

    low = text.lower()

    matched = None
    for cmd in ACTION_COMMANDS:
        if low == cmd or low.startswith(cmd + " ") or low.startswith(cmd + "@"):
            matched = cmd
            break
    if not matched:
        return

    target_mention = None

    # 1) Реплай на сообщение
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
        if target_user.id == message.from_user.id:
            target_mention = "сам с собой"
        elif target_user.username:
            target_mention = f"@{target_user.username}"
        else:
            target_mention = target_user.full_name

    # 2) Упоминание @username в тексте
    if not target_mention:
        rest = text[len(matched):].strip()
        if rest.startswith("@"):
            uname = rest.split()[0].lstrip("@")
            target_mention = f"@{uname}"

    # 3) Если ничего — сам с собой
    if not target_mention:
        target_mention = "сам с собой"

    result = ACTION_COMMANDS[matched].format(user=target_mention)
    await message.reply(result)


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
