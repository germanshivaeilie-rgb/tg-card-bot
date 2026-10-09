import os
import logging

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
DEV_ID = 1473258682

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

ACTION_COMMANDS = {
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
}


@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "👋 Бот активен.\n\n"
        "Команды-действия:\n"
        "• Выпить\n• Заморозить\n• Трахнуть\n• Кончить\n"
        "• Принять участие\n• Убиться\n• Брызнуть\n• Набухаться\n"
        "• Разрубить\n• Отсексафонить\n• Напердеть\n• Нарисовать\n"
        "• Обмануть\n• Взломать\n\n"
        "Как использовать:\n"
        "• Ответь (реплаем) на сообщение человека и напиши команду\n"
        "• Или напиши команду и @username\n"
        "• Или просто команду — сделаешь сам с собой"
    )


@dp.message(F.text.regexp(r"(?i)^(выпить|заморозить|трахнуть|кончить|принять участие|убиться|брызнуть|набухаться|разрубить|отсексафонить|напердеть|нарисовать|обмануть|взломать)(\s|$)"))
async def action_command(message: types.Message):
    if message.from_user.id != DEV_ID:
        return

    text = message.text.strip()
    low = text.lower()

    matched = None
    for cmd in ACTION_COMMANDS:
        if low.startswith(cmd):
            matched = cmd
            break
    if not matched:
        return

    target_mention = None

    # 1) Реплай на сообщение
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
        if target_user.username:
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
