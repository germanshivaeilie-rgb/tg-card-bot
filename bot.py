# -*- coding: utf-8 -*-
"""
🤖 УНИВЕРСАЛЬНЫЙ БОТ (aiogram 3.x): 🎴 карточки + 🎰 казино + ☢️ ивент/босс + 🎭 мафия + 🎬 RP-действия

Переменные окружения (Railway -> Variables):
  BOT_TOKEN     — токен от @BotFather (обязательно)
  MIN_PLAYERS / MAX_PLAYERS / REG_SECONDS / NIGHT_SECONDS / DAY_SECONDS / VOTE_SECONDS — настройки мафии
  RAILWAY_VOLUME_MOUNT_PATH — (необязательно) папка для базы и кэша видео

Порядок роутеров важен: мафия -> карточки -> RP (RP ловит любой текст, поэтому он последний).

ВАЖНО: для режима тишины в мафии боту нужны права админа в группе (удаление сообщений).
"""
import asyncio
import hashlib
import html
import io
import logging
import os
import random
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from aiogram import BaseMiddleware, Bot, Dispatcher, F, Router, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatMemberStatus, ChatType, ParseMode
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (BufferedInputFile, CallbackQuery, FSInputFile, InlineKeyboardButton,
                           InlineKeyboardMarkup, InputMediaAnimation, InputMediaPhoto, Message)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from PIL import Image, ImageDraw, ImageFont

try:
    from card_video import render_card_video, VIDEO_W, VIDEO_H, VIDEO_SECONDS
    USE_REVEAL_VIDEO = True
except Exception as _e:
    print("Видео выпадения отключено:", _e)
    USE_REVEAL_VIDEO = False
    VIDEO_W, VIDEO_H, VIDEO_SECONDS = 480, 640, 3.0

try:
    from card_video import (render_dice_video, DICE_W, DICE_H, DICE_SECONDS,
                            render_boss_transition, boss_clip_size, BOSS_CLIP_SECONDS)
    USE_EXTRA_VIDEO = True
except Exception as _e:
    print("Видео Color Dice / босса отключено:", _e)
    USE_EXTRA_VIDEO = False
    DICE_W, DICE_H, DICE_SECONDS, BOSS_CLIP_SECONDS = 480, 560, 4.7, 1.4

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("bot")

# ───────────────────────── ОБЩИЕ НАСТРОЙКИ ─────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise SystemExit("Не задана переменная BOT_TOKEN")

# По умолчанию HTML (его использует мафия). Там, где нужен Markdown (карточки),
# parse_mode передаётся явно.
bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
BOT_USERNAME = ""

# ── мафия
MIN_PLAYERS = int(os.getenv("MIN_PLAYERS", "4"))
MAX_PLAYERS = int(os.getenv("MAX_PLAYERS", "20"))
REG_SECONDS = int(os.getenv("REG_SECONDS", "120"))
NIGHT_SECONDS = int(os.getenv("NIGHT_SECONDS", "60"))
DAY_SECONDS = int(os.getenv("DAY_SECONDS", "90"))
VOTE_SECONDS = int(os.getenv("VOTE_SECONDS", "45"))
REVEAL_ROLES = True          # показывать роль погибшего/казнённого
ACTIONS_DURING_GAME = False  # False = RP-команды молчат, пока в чате идёт мафия
DEAD_CAN_CHAT = False        # True = мёртвые игроки тоже могут писать днём

# ── RP
ACTIONS_DEV_ONLY = False     # True — RP-команды работают только у DEV_ID

# ── карточки
COOLDOWN_MINUTES = 30
DEV_ID = 1473258682
TRADE_COOLDOWN_MIN = 5
BOSS_COOLDOWN_MIN = 30
BOSS_IDLE_MIN = 15
dev_mode = set()

FONT_PATH = "Roboto-Italic-VariableFont_wdth,wght.ttf"
BG_PATH = "ChatGPT Image 5 окт. 2026 г., 09_26_45.png"
BOSS_NORMAL = "ChatGPT Image 8 окт. 2026 г., 11_11_14.png"
BOSS_ATTACK = "ChatGPT Image 8 окт. 2026 г., 11_12_33.png"
BOSS_HURT = "ChatGPT Image 8 окт. 2026 г., 11_12_02.png"
BOSS_DEAD = "ChatGPT Image 8 окт. 2026 г., 11_03_00.png"

# Роутеры
router = Router()      # мафия
cr = Router()          # карточки / казино / ивент
rp = Router()          # RP-действия (самый последний — ловит любой текст)

MAIN_TEXT = (
    "🤖 Привет! Я универсальный бот: карточки, казино, мафия и RP-действия.\n\n"
    "🎴 КАРТОЧКИ\n"
    "/card — выбить карточку\n"
    "/cards — просмотр карточек\n"
    "/casino — 🎰 Casino\n"
    "/event — ☢️ Доходяги (ивент)\n"
    "/daily — 🎁 ежедневная награда\n"
    "/mycards — инвентарь\n"
    "/balance — баланс\n"
    "/tokens — сколько токенов\n"
    "/buytokens — купить токены\n"
    "/sell — продать карточку\n"
    "/sellall — продать всё\n"
    "/send @username сумма — передать монеты\n"
    "/trade @username — трейд картами\n"
    "/upgrade — улучшение\n"
    "/profile — профиль\n"
    "/top — топ-3\n"
    "/cancel — отмена действия\n\n"
    "🎭 МАФИЯ (в группе)\n"
    "/game — новая игра (набор)\n"
    "/startgame — начать сейчас\n"
    "/leave — выйти из набора\n"
    "/alive — кто жив\n"
    "/stop — остановить игру (админ)\n"
    "/rules — правила\n\n"
    "🎬 RP-ДЕЙСТВИЯ (ударить, обнять, выпить...) — список: /actions"
)

# ───────────────────────── МАФИЯ: РОЛИ ─────────────────────────
DON = "don"
MAFIA = "mafia"
COMMISSAR = "commissar"
DOCTOR = "doctor"
CIVILIAN = "civilian"
DECEIVER = "deceiver"
ALCOHOLIC = "alcoholic"

ROLE_TITLE = {
    DON: "🎩 Дон",
    MAFIA: "🔫 Мафия",
    COMMISSAR: "🕵️ Комиссар",
    DOCTOR: "💉 Доктор",
    CIVILIAN: "👨‍🌾 Мирный житель",
    DECEIVER: "🎭 Обманщик",
    ALCOHOLIC: "🍺 Алкаш",
}

ROLE_DESC = {
    DON: "Тебе решать, кто не проснётся этой ночью...\n\n"
         "Каждую ночь мафия голосует, кого убить. При равенстве голосов решает твой выбор.",
    MAFIA: "Каждую ночь вместе с Доном выбираешь жертву. "
           "Ночью можешь писать союзникам прямо сюда — бот перешлёт им твои сообщения.",
    COMMISSAR: "Каждую ночь выбираешь одно действие:\n"
               "🔍 Проверить — узнать, мафия игрок или нет.\n"
               "🔫 Застрелить — убить подозреваемого (рискованно: можно убить мирного).",
    DOCTOR: "Каждую ночь лечишь одного игрока. Если мафия выберет его — он выживет. "
            "Нельзя лечить одного и того же два раза подряд, себя — один раз за игру.",
    CIVILIAN: "Ночью ты спишь. Днём обсуждай, ищи мафию и голосуй.",
    DECEIVER: "Ты на стороне мафии, но сам никого не убиваешь.\n\n"
              "Ночью тебе доступно меню действий ВСЕХ ролей. Выбери любое — и в группе появится "
              "такое же сообщение, как от настоящей роли. На самом деле ничего не произойдёт. "
              "Запутывай город!",
    ALCOHOLIC: "Каждую ночь можешь увести кого-нибудь домой выпивать. Если мафия решит убить "
               "того, кого ты увёл, — она не найдёт его дома, и он выживет.",
}

KILLERS = {DON, MAFIA}
MAFIA_TEAM = {DON, MAFIA, DECEIVER}
ROLE_ACTION = {DON: "kill", MAFIA: "kill", COMMISSAR: "check", DOCTOR: "heal", ALCOHOLIC: "drink"}

KIND_PROMPT = {
    "kill": "🔪 Кого убьём этой ночью?",
    "check": "🔍 Кого проверим этой ночью?",
    "shoot": "🔫 Кого застрелим этой ночью?",
    "heal": "💉 Кого вылечим этой ночью?",
    "drink": "🍺 Кого уведёшь домой выпивать?",
}

ANNOUNCE = {
    "kill": "🔪 Мафия сделала свой выбор...",
    "check": "🕵️ Комиссар отправился на поиски мафии...",
    "shoot": "🔫 Комиссар достал оружие...",
    "heal": "💉 Доктор поспешил кому-то на помощь...",
    "drink": "🍺 Алкаш утащил кого-то домой выпивать...",
}

FAKE_LABEL = {
    "kill": "🔪 Убить (как мафия)",
    "check": "🕵️ Проверить (как комиссар)",
    "shoot": "🔫 Застрелить (как комиссар)",
    "heal": "💉 Вылечить (как доктор)",
    "drink": "🍺 Увести бухать (как алкаш)",
}

RULES_TEXT = (
    "📖 <b>Правила</b>\n\n"
    "Город делится на мирных и мафию. Игра идёт кругами: ночь → день → голосование.\n\n"
    "🌙 <b>Ночью</b> роли получают меню в личке бота и делают ход. В группе писать нельзя — сообщения удаляются.\n"
    "☀️ <b>Днём</b> обсуждают, кто мафия. Писать в группу могут только игроки.\n"
    "⚖️ <b>Голосование</b> — кого казнить (кнопки в группе).\n\n"
    "<b>Роли:</b>\n"
    + "\n\n".join(f"{ROLE_TITLE[r]}\n{ROLE_DESC[r]}" for r in
                  (DON, MAFIA, COMMISSAR, DOCTOR, CIVILIAN, DECEIVER, ALCOHOLIC))
    + "\n\n🏆 <b>Победа мирных:</b> убиты Дон и вся мафия.\n"
      "🏆 <b>Победа мафии:</b> мафия (с Обманщиком) сравнялась по числу с остальными."
)


# ───────────────────────── МАФИЯ: МОДЕЛИ ─────────────────────────
@dataclass
class Player:
    user_id: int
    name: str
    role: str = CIVILIAN
    alive: bool = True
    self_healed: bool = False
    last_heal: Optional[int] = None

    @property
    def mention(self) -> str:
        return f'<a href="tg://user?id={self.user_id}">{html.escape(self.name)}</a>'


class Game:
    def __init__(self, chat_id: int, owner_id: int, title: str):
        self.chat_id = chat_id
        self.owner_id = owner_id
        self.title = title
        self.players: dict[int, Player] = {}
        self.state = "lobby"  # lobby / starting / night / resolving / day / vote / ended
        self.day = 0
        self.chat_link: Optional[str] = None
        self.lobby_msg_id: Optional[int] = None
        self.lobby_task: Optional[asyncio.Task] = None
        self.task: Optional[asyncio.Task] = None
        # ночь
        self.mafia_votes: dict[int, int] = {}
        self.doctor_target: Optional[int] = None
        self.commissar_target: Optional[int] = None
        self.shoot_target: Optional[int] = None
        self.drunk_target: Optional[int] = None
        self.acted: set[int] = set()
        self.announced: set[str] = set()
        self.night_event = asyncio.Event()
        # голосование
        self.votes: dict[int, int] = {}
        self.vote_event = asyncio.Event()

    def alive(self) -> list[Player]:
        return [p for p in self.players.values() if p.alive]


games: dict[int, Game] = {}
user_game: dict[int, int] = {}
GROUP_TYPES = {ChatType.GROUP, ChatType.SUPERGROUP}


# ───────────────────────── МАФИЯ: ХЕЛПЕРЫ ─────────────────────────
async def send(chat_id: int, text: str, **kw) -> Optional[Message]:
    try:
        return await bot.send_message(chat_id, text, **kw)
    except TelegramAPIError as e:
        log.warning("send to %s failed: %s", chat_id, e)
        return None


async def edit_cb(cb: CallbackQuery, text: str, markup=None):
    try:
        await cb.message.edit_text(text, reply_markup=markup)
    except TelegramAPIError as e:
        log.debug("edit failed: %s", e)


async def get_chat_link(chat) -> Optional[str]:
    if chat.username:
        return f"https://t.me/{chat.username}"
    try:
        link = await bot.create_chat_invite_link(chat.id, name="mafia-bot")
        return link.invite_link
    except TelegramAPIError:
        return None


def go_group_kb(g: Game):
    if not g.chat_link:
        return None
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="Перейти в группу", url=g.chat_link))
    return b.as_markup()


def go_bot_kb():
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="🤖 Открыть бота", url=f"https://t.me/{BOT_USERNAME}"))
    return b.as_markup()


def cleanup(g: Game):
    current = asyncio.current_task()
    for t in (g.lobby_task, g.task):
        if t and t is not current and not t.done():
            t.cancel()
    for uid in list(g.players):
        if user_game.get(uid) == g.chat_id:
            user_game.pop(uid, None)
    if games.get(g.chat_id) is g:
        games.pop(g.chat_id, None)
    g.state = "ended"


async def is_manager(g: Game, uid: int) -> bool:
    if uid == g.owner_id:
        return True
    try:
        m = await bot.get_chat_member(g.chat_id, uid)
        return m.status in (ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR)
    except TelegramAPIError:
        return False


def alive_list_text(g: Game) -> str:
    return "\n".join(f"• {p.mention}" for p in g.alive())


# ───────────────────────── МАФИЯ: ТИШИНА В ГРУППЕ ─────────────────────────
class GroupGuard(BaseMiddleware):
    """Ночью в группе писать никому нельзя; днём и на голосовании — только игрокам.
    Лишние сообщения бот удаляет (нужны права админа). Команды (/...) пропускаются."""

    async def __call__(self, handler, event: Message, data):
        if (event.chat.type in GROUP_TYPES and event.from_user
                and not event.from_user.is_bot):
            g = games.get(event.chat.id)
            if g and g.state in ("starting", "night", "resolving", "day", "vote"):
                if not (event.text or "").startswith("/"):
                    p = g.players.get(event.from_user.id)
                    allowed = (g.state in ("starting", "day", "vote") and p is not None
                               and (p.alive or DEAD_CAN_CHAT))
                    if not allowed:
                        try:
                            await event.delete()
                        except TelegramAPIError:
                            pass
                        return
        return await handler(event, data)


# ───────────────────────── МАФИЯ: ЛОББИ ─────────────────────────
def lobby_text(g: Game) -> str:
    lines = [
        "🎭 <b>Набор в Мафию!</b>",
        "",
        f"Игроков: <b>{len(g.players)}</b> (минимум {MIN_PLAYERS}, максимум {MAX_PLAYERS})",
    ]
    if g.players:
        lines.append("")
        for i, p in enumerate(g.players.values(), 1):
            lines.append(f"{i}. {p.mention}")
    lines += [
        "",
        "Нажми «Присоединиться» → откроется бот → нажми там «Запустить».",
        f"Набор идёт {REG_SECONDS} сек. Начать раньше: /startgame",
    ]
    return "\n".join(lines)


def lobby_kb(g: Game):
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(
        text="✅ Присоединиться",
        url=f"https://t.me/{BOT_USERNAME}?start=join_{g.chat_id}"))
    b.row(InlineKeyboardButton(text="▶️ Начать сейчас", callback_data=f"startnow:{g.chat_id}"))
    return b.as_markup()


async def refresh_lobby(g: Game):
    if not g.lobby_msg_id:
        return
    try:
        await bot.edit_message_text(lobby_text(g), chat_id=g.chat_id,
                                    message_id=g.lobby_msg_id, reply_markup=lobby_kb(g))
    except TelegramAPIError as e:
        log.debug("lobby edit: %s", e)


async def lobby_timer(g: Game):
    await asyncio.sleep(REG_SECONDS)
    g.lobby_task = None
    if g.state == "lobby":
        await begin_game(g, by_timer=True)


def build_roles(n: int) -> list[str]:
    killers = max(1, n // 4)
    roles = [DON, COMMISSAR, DOCTOR]
    roles += [MAFIA] * (killers - 1)
    if n >= 6:
        roles.append(DECEIVER)
    if n >= 5:
        roles.append(ALCOHOLIC)
    while len(roles) < n:
        roles.append(CIVILIAN)
    return roles[:n]


async def send_role(g: Game, p: Player):
    text = f"Твоя роль - <b>{ROLE_TITLE[p.role]}</b>!\n\n{ROLE_DESC[p.role]}"
    if p.role in KILLERS:
        text += "\n\n<b>Запомни своих союзников:</b>\n"
        for q in g.players.values():
            if q.role in KILLERS:
                text += f"{q.mention} - {ROLE_TITLE[q.role]}\n"
    elif p.role == DECEIVER:
        text += "\n\n<b>Твоя мафия (они о тебе не знают):</b>\n"
        for q in g.players.values():
            if q.role in KILLERS:
                text += f"{q.mention} - {ROLE_TITLE[q.role]}\n"
    await send(p.user_id, text, reply_markup=go_group_kb(g))


async def begin_game(g: Game, by_timer: bool = False):
    if g.state != "lobby":
        return
    if len(g.players) < MIN_PLAYERS:
        if by_timer:
            await send(g.chat_id, f"😔 Не набралось игроков (нужно минимум {MIN_PLAYERS}). Игра отменена.")
            cleanup(g)
        else:
            await send(g.chat_id, f"Нужно минимум {MIN_PLAYERS} игроков. Сейчас: {len(g.players)}.")
        return
    if g.lobby_task and not by_timer:
        g.lobby_task.cancel()
    g.lobby_task = None
    g.state = "starting"

    roles = build_roles(len(g.players))
    random.shuffle(roles)
    for p, r in zip(list(g.players.values()), roles):
        p.role = r

    if g.lobby_msg_id:
        try:
            await bot.edit_message_reply_markup(chat_id=g.chat_id, message_id=g.lobby_msg_id,
                                                reply_markup=None)
        except TelegramAPIError:
            pass

    for p in g.players.values():
        await send_role(g, p)

    comp = Counter(roles)
    comp_text = "\n".join(f"{ROLE_TITLE[r]}: {comp[r]}" for r in
                          (DON, MAFIA, DECEIVER, COMMISSAR, DOCTOR, ALCOHOLIC, CIVILIAN) if comp[r])
    await send(
        g.chat_id,
        f"🎬 <b>Игра началась!</b>\nРоли розданы в личных сообщениях.\n\n"
        f"Игроков: {len(g.players)}\n<b>В игре:</b>\n{comp_text}\n\n"
        f"Живые:\n{alive_list_text(g)}",
        reply_markup=go_bot_kb(),
    )
    g.task = asyncio.create_task(game_loop(g))


# ───────────────────────── МАФИЯ: КОМАНДЫ ─────────────────────────
@router.message(CommandStart(deep_link=True), F.chat.type == ChatType.PRIVATE)
async def start_deeplink(m: Message, command: CommandObject):
    arg = command.args or ""
    if not arg.startswith("join_"):
        await m.answer(MAIN_TEXT, parse_mode=None)
        return
    try:
        chat_id = int(arg[5:])
    except ValueError:
        await m.answer("Некорректная ссылка.")
        return
    g = games.get(chat_id)
    if not g or g.state != "lobby":
        await m.answer("Набор в эту игру уже закрыт или игры нет.")
        return
    uid = m.from_user.id
    if user_game.get(uid) not in (None, chat_id):
        await m.answer("Ты уже участвуешь в другой игре.")
        return
    if uid in g.players:
        await m.answer("Ты уже в игре ✅ Возвращайся в группу.", reply_markup=go_group_kb(g))
        return
    if len(g.players) >= MAX_PLAYERS:
        await m.answer("Мест нет 😔")
        return
    g.players[uid] = Player(uid, m.from_user.full_name or "Игрок")
    user_game[uid] = chat_id
    await m.answer(f"✅ Ты в игре «{html.escape(g.title)}». Возвращайся в группу и жди начала.",
                   reply_markup=go_group_kb(g))
    await refresh_lobby(g)


@router.message(Command("help"))
async def cmd_help(m: Message):
    await m.answer(MAIN_TEXT, parse_mode=None)


@router.message(Command("rules"))
async def cmd_rules(m: Message):
    await m.answer(RULES_TEXT)


@router.message(Command("game", "newgame", "mafia"), F.chat.type.in_(GROUP_TYPES))
async def cmd_game(m: Message):
    if m.chat.id in games:
        await m.reply("В этом чате уже идёт игра или набор. /stop — остановить (админ).")
        return
    g = Game(m.chat.id, m.from_user.id, m.chat.title or "группа")
    g.chat_link = await get_chat_link(m.chat)
    games[m.chat.id] = g
    msg = await m.answer(lobby_text(g), reply_markup=lobby_kb(g))
    g.lobby_msg_id = msg.message_id
    g.lobby_task = asyncio.create_task(lobby_timer(g))


@router.message(Command("startgame"), F.chat.type.in_(GROUP_TYPES))
async def cmd_startgame(m: Message):
    g = games.get(m.chat.id)
    if not g or g.state != "lobby":
        await m.reply("Сейчас нет набора. Начни его командой /game")
        return
    if not await is_manager(g, m.from_user.id):
        await m.reply("Запустить может создатель набора или админ.")
        return
    await begin_game(g)


@router.callback_query(F.data.startswith("startnow:"))
async def cb_startnow(cb: CallbackQuery):
    g = games.get(int(cb.data.split(":")[1]))
    if not g or g.state != "lobby":
        await cb.answer("Набор уже закрыт", show_alert=True)
        return
    if not await is_manager(g, cb.from_user.id):
        await cb.answer("Только создатель набора или админ", show_alert=True)
        return
    await cb.answer()
    await begin_game(g)


@router.message(Command("leave"))
async def cmd_leave(m: Message):
    uid = m.from_user.id
    g = games.get(user_game.get(uid, 0))
    if not g:
        await m.reply("Ты не в игре.")
        return
    if g.state != "lobby":
        await m.reply("Игра уже идёт — выйти нельзя 😈")
        return
    g.players.pop(uid, None)
    user_game.pop(uid, None)
    await m.reply("Ты вышел из набора.")
    await refresh_lobby(g)


@router.message(Command("stop"), F.chat.type.in_(GROUP_TYPES))
async def cmd_stop(m: Message):
    g = games.get(m.chat.id)
    if not g:
        await m.reply("Нет активной игры.")
        return
    if not await is_manager(g, m.from_user.id):
        await m.reply("Остановить может создатель игры или админ.")
        return
    cleanup(g)
    await m.answer("🛑 Игра остановлена.")


@router.message(Command("alive"), F.chat.type.in_(GROUP_TYPES))
async def cmd_alive(m: Message):
    g = games.get(m.chat.id)
    if not g or g.state in ("lobby", "ended"):
        await m.reply("Игра не идёт.")
        return
    await m.answer(f"👥 <b>Живые ({len(g.alive())}):</b>\n{alive_list_text(g)}")


# ───────────────────────── МАФИЯ: ИГРОВОЙ ЦИКЛ ─────────────────────────
async def game_loop(g: Game):
    try:
        await asyncio.sleep(3)
        while True:
            g.day += 1
            await night_phase(g)
            if await check_win(g):
                break
            await day_phase(g)
            if await check_win(g):
                break
            await vote_phase(g)
            if await check_win(g):
                break
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception("game crashed in chat %s", g.chat_id)
        await send(g.chat_id, "⚠️ В игре произошла ошибка, игра остановлена. Начни заново: /game")
    finally:
        cleanup(g)


# ───────────────────────── МАФИЯ: НОЧЬ ─────────────────────────
def night_targets(g: Game, p: Player, kind: str) -> list[Player]:
    alive = g.alive()
    if kind == "kill":
        return [q for q in alive if q.role not in KILLERS]
    if kind == "heal":
        return [q for q in alive
                if q.user_id != p.last_heal and not (q.user_id == p.user_id and p.self_healed)]
    return [q for q in alive if q.user_id != p.user_id]  # check / shoot / drink


def skip_row(g: Game):
    return InlineKeyboardButton(text="😴 Пропустить", callback_data=f"skip:{g.chat_id}")


def targets_kb(g: Game, prefix: str, targets: list[Player], back: bool = False,
               back_cb: Optional[str] = None):
    b = InlineKeyboardBuilder()
    for t in targets:
        b.button(text=t.name[:30], callback_data=f"{prefix}:{t.user_id}")
    b.adjust(2)
    if back:
        b.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=back_cb or f"fkb:{g.chat_id}"))
    b.row(skip_row(g))
    if g.chat_link:
        b.row(InlineKeyboardButton(text="Перейти в группу", url=g.chat_link))
    return b.as_markup()


def deceiver_menu_kb(g: Game):
    b = InlineKeyboardBuilder()
    for kind in ("kill", "check", "shoot", "heal", "drink"):
        b.row(InlineKeyboardButton(text=FAKE_LABEL[kind], callback_data=f"fk:{g.chat_id}:{kind}"))
    b.row(skip_row(g))
    if g.chat_link:
        b.row(InlineKeyboardButton(text="Перейти в группу", url=g.chat_link))
    return b.as_markup()


def deceiver_menu_text(g: Game) -> str:
    return (f"🌙 <b>Ночь {g.day}</b>\n🎭 Ты Обманщик. Выбери действие — в группе появится "
            f"такое же сообщение, как от настоящей роли (на деле ничего не произойдёт). "
            f"Можно одно действие за ночь.")


def commissar_menu_kb(g: Game):
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="🔍 Проверить роль", callback_data=f"cmk:{g.chat_id}:check"))
    b.row(InlineKeyboardButton(text="🔫 Застрелить", callback_data=f"cmk:{g.chat_id}:shoot"))
    b.row(skip_row(g))
    if g.chat_link:
        b.row(InlineKeyboardButton(text="Перейти в группу", url=g.chat_link))
    return b.as_markup()


def commissar_menu_text(g: Game) -> str:
    return f"🌙 <b>Ночь {g.day}</b>\n🕵️ Что делаешь этой ночью? (одно действие)"


async def send_night_menu(g: Game, p: Player):
    if p.role == DECEIVER:
        await send(p.user_id, deceiver_menu_text(g), reply_markup=deceiver_menu_kb(g))
        return
    if p.role == COMMISSAR:
        await send(p.user_id, commissar_menu_text(g), reply_markup=commissar_menu_kb(g))
        return
    kind = ROLE_ACTION.get(p.role)
    if not kind:
        await send(p.user_id, f"🌙 <b>Ночь {g.day}</b>\nТы спишь... Жди утра.",
                   reply_markup=go_group_kb(g))
        return
    targets = night_targets(g, p, kind)
    await send(p.user_id, f"🌙 <b>Ночь {g.day}</b>\n{KIND_PROMPT[kind]}",
               reply_markup=targets_kb(g, f"act:{g.chat_id}:{kind}", targets))


def all_acted(g: Game) -> bool:
    for p in g.alive():
        if (p.role in ROLE_ACTION or p.role == DECEIVER) and p.user_id not in g.acted:
            return False
    return True


async def night_phase(g: Game):
    g.state = "night"
    g.mafia_votes = {}
    g.doctor_target = g.commissar_target = g.drunk_target = g.shoot_target = None
    g.acted = set()
    g.announced = set()
    g.night_event = asyncio.Event()

    await send(g.chat_id,
               f"🌙 <b>Ночь {g.day} наступила</b>\n\n"
               f"Город засыпает, просыпается мафия...\n"
               f"🤫 <b>Писать в чат нельзя</b> — сообщения удаляются.\n"
               f"У ролей {NIGHT_SECONDS} сек. на ход — меню в личке бота.",
               reply_markup=go_bot_kb())
    for p in g.alive():
        await send_night_menu(g, p)

    if all_acted(g):
        g.night_event.set()
    early = False
    try:
        await asyncio.wait_for(g.night_event.wait(), NIGHT_SECONDS)
        early = True
    except asyncio.TimeoutError:
        pass
    if early:
        await asyncio.sleep(random.uniform(2, 5))
    g.state = "resolving"
    await resolve_night(g)


async def to_killers(g: Game, text: str, exclude: Optional[int] = None):
    for q in g.alive():
        if q.role in KILLERS and q.user_id != exclude:
            await send(q.user_id, text, reply_markup=go_group_kb(g))


async def announce_action(g: Game, kind: str, fake: bool = False):
    if not fake:
        if kind in g.announced:
            return
        g.announced.add(kind)
    await send(g.chat_id, ANNOUNCE[kind])


def night_ctx(cb: CallbackQuery, chat_id: int):
    g = games.get(chat_id)
    if not g or g.state != "night":
        return None, None
    p = g.players.get(cb.from_user.id)
    if not p or not p.alive:
        return None, None
    return g, p


@router.callback_query(F.data.startswith("act:"))
async def cb_act(cb: CallbackQuery):
    try:
        _, chat, kind, tid = cb.data.split(":")
        chat_id, tid = int(chat), int(tid)
    except ValueError:
        await cb.answer()
        return
    g, p = night_ctx(cb, chat_id)
    if not g:
        await cb.answer("Это действие уже недоступно", show_alert=True)
        return
    if p.role == COMMISSAR:
        allowed = kind in ("check", "shoot")
    else:
        allowed = ROLE_ACTION.get(p.role) == kind
    if not allowed:
        await cb.answer("Это не твоё действие", show_alert=True)
        return
    if p.user_id in g.acted:
        await cb.answer("Ты уже сделал выбор", show_alert=True)
        return
    t = g.players.get(tid)
    if not t or not t.alive or t not in night_targets(g, p, kind):
        await cb.answer("Нельзя выбрать этого игрока", show_alert=True)
        return

    g.acted.add(p.user_id)
    await cb.answer()
    await edit_cb(cb, f"Ваш выбор: {t.mention}")

    if kind == "kill":
        g.mafia_votes[p.user_id] = tid
        await to_killers(g, f"{p.mention} выбрал(а) {t.mention}", exclude=p.user_id)
    elif kind == "check":
        g.commissar_target = tid
        mafia_like = t.role in MAFIA_TEAM
        verdict = "🔴 <b>МАФИЯ</b>" if mafia_like else "🟢 <b>Мирный житель</b>"
        await send(p.user_id, f"🕵️ Результат проверки: {t.mention} — {verdict}")
    elif kind == "shoot":
        g.shoot_target = tid
    elif kind == "heal":
        g.doctor_target = tid
        p.last_heal = tid
        if tid == p.user_id:
            p.self_healed = True
    elif kind == "drink":
        g.drunk_target = tid
        await send(tid, "🍺 Этой ночью тебя кто-то увёл домой выпивать. Ты всю ночь пил и ничего не помнишь...")

    await announce_action(g, kind)
    if all_acted(g):
        g.night_event.set()


@router.callback_query(F.data.startswith("cmk:"))
async def cb_commissar_kind(cb: CallbackQuery):
    try:
        _, chat, kind = cb.data.split(":")
        chat_id = int(chat)
    except ValueError:
        await cb.answer()
        return
    g, p = night_ctx(cb, chat_id)
    if not g or p.role != COMMISSAR or p.user_id in g.acted or kind not in ("check", "shoot"):
        await cb.answer("Это действие уже недоступно", show_alert=True)
        return
    await cb.answer()
    await edit_cb(cb, KIND_PROMPT[kind],
                  targets_kb(g, f"act:{g.chat_id}:{kind}", night_targets(g, p, kind),
                             back=True, back_cb=f"cmb:{g.chat_id}"))


@router.callback_query(F.data.startswith("cmb:"))
async def cb_commissar_back(cb: CallbackQuery):
    g, p = night_ctx(cb, int(cb.data.split(":")[1]))
    if not g or p.role != COMMISSAR or p.user_id in g.acted:
        await cb.answer("Это действие уже недоступно", show_alert=True)
        return
    await cb.answer()
    await edit_cb(cb, commissar_menu_text(g), commissar_menu_kb(g))


@router.callback_query(F.data.startswith("fk:"))
async def cb_fake_kind(cb: CallbackQuery):
    try:
        _, chat, kind = cb.data.split(":")
        chat_id = int(chat)
    except ValueError:
        await cb.answer()
        return
    g, p = night_ctx(cb, chat_id)
    if not g or p.role != DECEIVER or p.user_id in g.acted or kind not in KIND_PROMPT:
        await cb.answer("Это действие уже недоступно", show_alert=True)
        return
    targets = [q for q in g.alive() if q.user_id != p.user_id]
    await cb.answer()
    await edit_cb(cb, f"🎭 {FAKE_LABEL[kind]}\nКого выбрать? (это фейк)",
                  targets_kb(g, f"fkt:{chat_id}:{kind}", targets, back=True))


@router.callback_query(F.data.startswith("fkb:"))
async def cb_fake_back(cb: CallbackQuery):
    g, p = night_ctx(cb, int(cb.data.split(":")[1]))
    if not g or p.role != DECEIVER or p.user_id in g.acted:
        await cb.answer("Это действие уже недоступно", show_alert=True)
        return
    await cb.answer()
    await edit_cb(cb, deceiver_menu_text(g), deceiver_menu_kb(g))


@router.callback_query(F.data.startswith("fkt:"))
async def cb_fake_target(cb: CallbackQuery):
    try:
        _, chat, kind, tid = cb.data.split(":")
        chat_id, tid = int(chat), int(tid)
    except ValueError:
        await cb.answer()
        return
    g, p = night_ctx(cb, chat_id)
    if not g or p.role != DECEIVER or p.user_id in g.acted or kind not in ANNOUNCE:
        await cb.answer("Это действие уже недоступно", show_alert=True)
        return
    t = g.players.get(tid)
    if not t or not t.alive:
        await cb.answer("Нельзя выбрать этого игрока", show_alert=True)
        return
    g.acted.add(p.user_id)
    await cb.answer("Фейк отправлен 😈")
    await edit_cb(cb, f"🎭 Ты сымитировал: {FAKE_LABEL[kind]}\nЦель: {t.mention}\n"
                      f"В группу ушло такое же сообщение, как от настоящей роли.")
    await announce_action(g, kind, fake=True)
    if all_acted(g):
        g.night_event.set()


@router.callback_query(F.data.startswith("skip:"))
async def cb_skip(cb: CallbackQuery):
    g, p = night_ctx(cb, int(cb.data.split(":")[1]))
    if not g or p.user_id in g.acted or not (p.role in ROLE_ACTION or p.role == DECEIVER):
        await cb.answer("Это действие уже недоступно", show_alert=True)
        return
    g.acted.add(p.user_id)
    await cb.answer()
    await edit_cb(cb, "😴 Ты пропустил ход.")
    if all_acted(g):
        g.night_event.set()


# Чат мафии: ночью союзники пишут друг другу в личку боту
async def is_mafia_night_chat(m: Message) -> bool:
    if not m.from_user:
        return False
    g = games.get(user_game.get(m.from_user.id, 0))
    if not g or g.state != "night":
        return False
    p = g.players.get(m.from_user.id)
    return bool(p and p.alive and p.role in KILLERS)


@router.message(F.chat.type == ChatType.PRIVATE, F.text, ~F.text.startswith("/"), is_mafia_night_chat)
async def mafia_chat(m: Message):
    g = games[user_game[m.from_user.id]]
    p = g.players[m.from_user.id]
    await to_killers(g, f"{p.mention}: <i>{html.escape(m.text)}</i>", exclude=p.user_id)


def pick_mafia_target(g: Game) -> Optional[int]:
    votes = dict(g.mafia_votes)
    if not votes:
        return None
    counts = Counter(votes.values())
    top_n = max(counts.values())
    cands = [t for t, c in counts.items() if c == top_n]
    if len(cands) == 1:
        return cands[0]
    don = next((p for p in g.alive() if p.role == DON), None)
    if don and votes.get(don.user_id) in cands:
        return votes[don.user_id]
    return random.choice(cands)


async def resolve_night(g: Game):
    target_id = pick_mafia_target(g)
    killed: list[tuple[Player, str]] = []

    if target_id is None:
        await to_killers(g, "Голосование мафии завершено\nМафия никого не выбрала.")
    else:
        t = g.players[target_id]
        await to_killers(g, f"Голосование мафии завершено\nМафия принесла в жертву: {t.mention}")
        if g.drunk_target == target_id:
            await to_killers(g, f"🍺 Вы пришли за {t.mention}, но дома его не оказалось — не нашли.")
        elif g.doctor_target == target_id:
            doc = next((p for p in g.alive() if p.role == DOCTOR), None)
            if doc:
                await send(doc.user_id, f"💉 Ты спас жизнь: {t.mention}!")
            await send(t.user_id, "💉 Этой ночью на тебя напали, но доктор успел тебя спасти!")
        else:
            t.alive = False
            killed.append((t, "mafia"))
            await send(t.user_id, "💀 Этой ночью тебя убила мафия. Ты выбыл из игры.")

    # выстрел комиссара
    sid = g.shoot_target
    if sid is not None:
        s = g.players[sid]
        com = next((p for p in g.players.values() if p.role == COMMISSAR), None)
        if s.alive:
            if g.drunk_target == sid:
                if com:
                    await send(com.user_id, f"🔫 Ты пришёл за {s.mention}, но дома его не оказалось.")
            elif g.doctor_target == sid:
                doc = next((p for p in g.alive() if p.role == DOCTOR), None)
                if doc:
                    await send(doc.user_id, f"💉 Ты спас жизнь: {s.mention}!")
                await send(s.user_id, "💉 Этой ночью в тебя стреляли, но доктор успел тебя спасти!")
                if com:
                    await send(com.user_id, f"🔫 Выстрел в {s.mention} не убил — его спасли.")
            else:
                s.alive = False
                killed.append((s, "shot"))
                await send(s.user_id, "💀 Этой ночью тебя застрелил комиссар. Ты выбыл из игры.")
                if com:
                    await send(com.user_id, f"🔫 Ты застрелил {s.mention} — {ROLE_TITLE[s.role]}.")

    text = f"☀️ <b>Наступило утро. День {g.day}</b>\n\n"
    if killed:
        for p, cause in killed:
            how = "убит(а) мафией" if cause == "mafia" else "застрелен(а) комиссаром"
            text += f"Этой ночью {how}: {p.mention}"
            text += f" — {ROLE_TITLE[p.role]}.\n" if REVEAL_ROLES else ".\n"
    else:
        text += "Этой ночью никто не погиб. 🙏\n"
    text += f"\n👥 <b>Живые ({len(g.alive())}):</b>\n{alive_list_text(g)}"
    await send(g.chat_id, text)


# ───────────────────────── МАФИЯ: ДЕНЬ / ГОЛОСОВАНИЕ ─────────────────────────
async def day_phase(g: Game):
    g.state = "day"
    await send(g.chat_id, f"💬 <b>Обсуждение</b> — {DAY_SECONDS} сек.\nКто мафия? Спорьте, доказывайте!")
    await asyncio.sleep(DAY_SECONDS)


async def vote_phase(g: Game):
    g.state = "vote"
    g.votes = {}
    g.vote_event = asyncio.Event()

    b = InlineKeyboardBuilder()
    for p in g.alive():
        b.button(text=p.name[:30], callback_data=f"vt:{g.chat_id}:{p.user_id}")
    b.adjust(2)
    b.row(InlineKeyboardButton(text="🚫 Никого не казнить", callback_data=f"vt:{g.chat_id}:0"))
    msg = await send(g.chat_id,
                     f"⚖️ <b>Голосование!</b> Кого казним? У вас {VOTE_SECONDS} сек.",
                     reply_markup=b.as_markup())
    try:
        await asyncio.wait_for(g.vote_event.wait(), VOTE_SECONDS)
    except asyncio.TimeoutError:
        pass
    g.state = "resolving"
    if msg:
        try:
            await bot.edit_message_reply_markup(chat_id=g.chat_id, message_id=msg.message_id,
                                                reply_markup=None)
        except TelegramAPIError:
            pass

    counts = Counter(g.votes.values())
    if not counts:
        await send(g.chat_id, "🤷 Никто не проголосовал. Сегодня казни не будет.")
        return
    top_n = max(counts.values())
    cands = [t for t, c in counts.items() if c == top_n]
    if len(cands) > 1 or cands[0] == 0:
        await send(g.chat_id, "⚖️ Мнения разделились (или выбрано «никого»). Сегодня никого не казнят.")
        return
    victim = g.players[cands[0]]
    victim.alive = False
    text = f"⚖️ Город решил казнить {victim.mention} ({top_n} гол.)"
    text += f"\nОн был: {ROLE_TITLE[victim.role]}" if REVEAL_ROLES else ""
    await send(g.chat_id, text)
    await send(victim.user_id, "⚰️ Город тебя казнил. Ты выбыл из игры.")


@router.callback_query(F.data.startswith("vt:"))
async def cb_vote(cb: CallbackQuery):
    try:
        _, chat, tid = cb.data.split(":")
        chat_id, tid = int(chat), int(tid)
    except ValueError:
        await cb.answer()
        return
    g = games.get(chat_id)
    if not g or g.state != "vote":
        await cb.answer("Голосование закончено", show_alert=True)
        return
    p = g.players.get(cb.from_user.id)
    if not p or not p.alive:
        await cb.answer("Голосуют только живые игроки", show_alert=True)
        return
    if tid == p.user_id:
        await cb.answer("За себя голосовать нельзя", show_alert=True)
        return
    if tid != 0:
        t = g.players.get(tid)
        if not t or not t.alive:
            await cb.answer("Этот игрок уже выбыл", show_alert=True)
            return
        label = t.mention
    else:
        label = "никого"
    g.votes[p.user_id] = tid
    await cb.answer("Голос принят")
    await send(g.chat_id, f"👉 {p.mention} проголосовал(а) за: {label}")
    if len(g.votes) >= len(g.alive()):
        g.vote_event.set()


# ───────────────────────── МАФИЯ: ПОБЕДА ─────────────────────────
async def check_win(g: Game) -> bool:
    alive = g.alive()
    killers = [p for p in alive if p.role in KILLERS]
    team = [p for p in alive if p.role in MAFIA_TEAM]
    peace = len(alive) - len(team)

    if not killers:
        winner = "peace"
    elif len(team) >= peace:
        winner = "mafia"
    else:
        return False

    title = "🏆 <b>Победили мирные жители!</b>" if winner == "peace" else "🏆 <b>Победила мафия!</b>"
    lines = [title, "", "<b>Роли в этой игре:</b>"]
    for p in g.players.values():
        mark = "🟢" if p.alive else "💀"
        lines.append(f"{mark} {p.mention} — {ROLE_TITLE[p.role]}")
    lines += ["", "Сыграем ещё? /game"]
    await send(g.chat_id, "\n".join(lines))
    g.state = "ended"
    return True


# ═════════════════════════════════════════════════════════════════
# ═══════════════════  КАРТОЧКИ / КАЗИНО / ИВЕНТ  ═══════════════════
# ═════════════════════════════════════════════════════════════════
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
    {"name": "Зелёная шлюшка",          "rarity": "🔮 Эпическая",   "price": 1500,   "file": "ChatGPT Image 6 окт. 2026 г., 15_28_10.png"},
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
            {"name": "Огненная Лера",   "price": 22500,  "file": "ChatGPT Image 6 окт. 2026 г., 11_30_41.png"},
            {"name": "Пожиратель тыкв", "price": 45000,  "file": "ChatGPT Image 6 окт. 2026 г., 11_26_06.png"},
            {"name": "Нора с тыквами",  "price": 90000,  "file": "ChatGPT Image 6 окт. 2026 г., 11_19_50.png"},
        ],
        "👻 Призрачная": [
            {"name": "Призрачный рубрик", "price": 135000, "file": "ChatGPT Image 6 окт. 2026 г., 11_23_00.png"},
        ],
        "🧙 Ведьминская": [
            {"name": "Ведьминский Еля", "price": 900000, "file": "ChatGPT Image 6 окт. 2026 г., 11_16_21.png"},
        ],
        "🧛 Вампирская": [
            {"name": "Вампирский хлеб", "price": 1800000, "file": "ChatGPT Image 6 окт. 2026 г., 10_48_44.png"},
        ],
    },
    "skeleton": {
        "👻 Призрачная": [
            {"name": "Котакбас",     "price": 270000, "file": "ChatGPT Image 6 окт. 2026 г., 14_07_30.png"},
            {"name": "Призрак заез", "price": 450000, "file": "ChatGPT Image 6 окт. 2026 г., 14_10_39.png"},
        ],
        "🧙 Ведьминская": [
            {"name": "Ведьминская кошка", "price": 1350000, "file": "ChatGPT Image 6 окт. 2026 г., 14_03_47.png"},
            {"name": "Ведьма неля",       "price": 1530000, "file": "ChatGPT Image 6 окт. 2026 г., 14_23_18.png"},
        ],
        "🧛 Вампирская": [
            {"name": "А хотелось бы ведьминский жезл", "price": 2250000, "file": "ChatGPT Image 6 окт. 2026 г., 14_28_54.png"},
        ],
        "💀 Скелетная": [
            {"name": "Костяной Губка боб",     "price": 2700000, "file": "ChatGPT Image 6 окт. 2026 г., 14_36_53.png"},
            {"name": "Костяной Литвин x Спид", "price": 3600000, "file": "ChatGPT Image 6 окт. 2026 г., 14_42_20.png"},
        ],
        "😈 Демоническая": [
            {"name": "Коллекционер душ", "price": 9000000, "file": "ChatGPT Image 6 окт. 2026 г., 14_45_53.png"},
        ],
    },
    "ghost": {
        "💀 Скелетная": [
            {"name": "Костяной Губка боб",     "price": 2700000, "file": "ChatGPT Image 6 окт. 2026 г., 14_36_53.png"},
            {"name": "Костяной Литвин x Спид", "price": 3600000, "file": "ChatGPT Image 6 окт. 2026 г., 14_42_20.png"},
        ],
        "😈 Демоническая": [
            {"name": "Коллекционер душ", "price": 9000000, "file": "ChatGPT Image 6 окт. 2026 г., 14_45_53.png"},
        ],
        "😱 Кошмарная": [
            {"name": "Кошмарный Moggfone", "price": 45000000, "file": "ChatGPT Image 6 окт. 2026 г., 15_28_10.png"},
        ],
    },
}

RAD_CARDS = {
    "🦠 Заражённая": [
        {"name": "Проигравший доходяга",   "price": 70000,  "file": "ChatGPT Image 8 окт. 2026 г., 00_46_45.png"},
        {"name": "Заражёный фонк",         "price": 150000, "file": "ChatGPT Image 8 окт. 2026 г., 01_03_41.png"},
        {"name": "Заражёный глаз рубрика", "price": 200000, "file": "ChatGPT Image 8 окт. 2026 г., 00_51_53.png"},
    ],
    "☢️ Токсичная": [
        {"name": "Слабый Спид",   "price": 300000, "file": "ChatGPT Image 8 окт. 2026 г., 01_35_33.png"},
        {"name": "Токсичный кот", "price": 800000, "file": "ChatGPT Image 8 окт. 2026 г., 00_17_03.png"},
    ],
    "🧬 Мутировавшая": [
        {"name": "Мутировавший дерку",     "price": 500000,  "file": "ChatGPT Image 8 окт. 2026 г., 01_19_09.png"},
        {"name": "Мутировавший МГЕ прайм", "price": 1300000, "file": "ChatGPT Image 8 окт. 2026 г., 01_08_27.png"},
        {"name": "Мутировавшая Леся",      "price": 1500000, "file": "ChatGPT Image 8 окт. 2026 г., 00_56_05.png"},
    ],
    "⚛️ Ядерная": [
        {"name": "Слабо ядерная Лера", "price": 1400000, "file": "ChatGPT Image 8 окт. 2026 г., 01_54_55.png"},
        {"name": "Ядерный Еля",        "price": 3500000, "file": "ChatGPT Image 8 окт. 2026 г., 01_28_31.png"},
    ],
    "🔥 Критическая масса": [
        {"name": "Бойка против Мии", "price": 4250000, "file": "ChatGPT Image 8 окт. 2026 г., 01_50_08.png"},
        {"name": "Крутой Хлеб",      "price": 6700000, "file": "ChatGPT Image 8 окт. 2026 г., 01_43_16.png"},
    ],
    "🕳 Отчуждение": [
        {"name": "Правители доходяги", "price": 270000000, "file": "ChatGPT Image 8 окт. 2026 г., 01_59_13.png"},
        {"name": "Всегда рядом",       "price": 300000000, "file": "ChatGPT Image 8 окт. 2026 г., 00_05_19.png"},
    ],
    "💠 Специальная": [
        {"name": "Побеждённый король 👑", "price": 100000000, "file": BOSS_DEAD},
    ],
}

RAD_CASES = {
    "🦠 Заражённый": {
        "price": 1, "cooldown_min": 30,
        "chances": [("🦠 Заражённая", 85), ("☢️ Токсичная", 15)],
    },
    "☢️ Токсичный": {
        "price": 5, "cooldown_min": 30,
        "chances": [("🦠 Заражённая", 70), ("☢️ Токсичная", 25), ("🧬 Мутировавшая", 5)],
    },
    "🧬 Мутировавший": {
        "price": 10, "cooldown_min": 30,
        "chances": [("☢️ Токсичная", 70), ("🧬 Мутировавшая", 25), ("⚛️ Ядерная", 5)],
    },
    "⚛️ Ядерный": {
        "price": 20, "cooldown_min": 30,
        "chances": [("🧬 Мутировавшая", 70), ("⚛️ Ядерная", 25), ("🔥 Критическая масса", 5)],
    },
    "🔥 Критический": {
        "price": 50, "cooldown_min": 30,
        "chances": [("⚛️ Ядерная", 50), ("🔥 Критическая масса", 50)],
    },
    "🕳 Отчуждённый": {
        "price": 100, "cooldown_min": 30,
        "chances": [("⚛️ Ядерная", 79), ("🔥 Критическая масса", 20), ("🕳 Отчуждение", 1)],
    },
}

TOKEN_RATE = 100000
DAILY_TOKENS = 5
HALLOWEEN_RATE_BACK = 90

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

WHEEL_SEGMENTS = [
    {"emoji": "👻", "name": "Призрак",      "mult": 0,   "weight": 45},
    {"emoji": "🕷", "name": "Паук",         "mult": 0.5, "weight": 22},
    {"emoji": "🦇", "name": "Летучая мышь", "mult": 1.5, "weight": 16},
    {"emoji": "🧛", "name": "Вампир",       "mult": 2,   "weight": 11},
    {"emoji": "🎃", "name": "Тыква-босс",   "mult": 5,   "weight": 5},
    {"emoji": "👑", "name": "Король тыкв",  "mult": 10,  "weight": 1},
]

BOSS_MAX_HP = 100
PLAYER_MAX_HP = 250
BOSS_DAMAGE = 10
PLAYER_DAMAGE = 10
BOSS_ATTACK_EVERY = 3
BOSS_ATTACK_DAMAGE = 5

color_games = {}
miner_games = {}
coin_games = {}
trade_games = {}
cards_view_games = {}
sell_games = {}
wheel_games = {}
rad_games = {}
rad_convert_games = {}
boss_games = {}
boss_cooldowns = {}
boss_lock = {"current": None}

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
    last_trade TEXT,
    tokens INTEGER DEFAULT 0
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
cur.execute("""CREATE TABLE IF NOT EXISTS rad_cooldowns (
    user_id INTEGER,
    case_name TEXT,
    last_time TEXT,
    PRIMARY KEY (user_id, case_name)
)""")
db.commit()

for _col, _type in (("hw_balance", "INTEGER DEFAULT 0"), ("registered_at", "TEXT"),
                    ("last_trade", "TEXT"), ("last_daily", "TEXT"),
                    ("tokens", "INTEGER DEFAULT 0")):
    try:
        cur.execute(f"SELECT {_col} FROM users LIMIT 1")
    except sqlite3.OperationalError:
        cur.execute(f"ALTER TABLE users ADD COLUMN {_col} {_type}")
        db.commit()

_now_iso = datetime.now().isoformat()
cur.execute("UPDATE users SET registered_at = ? WHERE registered_at IS NULL", (_now_iso,))
db.commit()


# ==================== ВСПОМОГАТЕЛЬНЫЕ ====================
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


def roll_card_dev():
    top_rarities = ["👑 Легендарная", "♣️ Секретная", "🌌 Бесконечная", "💠 Специальная"]
    pool = [c for c in cards if c["rarity"] in top_rarities]
    if not pool:
        pool = cards
    return random.choice(pool)


def roll_rad_card(case_name):
    case = RAD_CASES[case_name]
    total = sum(ch for _, ch in case["chances"])
    r = random.uniform(0, total)
    upto = 0
    chosen_rarity = None
    for rarity, chance in case["chances"]:
        upto += chance
        if r <= upto:
            chosen_rarity = rarity
            break
    pool = RAD_CARDS.get(chosen_rarity, [])
    if not pool:
        for rar in RAD_CARDS:
            pool.extend(RAD_CARDS[rar])
    if "🕳 Отчуждение" == chosen_rarity:
        if random.random() < 0.5:
            return [c for c in pool if c["name"] == "Всегда рядом"][0], chosen_rarity
        else:
            return [c for c in pool if c["name"] == "Правители доходяги"][0], chosen_rarity
    return random.choice(pool), chosen_rarity


def find_rad_card(name):
    for rarity, lst in RAD_CARDS.items():
        for c in lst:
            if c["name"].lower() == name.lower():
                return c
    return None


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
    rad = find_rad_card(name)
    if rad:
        return rad
    return None


def card_rarity(name):
    """Редкость карты по названию (для карт ивентов в словаре она хранится в ключе)."""
    for c in cards:
        if c["name"].lower() == name.lower():
            return c["rarity"]
    for rarity, lst in RAD_CARDS.items():
        if any(c["name"].lower() == name.lower() for c in lst):
            return rarity
    for case_type, rarities in HW_CARDS.items():
        for rarity, lst in rarities.items():
            if any(c["name"].lower() == name.lower() for c in lst):
                return rarity
    return "—"


def has_always_near(uid):
    cur.execute("SELECT COUNT(*) FROM inventory WHERE user_id = ? AND card_name = ?", (uid, "Всегда рядом"))
    return cur.fetchone()[0] > 0


def rad_case_price(uid, case_name):
    base = RAD_CASES[case_name]["price"]
    if has_always_near(uid):
        discounted = int(base * 0.8)
        return max(1, discounted)
    return base


def get_all_cards_unique():
    result = []
    seen = set()
    for c in cards:
        if c["name"] not in seen:
            result.append(c)
            seen.add(c["name"])
    for case_type, rarities in HW_CARDS.items():
        for rarity, lst in rarities.items():
            for c in lst:
                if c["name"] not in seen:
                    result.append(c)
                    seen.add(c["name"])
    for rarity, lst in RAD_CARDS.items():
        for c in lst:
            if c["name"] not in seen:
                result.append(c)
                seen.add(c["name"])
    return result


def get_user(uid, username=None):
    cur.execute("SELECT balance, last_card, level, registered_at, hw_balance, last_trade, tokens FROM users WHERE user_id = ?", (uid,))
    row = cur.fetchone()
    if not row:
        now = datetime.now().isoformat()
        cur.execute("INSERT INTO users (user_id, username, registered_at) VALUES (?, ?, ?)", (uid, username, now))
        db.commit()
        return 0, None, 1, now, 0, None, 0
    if username:
        cur.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, uid))
        db.commit()
    return row[0], row[1], row[2], row[3], row[4], row[5], row[6]


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
render_sem = asyncio.Semaphore(2)
video_file_ids = {}


def _video_path(card_data, rarity_label):
    key = hashlib.md5(f"{card_data['file']}|{card_data['name']}|{rarity_label}|v4".encode()).hexdigest()
    return os.path.join(VIDEO_DIR, key + ".mp4")


async def send_reveal(message, card_data, rarity_label, caption, reply_markup=None, parse_mode=None):
    """Анимация открытия карты (3 сек, тема по редкости), затем замена на фото с кнопками."""
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


# ---------- видео Color Dice ----------
dice_file_ids = {}


async def send_dice_video(message, result, caption):
    """Видео: падают 4 цветных шара. Возвращает отправленное сообщение или None."""
    if not USE_EXTRA_VIDEO:
        return None
    codes = [c["code"] for c in result]
    key = "_".join(codes)
    path = os.path.join(VIDEO_DIR, "dice_" + key + ".mp4")
    status = None
    made_tmp = False
    try:
        media = dice_file_ids.get(key)
        if media is None:
            status = await message.answer("🎲 Готовим стол...")
            async with render_sem:
                await asyncio.to_thread(render_dice_video, codes, path, FONT_PATH)
            media = FSInputFile(path)
            made_tmp = True
        sent = await message.answer_animation(media, caption=caption, parse_mode="Markdown",
                                              width=DICE_W, height=DICE_H)
        if sent.animation:
            dice_file_ids[key] = sent.animation.file_id
        elif sent.video:
            dice_file_ids[key] = sent.video.file_id
        return sent
    except Exception as e:
        print("Ошибка видео Color Dice:", e)
        return None
    finally:
        if status:
            try:
                await status.delete()
            except Exception:
                pass
        if made_tmp and os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass


# ---------- плавные переходы босса ----------
boss_clip_ids = {}


def _boss_clip_path(kind):
    return os.path.join(VIDEO_DIR, f"boss_{kind}_v1.mp4")


async def ensure_boss_clip(kind):
    other = BOSS_HURT if kind == "hurt" else BOSS_ATTACK
    path = _boss_clip_path(kind)
    if not os.path.exists(path):
        async with render_sem:
            if not os.path.exists(path):
                await asyncio.to_thread(render_boss_transition, BOSS_NORMAL, other, path, kind)
    return path


async def prerender_videos():
    if not USE_REVEAL_VIDEO:
        return
    jobs = []
    for c in cards:
        if c["rarity"] in RARITY_CHANCES:
            jobs.append((c, c["rarity"]))
    for rarity, lst in RAD_CARDS.items():
        for c in lst:
            jobs.append((c, rarity))
    for c, rarity in jobs:
        path = _video_path(c, rarity)
        if os.path.exists(path):
            continue
        try:
            async with render_sem:
                await asyncio.to_thread(render_card_video, c["file"], path, c["name"], rarity, FONT_PATH)
        except Exception as e:
            print("Не удалось собрать видео для", c["name"], "-", e)
    if USE_EXTRA_VIDEO:
        for kind in ("hurt", "attack"):
            try:
                await ensure_boss_clip(kind)
            except Exception as e:
                print("Не удалось собрать клип босса", kind, "-", e)


# ==================== ОСНОВНЫЕ КОМАНДЫ ====================
@cr.message(Command("start"))
async def start(message: types.Message):
    get_user(message.from_user.id, message.from_user.username)
    await message.answer(MAIN_TEXT, parse_mode=None)


@cr.message(Command("card"))
async def card(message: types.Message):
    uid = message.from_user.id
    username = message.from_user.username or "Игрок"
    is_dev = uid == DEV_ID and uid in dev_mode
    balance, last, level, _, _, _, _ = get_user(uid, message.from_user.username)
    if not is_dev and last:
        last_dt = datetime.fromisoformat(last)
        elapsed = datetime.now() - last_dt
        if elapsed < timedelta(minutes=COOLDOWN_MINUTES):
            left = timedelta(minutes=COOLDOWN_MINUTES) - elapsed
            await message.answer(f"@{username}, ты уже крутил, открой позже.\n⏳ Ждать ещё: {format_cooldown(int(left.total_seconds()))}")
            return
    if not is_dev:
        cur.execute("UPDATE users SET last_card = ? WHERE user_id = ?", (datetime.now().isoformat(), uid))
        db.commit()

    drawn = []
    for _ in range(level):
        c = roll_card_dev() if is_dev else roll_card()
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
            await message.answer_photo(photo, caption=caption, reply_markup=kb, parse_mode=None)

    await asyncio.gather(*(show_one(c, inv_id) for c, inv_id in drawn))


@cr.callback_query(F.data.startswith("sell_card_"))
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
    await call.message.edit_caption(caption=f"✅ Продано: {row[0]} за {price}", reply_markup=None, parse_mode=None)
    await call.answer("Готово!")


@cr.message(Command("balance"))
async def balance_cmd(message: types.Message):
    balance, _, _, _, hw, _, tokens = get_user(message.from_user.id, message.from_user.username)
    await message.answer(f"💰 Монет: {balance}\n☢️ Токенов: {tokens}")


@cr.message(Command("tokens"))
async def tokens_cmd(message: types.Message):
    balance, _, _, _, _, _, tokens = get_user(message.from_user.id, message.from_user.username)
    await message.answer(f"☢️ Токенов: {tokens}\n(1 токен = {TOKEN_RATE} монет)")


@cr.message(Command("buytokens"))
async def buytokens_cmd(message: types.Message):
    uid = message.from_user.id
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(f"Использование: /buytokens количество\nКурс: 1 токен = {TOKEN_RATE} монет")
        return
    try:
        amount = int(args[1])
    except ValueError:
        await message.answer("❌ Введи число.")
        return
    if amount <= 0:
        await message.answer("❌ Больше 0.")
        return
    cost = amount * TOKEN_RATE
    balance, _, _, _, _, _, _ = get_user(uid, message.from_user.username)
    if balance < cost:
        await message.answer(f"❌ Нужно {cost} монет, у тебя {balance}.")
        return
    cur.execute("UPDATE users SET balance = balance - ?, tokens = tokens + ? WHERE user_id = ?", (cost, amount, uid))
    db.commit()
    _, _, _, _, _, _, new_tokens = get_user(uid)
    await message.answer(f"✅ Куплено {amount} токенов за {cost} монет.\n☢️ Теперь: {new_tokens}")


@cr.message(Command("daily"))
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
        "UPDATE users SET tokens = tokens + ?, last_daily = ? WHERE user_id = ?",
        (DAILY_TOKENS, datetime.now().isoformat(), uid)
    )
    db.commit()
    _, _, _, _, _, _, tokens = get_user(uid)
    await message.answer(f"🎁 Ежедневная награда: +{DAILY_TOKENS} ☢️ токенов\n☢️ Теперь у тебя: {tokens}\n\nСледующая через 24 часа.")


@cr.message(Command("mycards"))
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


# ==================== DEV ====================
@cr.message(Command("dev"))
async def dev_toggle(message: types.Message):
    uid = message.from_user.id
    if uid != DEV_ID:
        return
    if uid in dev_mode:
        dev_mode.remove(uid)
        await message.answer("🔴 Dev-режим ВЫКЛючен.")
    else:
        dev_mode.add(uid)
        await message.answer("🟢 Dev-режим ВКЛючен! <code>/card</code> = топ-редкости без кулдауна.")


@cr.message(Command("give"))
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
        await message.answer(f"❌ Карта «{html.escape(name)}» не найдена.")
        return
    cur.execute("INSERT INTO inventory (user_id, card_name) VALUES (?, ?)", (uid, found["name"]))
    db.commit()
    await message.answer(f"✅ Выдано: {found['name']} ({found['price']})")


@cr.message(Command("giveall"))
async def giveall_cards(message: types.Message):
    uid = message.from_user.id
    if uid != DEV_ID:
        return
    all_cards = get_all_cards_unique()
    for c in all_cards:
        cur.execute("INSERT INTO inventory (user_id, card_name) VALUES (?, ?)", (uid, c["name"]))
    db.commit()
    await message.answer(f"✅ Выдано {len(all_cards)} карт!")


@cr.message(Command("setmoney"))
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


@cr.message(Command("settokens"))
async def settokens(message: types.Message):
    uid = message.from_user.id
    if uid != DEV_ID:
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Использование: /settokens Сумма")
        return
    try:
        amount = int(args[1])
    except ValueError:
        await message.answer("❌ Введи число.")
        return
    get_user(uid, message.from_user.username)
    cur.execute("UPDATE users SET tokens = ? WHERE user_id = ?", (amount, uid))
    db.commit()
    await message.answer(f"✅ Токенов установлено: {amount}")


# ==================== ПЕРЕДАЧА ДЕНЕГ ====================
@cr.message(Command("send"))
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
        await message.answer("❌ Больше 0.")
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
    balance, _, _, _, _, _, _ = get_user(uid, message.from_user.username)
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


@cr.message(Command("casino"))
async def casino_command(message: types.Message):
    uid = message.from_user.id
    username = message.from_user.username or message.from_user.full_name or "Игрок"
    await message.answer(f"🎰 *Casino* — @{username}\n\nВыбери игру:", reply_markup=casino_menu_kb(uid), parse_mode="Markdown")


@cr.callback_query(F.data.startswith("open_casino_"))
async def open_casino(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Это не твоё меню!", show_alert=True)
        return
    username = call.from_user.username or call.from_user.full_name or "Игрок"
    await call.message.answer(f"🎰 *Casino* — @{username}\n\nВыбери игру:", reply_markup=casino_menu_kb(uid), parse_mode="Markdown")
    await call.answer()


@cr.callback_query(F.data.startswith("casino_close_"))
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


@cr.callback_query(F.data.startswith("casino_color_"))
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


@cr.callback_query(F.data.startswith("col_"))
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


@cr.callback_query(F.data.startswith("casino_miner_"))
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


@cr.callback_query(F.data.startswith("casino_back_"))
async def casino_back(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Не твоё меню!", show_alert=True)
        return
    username = call.from_user.username or call.from_user.full_name or "Игрок"
    await call.message.edit_text(f"🎰 *Casino* — @{username}\n\nВыбери игру:", reply_markup=casino_menu_kb(uid), parse_mode="Markdown")
    await call.answer()


@cr.callback_query(F.data.startswith("miner_bet_"))
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


@cr.callback_query(F.data.startswith("miner_noop_"))
async def miner_noop(call: types.CallbackQuery):
    parts = call.data.split("_")
    uid = int(parts[3])
    if call.from_user.id != uid:
        await call.answer("Не твоя игра!", show_alert=True)
        return
    await call.answer("Уже открыто.")


@cr.callback_query(F.data.startswith("miner_open_"))
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
        del miner_games[uid]
        await call.answer("🎉 Победа!")
        if special_card:
            try:
                cd = next((c for c in cards if c["name"] == "Топ 1 Минёр"), None)
                if cd:
                    reward = f"🎁 *Награда!*\n\n🎴 {cd['name']}\n{cd['rarity']} | 💰 {cd['price']}"
                    ok = await send_reveal(call.message, cd, cd["rarity"], reward, parse_mode="Markdown")
                    if not ok:
                        await call.message.answer_photo(FSInputFile(cd["file"]), caption=reward, parse_mode="Markdown")
            except Exception:
                pass
        return
    await call.message.edit_text(
        f"💣 *Минёр* — @{username}\n💰 Ставка: {game['bet']}\n🟢 Открыто: {count}\n📈 Множитель: ×{multiplier}\n💵 Заберёшь: {potential}",
        reply_markup=miner_keyboard(game["opened"], game["mines"], uid), parse_mode="Markdown"
    )
    await call.answer(f"Открыто: {count} | ×{multiplier}")


@cr.callback_query(F.data.startswith("miner_cashout_"))
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


@cr.callback_query(F.data.startswith("casino_coin_"))
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
        f"🪙 *Орёл и Решка* — @{username}\n\n🦅 Угадал → ×2\n❌ Не угадал → проигрыш\n\n*Выбери сторону:*",
        reply_markup=kb, parse_mode="Markdown"
    )
    await call.answer()


@cr.callback_query(F.data.startswith("coin_heads_"))
async def coin_heads(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Не твоя игра!", show_alert=True)
        return
    coin_games[uid] = {"choice": "heads", "state": "wait_bet"}
    await call.message.edit_text("🪙 Твой выбор: 🦅 Орёл\n\n💰 Напиши сумму ставки.\nОтмена — /cancel")
    await call.answer()


@cr.callback_query(F.data.startswith("coin_tails_"))
async def coin_tails(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Не твоя игра!", show_alert=True)
        return
    coin_games[uid] = {"choice": "tails", "state": "wait_bet"}
    await call.message.edit_text("🪙 Твой выбор: 🪙 Монета\n\n💰 Напиши сумму ставки.\nОтмена — /cancel")
    await call.answer()


@cr.callback_query(F.data.startswith("casino_wheel_"))
async def casino_wheel(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Не твоё меню!", show_alert=True)
        return
    lines = [f"{s['emoji']} {s['name']} — ×{s['mult']} ({s['weight']}%)" for s in WHEEL_SEGMENTS]
    rules = "\n".join(lines)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Сделать ставку", callback_data=f"wheel_bet_{uid}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"casino_back_{uid}")],
    ])
    await call.message.edit_text(
        f"👹 *Колесо монстров*\n\n{rules}\n\nГотов рискнуть?",
        reply_markup=kb, parse_mode="Markdown"
    )
    await call.answer()


@cr.callback_query(F.data.startswith("wheel_bet_"))
async def wheel_bet_request(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Не твоё меню!", show_alert=True)
        return
    wheel_games[uid] = {"state": "wait_bet"}
    await call.message.edit_text("👹 *Колесо монстров*\n\n💰 Напиши сумму ставки.\nОтмена — /cancel", parse_mode="Markdown")
    await call.answer()


# ==================== EVENT (ДОХОДЯГИ) ====================
def event_menu_kb(uid):
    rows = []
    for case_name in RAD_CASES:
        price = rad_case_price(uid, case_name)
        rows.append([InlineKeyboardButton(
            text=f"{case_name} — {price} ☢️",
            callback_data=f"rad_open_{case_name}_{uid}"
        )])
    rows.append([InlineKeyboardButton(text="👑 Босс", callback_data=f"boss_start_{uid}")])
    rows.append([InlineKeyboardButton(text="💱 Купить токены", callback_data=f"rad_conv_{uid}")])
    rows.append([InlineKeyboardButton(text="🔙 Закрыть", callback_data=f"rad_close_{uid}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@cr.message(Command("event"))
async def event_menu(message: types.Message):
    uid = message.from_user.id
    username = message.from_user.username or message.from_user.full_name or "Игрок"
    balance, _, _, _, _, _, tokens = get_user(uid, message.from_user.username)
    has_an = has_always_near(uid)
    an_note = "\n🕳 *«Всегда рядом» — скидка −20%!*" if has_an else ""
    caption = (
        f"☢️ *Доходяги* — @{username}\n\n"
        f"🟢 Токсичный ивент. Кейсы и босс.\n\n"
        f"💰 Монет: {balance}\n"
        f"☢️ Токенов: {tokens}\n\n"
        f"*Выбирай:*{an_note}"
    )
    try:
        photo = FSInputFile("ChatGPT Image 8 окт. 2026 г., 00_05_19.png")
        await message.answer_photo(photo, caption=caption, reply_markup=event_menu_kb(uid), parse_mode="Markdown")
    except Exception:
        await message.answer(caption, reply_markup=event_menu_kb(uid), parse_mode="Markdown")


@cr.callback_query(F.data.startswith("rad_close_"))
async def rad_close(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Не твоё меню!", show_alert=True)
        return
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.answer()


async def show_event_menu(call, uid):
    username = call.from_user.username or call.from_user.full_name or "Игрок"
    balance, _, _, _, _, _, tokens = get_user(uid)
    has_an = has_always_near(uid)
    an_note = "\n🕳 *Скидка −20%!*" if has_an else ""
    caption = (
        f"☢️ *Доходяги* — @{username}\n\n"
        f"💰 Монет: {balance}\n☢️ Токенов: {tokens}\n\n"
        f"*Выбирай:*{an_note}"
    )
    try:
        await call.message.delete()
    except Exception:
        pass
    try:
        photo = FSInputFile("ChatGPT Image 8 окт. 2026 г., 00_05_19.png")
        await call.message.answer_photo(photo, caption=caption, reply_markup=event_menu_kb(uid), parse_mode="Markdown")
    except Exception:
        await call.message.answer(caption, reply_markup=event_menu_kb(uid), parse_mode="Markdown")


@cr.callback_query(F.data.startswith("rad_back_"))
async def rad_back(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Не твоё меню!", show_alert=True)
        return
    await show_event_menu(call, uid)
    await call.answer()


@cr.callback_query(F.data.startswith("rad_menu_"))
async def rad_menu_cb(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Не твоё меню!", show_alert=True)
        return
    await show_event_menu(call, uid)
    await call.answer()


@cr.callback_query(F.data.startswith("rad_conv_"))
async def rad_convert_menu(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Не твоё меню!", show_alert=True)
        return
    balance, _, _, _, _, _, tokens = get_user(uid)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="☢️ Купить токены", callback_data=f"rad_buy_tokens_{uid}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"rad_back_{uid}")],
    ])
    text = (
        f"💱 *Купить токены*\n\n"
        f"Курс: 1 ☢️ = {TOKEN_RATE} монет\n\n"
        f"💰 Монет: {balance}\n☢️ Токенов: {tokens}\n\n"
        f"Напиши число — сколько токенов купить."
    )
    try:
        await call.message.edit_caption(caption=text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        await call.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await call.answer()


@cr.callback_query(F.data.startswith("rad_buy_tokens_"))
async def rad_buy_tokens(call: types.CallbackQuery):
    uid = int(call.data.split("_")[3])
    if call.from_user.id != uid:
        await call.answer("Не твоё меню!", show_alert=True)
        return
    rad_convert_games[uid] = {"state": "wait_tokens"}
    text = f"☢️ Напиши сколько токенов купить (1 токен = {TOKEN_RATE} монет).\nОтмена — /cancel"
    try:
        await call.message.edit_caption(caption=text)
    except Exception:
        try:
            await call.message.edit_text(text)
        except Exception:
            pass
    await call.answer()


@cr.callback_query(F.data.startswith("rad_open_"))
async def rad_open_case(call: types.CallbackQuery):
    parts = call.data.split("_")
    uid = int(parts[-1])
    case_name = call.data.replace("rad_open_", "").rsplit("_", 1)[0]
    if call.from_user.id != uid:
        await call.answer("Не твоё меню!", show_alert=True)
        return
    case_name_full = case_name
    if case_name_full not in RAD_CASES:
        for cn in RAD_CASES:
            if cn.replace(" ", "_") == case_name_full:
                case_name_full = cn
                break
        else:
            await call.answer("Ошибка кейса", show_alert=True)
            return
    cur.execute("SELECT last_time FROM rad_cooldowns WHERE user_id = ? AND case_name = ?", (uid, case_name_full))
    row = cur.fetchone()
    if row:
        last_dt = datetime.fromisoformat(row[0])
        cd = RAD_CASES[case_name_full]["cooldown_min"]
        elapsed = datetime.now() - last_dt
        if elapsed < timedelta(minutes=cd):
            left = timedelta(minutes=cd) - elapsed
            await call.answer(f"⏳ Кулдаун: {format_cooldown(int(left.total_seconds()))}", show_alert=True)
            return
    price = rad_case_price(uid, case_name_full)
    _, _, _, _, _, _, tokens = get_user(uid)
    if tokens < price:
        await call.answer(f"❌ Нужно {price} ☢️, у тебя {tokens}", show_alert=True)
        return
    cur.execute("UPDATE users SET tokens = tokens - ? WHERE user_id = ?", (price, uid))
    cur.execute(
        "INSERT OR REPLACE INTO rad_cooldowns (user_id, case_name, last_time) VALUES (?, ?, ?)",
        (uid, case_name_full, datetime.now().isoformat())
    )
    db.commit()
    card_data, rarity = roll_rad_card(case_name_full)
    cur.execute("INSERT INTO inventory (user_id, card_name) VALUES (?, ?)", (uid, card_data["name"]))
    db.commit()
    _, _, _, _, _, _, tokens_new = get_user(uid)
    caption = (
        f"☢️ *{case_name_full}*\n\n🎉 Тебе выпала карточка!\n\n"
        f"🎴 *{card_data['name']}*\nРедкость: {rarity}\n💰 Цена: {card_data['price']} монет\n\n"
        f"☢️ Осталось токенов: {tokens_new}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="☢️ Открыть ещё", callback_data=f"rad_menu_{uid}")],
        [InlineKeyboardButton(text="🔙 Меню", callback_data=f"rad_back_{uid}")],
    ])
    await call.answer("☢️ Открываем кейс...")
    try:
        await call.message.delete()
    except Exception:
        pass
    ok = await send_reveal(call.message, card_data, rarity, caption, reply_markup=kb, parse_mode="Markdown")
    if not ok:
        try:
            await call.message.answer_photo(FSInputFile(card_data["file"]), caption=caption,
                                            reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await call.message.answer(caption, reply_markup=kb, parse_mode="Markdown")


# ==================== БОСС ДОХОДЯГ ====================
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


def boss_new_round(game):
    cells, goals = boss_round_info(game["round"])
    icons = ["🧪"] * goals + ["❌"] * (cells - goals)
    random.shuffle(icons)
    game["icons"] = icons
    game["cells"] = cells
    game["goals"] = goals
    game["opened"] = []
    game["found"] = []


def boss_build_kb(game):
    cells = game["cells"]
    opened = game["opened"]
    icons = game["icons"]
    buttons = []
    row = []
    for i in range(cells):
        if i in opened:
            if icons[i] == "🧪":
                row.append(InlineKeyboardButton(text="🧪", callback_data="boss_noop"))
            else:
                row.append(InlineKeyboardButton(text="❌", callback_data="boss_noop"))
        else:
            row.append(InlineKeyboardButton(text="🎲", callback_data=f"boss_cell_{i}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="🏳 Сдаться", callback_data="boss_surrender")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def boss_render_caption(game):
    username = game["username"]
    return (
        f"☢️ *БОСС ДОХОДЯГ* — @{username}\n\n"
        f"👑 Босс: {game['boss_hp']}/{BOSS_MAX_HP} HP\n"
        f"❤️ Ты: {game['player_hp']}/{PLAYER_MAX_HP} HP\n\n"
        f"📍 Раунд {game['round']}/5\n"
        f"🧪 Найдено: {len(game['found'])}/{game['goals']}\n\n"
        f"*Правила:*\n"
        f"🧪 Зелье → боссу −{BOSS_DAMAGE} HP\n"
        f"❌ Промах → тебе −{PLAYER_DAMAGE} HP\n"
        f"⚔️ Каждые 3 хода → тебе −{BOSS_ATTACK_DAMAGE} HP"
    )


def boss_release_if_idle():
    """Освобождает босса, если игрок бросил бой и не заходит давно."""
    cu = boss_lock["current"]
    if cu is None:
        return
    g = boss_games.get(cu)
    if not g or datetime.now() - g["last_action"] > timedelta(minutes=BOSS_IDLE_MIN):
        boss_games.pop(cu, None)
        boss_lock["current"] = None


@cr.callback_query(F.data.startswith("boss_start_"))
async def boss_start(call: types.CallbackQuery):
    uid = int(call.data.split("_")[2])
    if call.from_user.id != uid:
        await call.answer("Не твоё меню!", show_alert=True)
        return
    if uid in boss_games:
        await call.answer("Ты уже в бою! Если сообщение потерялось — /cancel", show_alert=True)
        return
    if uid in boss_cooldowns:
        elapsed = datetime.now() - boss_cooldowns[uid]
        if elapsed < timedelta(minutes=BOSS_COOLDOWN_MIN):
            left = timedelta(minutes=BOSS_COOLDOWN_MIN) - elapsed
            await call.answer(f"⏳ Кулдаун: {format_cooldown(int(left.total_seconds()))}", show_alert=True)
            return
    boss_release_if_idle()
    if boss_lock["current"] is not None and boss_lock["current"] != uid:
        await call.answer("⏳ Кто-то уже сражается с боссом!", show_alert=True)
        return
    username = call.from_user.username or call.from_user.full_name or "Игрок"
    game = {
        "boss_hp": BOSS_MAX_HP,
        "player_hp": PLAYER_MAX_HP,
        "round": 1,
        "username": username,
        "moves": 0,
        "msg_id": None,
        "chat_id": call.message.chat.id,
        "anim_id": 0,
        "last_action": datetime.now(),
    }
    boss_new_round(game)
    boss_games[uid] = game
    boss_lock["current"] = uid
    await call.answer("⚔️ Бой начался!")
    try:
        await call.message.delete()
    except Exception:
        pass
    try:
        sent = await call.message.answer_photo(
            FSInputFile(BOSS_NORMAL), caption=boss_render_caption(game),
            reply_markup=boss_build_kb(game), parse_mode="Markdown")
        game["msg_id"] = sent.message_id
        game["chat_id"] = sent.chat.id
    except Exception as e:
        print("Ошибка старта босса:", e)
        boss_games.pop(uid, None)
        boss_lock["current"] = None


@cr.callback_query(F.data == "boss_noop")
async def boss_noop(call: types.CallbackQuery):
    await call.answer("Уже открыто.")


async def boss_flash(uid, kind, anim_id):
    """Плавный переход: кроссфейд обычного кадра босса в hurt/attack и обратно.
    Если видео недоступно — запасной вариант: простая смена фото."""
    game = boss_games.get(uid)
    if not game or not game.get("msg_id"):
        return
    chat_id, msg_id = game["chat_id"], game["msg_id"]
    other = BOSS_HURT if kind == "hurt" else BOSS_ATTACK
    try:
        if USE_EXTRA_VIDEO:
            path = await ensure_boss_clip(kind)
            w, h = boss_clip_size(BOSS_NORMAL)
            media_src = boss_clip_ids.get(kind) or FSInputFile(path)
            res = await bot.edit_message_media(
                chat_id=chat_id, message_id=msg_id,
                media=InputMediaAnimation(media=media_src, caption=boss_render_caption(game),
                                          parse_mode="Markdown", width=w, height=h),
                reply_markup=boss_build_kb(game))
            if getattr(res, "animation", None):
                boss_clip_ids[kind] = res.animation.file_id
            elif getattr(res, "video", None):
                boss_clip_ids[kind] = res.video.file_id
            wait = BOSS_CLIP_SECONDS + 0.1
        else:
            await bot.edit_message_media(
                chat_id=chat_id, message_id=msg_id,
                media=InputMediaPhoto(media=FSInputFile(other), caption=boss_render_caption(game), parse_mode="Markdown"),
                reply_markup=boss_build_kb(game))
            wait = 1.0
        await asyncio.sleep(wait)
        game = boss_games.get(uid)
        # если за это время началась другая анимация или бой закончился — ничего не трогаем
        if not game or game["anim_id"] != anim_id:
            return
        await bot.edit_message_media(
            chat_id=chat_id, message_id=msg_id,
            media=InputMediaPhoto(media=FSInputFile(BOSS_NORMAL), caption=boss_render_caption(game), parse_mode="Markdown"),
            reply_markup=boss_build_kb(game))
    except Exception as e:
        print("Ошибка анимации босса:", e)


@cr.callback_query(F.data.startswith("boss_cell_"))
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
    game["last_action"] = datetime.now()
    game["opened"].append(idx)
    game["moves"] += 1
    hit = game["icons"][idx] == "🧪"
    boss_attacked = False
    if hit:
        game["found"].append(idx)
        game["boss_hp"] = max(0, game["boss_hp"] - BOSS_DAMAGE)
    else:
        game["player_hp"] -= PLAYER_DAMAGE
    if game["moves"] % BOSS_ATTACK_EVERY == 0:
        game["player_hp"] -= BOSS_ATTACK_DAMAGE
        boss_attacked = True

    chat = call.message

    # Игрок пал
    if game["player_hp"] <= 0 and game["boss_hp"] > 0:
        boss_lock["current"] = None
        boss_cooldowns[uid] = datetime.now()
        boss_games.pop(uid, None)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data=f"rad_back_{uid}")]
        ])
        await call.answer("💀 Ты проиграл!")
        try:
            await chat.delete()
        except Exception:
            pass
        try:
            await chat.answer_photo(FSInputFile(BOSS_ATTACK),
                                    caption="💀 *ТЫ ПАЛ В БОЮ*\n\nБосс победил. Кулдаун: 30 минут.",
                                    reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass
        return

    # Победа над боссом
    if game["boss_hp"] <= 0:
        boss_lock["current"] = None
        boss_cooldowns[uid] = datetime.now()
        boss_games.pop(uid, None)
        cur.execute("INSERT INTO inventory (user_id, card_name) VALUES (?, ?)", (uid, "Побеждённый король 👑"))
        db.commit()
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data=f"rad_back_{uid}")]
        ])
        caption = ("🎉 *БОСС ПОВЕРЖЕН!*\n\n🎴 Получена карточка: *Побеждённый король 👑*\n"
                   "💠 Специальная | 1000 ☢️\n\n⏳ Кулдаун: 30 минут")
        await call.answer("🎉 Победа!")
        try:
            await chat.delete()
        except Exception:
            pass
        boss_card = find_rad_card("Побеждённый король 👑")
        ok = False
        if boss_card:
            ok = await send_reveal(chat, boss_card, "💠 Специальная", caption, reply_markup=kb, parse_mode="Markdown")
        if not ok:
            try:
                await chat.answer_photo(FSInputFile(BOSS_DEAD), caption=caption, reply_markup=kb, parse_mode="Markdown")
            except Exception:
                await chat.answer(caption, reply_markup=kb, parse_mode="Markdown")
        return

    # Переход в следующий раунд
    if len(game["found"]) >= game["goals"] and game["round"] < 5:
        game["round"] += 1
        boss_new_round(game)

    # Плавная анимация в фоне — обработчик не блокируется
    game["anim_id"] += 1
    asyncio.create_task(boss_flash(uid, "hurt" if hit else "attack", game["anim_id"]))

    msg = f"🧪 Зелье! Босс −{BOSS_DAMAGE} HP" if hit else f"❌ Промах! Тебе −{PLAYER_DAMAGE} HP"
    if boss_attacked:
        msg += f" | ⚔️ Босс −{BOSS_ATTACK_DAMAGE}!"
    await call.answer(msg)


@cr.callback_query(F.data == "boss_surrender")
async def boss_surrender(call: types.CallbackQuery):
    uid = call.from_user.id
    game = boss_games.get(uid)
    if not game:
        await call.answer("Нет активной игры.")
        return
    boss_lock["current"] = None
    boss_cooldowns[uid] = datetime.now()
    boss_games.pop(uid, None)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"rad_back_{uid}")]
    ])
    await call.answer("Сдался")
    try:
        await call.message.delete()
    except Exception:
        pass
    try:
        await call.message.answer_photo(FSInputFile(BOSS_NORMAL), caption="🏳 *Ты сдался!*\n\n⏳ Кулдаун: 30 минут",
                                        reply_markup=kb, parse_mode="Markdown")
    except Exception:
        pass


# ==================== ПРОСМОТР КАРТОЧЕК ====================
@cr.message(Command("cards"))
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


@cr.callback_query(F.data.startswith("cards_next_"))
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


@cr.callback_query(F.data.startswith("cards_prev_"))
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


@cr.callback_query(F.data == "cards_noop")
async def cards_noop(call: types.CallbackQuery):
    await call.answer()


@cr.callback_query(F.data.startswith("cards_close_"))
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


@cr.callback_query(F.data.startswith("cards_search_"))
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


@cr.callback_query(F.data.startswith("card_show_"))
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
    rarity = card_data.get("rarity") or card_rarity(card_data["name"])
    price = card_data["price"]
    if card_data["name"] == "Всегда рядом":
        price_text = f"{price} ☢️ (не продаётся)"
    elif card_data["name"] == "Побеждённый король 👑":
        price_text = "1000 ☢️"
    else:
        price_text = f"{price} монет"
    caption = f"🎴 *{card_data['name']}*\nРедкость: {rarity}\n💰 Цена: {price_text}\n📦 У тебя: {cnt} шт."
    try:
        photo = FSInputFile(card_data["file"])
        await call.message.answer_photo(photo, caption=caption, parse_mode="Markdown")
    except Exception:
        await call.message.answer(caption, parse_mode="Markdown")
    await call.answer()


# ==================== ТРЕЙД ====================
@cr.message(Command("trade"))
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


@cr.callback_query(F.data.startswith("tr_myn_"))
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


@cr.callback_query(F.data.startswith("tr_myp_"))
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


@cr.callback_query(F.data.startswith("tr_cancel_"))
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


@cr.callback_query(F.data.startswith("tr_mys_"))
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


@cr.callback_query(F.data.startswith("tr_my_"))
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


@cr.callback_query(F.data.startswith("tr_hisn_"))
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


@cr.callback_query(F.data.startswith("tr_hisp_"))
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


@cr.callback_query(F.data.startswith("tr_back_"))
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


@cr.callback_query(F.data.startswith("tr_his_"))
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
            f"🤝 *Тебе предложили трейд!*\n\n👤 От: @{my_username}\n\n"
            f"📤 Ты отдаёшь: *{full_name}*\n📥 Ты получаешь: *{my_card}*\n\nПодтвердить?",
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


@cr.callback_query(F.data.startswith("tr_acc_"))
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


@cr.callback_query(F.data.startswith("tr_dec_"))
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


# ==================== CANCEL ====================
@cr.message(Command("cancel"))
async def cancel_game(message: types.Message):
    uid = message.from_user.id
    cancelled = False
    for d in (color_games, miner_games, coin_games, wheel_games,
              trade_games, cards_view_games, rad_convert_games):
        if uid in d:
            del d[uid]
            cancelled = True
    if uid in boss_games:
        if boss_lock["current"] == uid:
            boss_lock["current"] = None
        boss_cooldowns[uid] = datetime.now()
        del boss_games[uid]
        cancelled = True
    if cancelled:
        await message.answer("❌ Отменено.")
    else:
        await message.answer("Нет активного действия.")


# ==================== ПРОФИЛЬ / ТОП / ПРОДАЖА / АПГРЕЙД ====================
@cr.message(Command("profile"))
async def profile(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        tu = args[1].lstrip("@").strip()
        cur.execute("SELECT user_id, username, balance, level, registered_at FROM users WHERE username = ?", (tu,))
        row = cur.fetchone()
        if not row:
            await message.answer(f"❌ @{html.escape(tu)} не найден.")
            return
        tid, tun, balance, level, reg = row
    else:
        tid = message.from_user.id
        tun = message.from_user.username
        balance, _, level, reg, _, _, _ = get_user(tid, tun)
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
        await message.answer(caption + f"\n\nОшибка картинки: {html.escape(str(e))}")


@cr.message(Command("top"))
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


@cr.message(Command("sell"))
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
    if real_name == "Всегда рядом":
        await message.answer("❌ «Всегда рядом» нельзя продать. Только трейд.")
        return
    hw = find_hw_card(real_name)
    rad = find_rad_card(real_name)
    cd = next((c for c in cards if c["name"].lower() == real_name.lower()), None)
    if hw:
        cur.execute("DELETE FROM inventory WHERE rowid = ?", (row[0],))
        cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (hw["price"], uid))
        db.commit()
        await message.answer(f"✅ Продано: {hw['name']} за {hw['price']} монет")
        return
    if rad:
        cur.execute("DELETE FROM inventory WHERE rowid = ?", (row[0],))
        if rad["name"] == "Побеждённый король 👑":
            cur.execute("UPDATE users SET tokens = tokens + 1000 WHERE user_id = ?", (uid,))
            db.commit()
            await message.answer(f"✅ Продано: {rad['name']} за 1000 ☢️")
        else:
            cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (rad["price"], uid))
            db.commit()
            await message.answer(f"✅ Продано: {rad['name']} за {rad['price']} монет")
        return
    if not cd:
        await message.answer("❌ Неизвестная карта.")
        return
    cur.execute("DELETE FROM inventory WHERE rowid = ?", (row[0],))
    cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (cd["price"], uid))
    db.commit()
    await message.answer(f"✅ Продано: {cd['name']} за {cd['price']} монет")


@cr.message(Command("sellall"))
async def sellall(message: types.Message):
    uid = message.from_user.id
    cur.execute("SELECT card_name, COUNT(*) FROM inventory WHERE user_id = ? GROUP BY card_name", (uid,))
    rows = cur.fetchall()
    if not rows:
        await message.answer("❌ Нет карточек.")
        return
    total_money = 0
    total_tokens = 0
    text = "💰 *Будет продано:*\n\n"
    skipped = []
    for name, cnt in rows:
        if name == "Всегда рядом":
            skipped.append(name)
            continue
        if name == "Побеждённый король 👑":
            total_tokens += 1000 * cnt
            text += f"• {name} × {cnt} = {1000 * cnt} ☢️\n"
            continue
        cd = find_any_card(name)
        if not cd:
            continue
        subtotal = cd["price"] * cnt
        total_money += subtotal
        text += f"• {name} × {cnt} = {subtotal} монет\n"
    text += f"\n💵 *Монет: {total_money}*"
    if total_tokens:
        text += f"\n☢️ *Токенов: {total_tokens}*"
    if skipped:
        text += f"\n\n⚠️ Не продаются: {', '.join(skipped)}"
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Да", callback_data="sellall_yes"),
        InlineKeyboardButton(text="❌ Нет", callback_data="sellall_no"),
    ]])
    sell_games[uid] = {"money": total_money, "tokens": total_tokens}
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")


@cr.callback_query(F.data == "sellall_yes")
async def sellall_yes(call: types.CallbackQuery):
    uid = call.from_user.id
    g = sell_games.pop(uid, None)
    if not g:
        await call.answer("Уже продано.", show_alert=True)
        return
    cur.execute("SELECT rowid, card_name FROM inventory WHERE user_id = ?", (uid,))
    rows = cur.fetchall()
    total_money = 0
    total_tokens = 0
    for rowid, name in rows:
        if name == "Всегда рядом":
            continue
        if name == "Побеждённый король 👑":
            total_tokens += 1000
            cur.execute("DELETE FROM inventory WHERE rowid = ?", (rowid,))
            continue
        cd = find_any_card(name)
        if not cd:
            continue
        total_money += cd["price"]
        cur.execute("DELETE FROM inventory WHERE rowid = ?", (rowid,))
    cur.execute("UPDATE users SET balance = balance + ?, tokens = tokens + ? WHERE user_id = ?",
                (total_money, total_tokens, uid))
    db.commit()
    text = f"✅ Продано!\n💰 +{total_money} монет"
    if total_tokens:
        text += f"\n☢️ +{total_tokens} токенов"
    await call.message.edit_text(text)
    await call.answer("Готово!")


@cr.callback_query(F.data == "sellall_no")
async def sellall_no(call: types.CallbackQuery):
    sell_games.pop(call.from_user.id, None)
    await call.message.edit_text("❌ Отменено.")
    await call.answer()


@cr.message(Command("upgrade"))
async def upgrade(message: types.Message):
    uid = message.from_user.id
    balance, _, level, _, _, _, _ = get_user(uid, message.from_user.username)
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


@cr.callback_query(F.data.startswith("upg_"))
async def upg_cb(call: types.CallbackQuery):
    uid = call.from_user.id
    balance, _, level, _, _, _, _ = get_user(uid, call.from_user.username)
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


# ==================== RESET (DEV) ====================
def reset_user(uid, money_only=False):
    if money_only:
        cur.execute("UPDATE users SET balance = 0, hw_balance = 0, tokens = 0 WHERE user_id = ?", (uid,))
    else:
        cur.execute(
            "UPDATE users SET balance = 0, hw_balance = 0, tokens = 0, level = 1, "
            "last_card = NULL, last_daily = NULL, last_trade = NULL WHERE user_id = ?", (uid,))
        cur.execute("DELETE FROM inventory WHERE user_id = ?", (uid,))
    cur.execute("DELETE FROM rad_cooldowns WHERE user_id = ?", (uid,))
    db.commit()
    for d in (color_games, miner_games, coin_games, wheel_games,
              trade_games, cards_view_games, sell_games, rad_convert_games):
        d.pop(uid, None)
    boss_cooldowns.pop(uid, None)


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


@cr.message(Command("reset"))
async def reset_cmd(message: types.Message):
    if message.from_user.id != DEV_ID:
        return
    tokens = message.text.split()[1:]
    if not tokens:
        await message.answer("/reset @user1 @user2 — полный сброс\n/resetmoney @user — деньги\n/resetall — всех")
        return
    ids, missing = find_targets(tokens)
    for u in ids:
        reset_user(u)
    text = f"✅ Сброшено игроков: {len(ids)}"
    if missing:
        text += f"\n❌ Не найдены: {html.escape(', '.join(map(str, missing)))}"
    await message.answer(text)


@cr.message(Command("resetmoney"))
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
    text = f"✅ Деньги обнулены у: {len(ids)}"
    if missing:
        text += f"\n❌ Не найдены: {html.escape(', '.join(map(str, missing)))}"
    await message.answer(text)


@cr.message(Command("resetall"))
async def resetall_cmd(message: types.Message):
    if message.from_user.id != DEV_ID:
        return
    cur.execute("SELECT COUNT(*) FROM users")
    n = cur.fetchone()[0]
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⚠️ ДА, обнулить всех", callback_data="resetall_yes"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="resetall_no"),
    ]])
    await message.answer(f"⚠️ Удалит всё у {n} игроков. Точно?", reply_markup=kb)


@cr.callback_query(F.data == "resetall_yes")
async def resetall_yes(call: types.CallbackQuery):
    if call.from_user.id != DEV_ID:
        await call.answer("Нет доступа", show_alert=True)
        return
    cur.execute("SELECT user_id FROM users")
    for (u,) in cur.fetchall():
        reset_user(u)
    await call.message.edit_text("✅ Все игроки обнулены.")
    await call.answer()


@cr.callback_query(F.data == "resetall_no")
async def resetall_no(call: types.CallbackQuery):
    if call.from_user.id != DEV_ID:
        await call.answer("Нет доступа", show_alert=True)
        return
    await call.message.edit_text("❌ Отменено.")
    await call.answer()


# ==================== COLOR DICE: игра с видео ====================
async def play_color_dice(message, uid, username, chosen, bet):
    result = [random.choice(COLORS) for _ in range(4)]
    matches = sum(1 for c in result if c["code"] == chosen["code"])
    head = (
        f"🎲 *Color Dice* — @{username}\n"
        f"Твой цвет: {chosen['emoji']} {chosen['name']}\n"
        f"💰 Ставка: {bet}"
    )
    shown = " ".join(c["emoji"] for c in result)
    names = ", ".join(f"{c['emoji']} {c['name']}" for c in result)
    if matches == 1:
        win = bet * 2
        cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (win, uid))
        db.commit()
        verdict = f"🎉 *Выиграл {win} монет!* (×2)"
    elif matches == 4:
        win = bet * 4
        cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (win, uid))
        db.commit()
        verdict = f"🎉 *ДЖЕКПОТ! +{win}!* (×4)"
    else:
        verdict = f"❌ *Проиграл {bet} монет.*"
    result_text = (
        f"{head}\n\n"
        f"🎨 *Выпало:*\n{names}\n\n"
        f"{shown}\n"
        f"Совпадений: {matches}\n{verdict}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲 Играть снова", callback_data=f"casino_color_{uid}")],
        [InlineKeyboardButton(text="🔙 Casino", callback_data=f"open_casino_{uid}")],
    ])

    sent = await send_dice_video(message, result, f"{head}\n\n🎲 Кубики падают...")
    if sent:
        await asyncio.sleep(DICE_SECONDS + 0.3)
        try:
            await sent.edit_caption(caption=result_text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await message.answer(result_text, reply_markup=kb, parse_mode="Markdown")
        return

    # запасной вариант без видео — старая анимация эмодзи
    msg = await message.answer(f"{head}\n\n🎲 Крутим...", parse_mode="Markdown")
    await asyncio.sleep(0.8)
    progressive = []
    for c in result:
        for _ in range(2):
            flick = random.choice(COLORS)["emoji"]
            await safe_edit(msg, f"{head}\n\n{' '.join(progressive + [flick])}", parse_mode="Markdown")
            await asyncio.sleep(0.4)
        progressive.append(c["emoji"])
        await safe_edit(msg, f"{head}\n\n{' '.join(progressive)}", parse_mode="Markdown")
        await asyncio.sleep(0.6)
    await safe_edit(msg, result_text, reply_markup=kb, parse_mode="Markdown")


# ==================== ВВОД ЧИСЛА (ставки, токены) ====================
@cr.message(F.text.regexp(r"^\d+$"))
async def handle_number(message: types.Message):
    uid = message.from_user.id
    username = message.from_user.username or message.from_user.full_name or "Игрок"

    # Покупка токенов
    conv = rad_convert_games.get(uid)
    if conv and conv.get("state") == "wait_tokens":
        amount = int(message.text)
        if amount <= 0:
            await message.answer("❌ Больше 0.")
            return
        cost = amount * TOKEN_RATE
        balance, _, _, _, _, _, tokens = get_user(uid, message.from_user.username)
        if balance < cost:
            await message.answer(f"❌ Нужно {cost} монет, у тебя {balance}.")
            return
        cur.execute("UPDATE users SET balance = balance - ?, tokens = tokens + ? WHERE user_id = ?", (cost, amount, uid))
        db.commit()
        del rad_convert_games[uid]
        _, _, _, _, _, _, new_tokens = get_user(uid)
        await message.answer(f"✅ Куплено {amount} ☢️ за {cost} монет.\n☢️ Теперь: {new_tokens}")
        return

    # Color Dice
    game = color_games.get(uid)
    if game and game.get("state") == "wait_bet":
        bet = int(message.text)
        if bet <= 0:
            await message.answer("❌ Ставка больше 0.")
            return
        balance, _, _, _, _, _, _ = get_user(uid, message.from_user.username)
        if balance < bet:
            await message.answer(f"❌ Не хватает. У тебя {balance}.")
            return
        cur.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (bet, uid))
        db.commit()
        chosen = game["color"]
        del color_games[uid]
        await play_color_dice(message, uid, username, chosen, bet)
        return

    # Минёр
    game = miner_games.get(uid)
    if game and game.get("state") == "wait_bet":
        bet = int(message.text)
        if bet <= 0:
            await message.answer("❌ Ставка больше 0.")
            return
        balance, _, _, _, _, _, _ = get_user(uid, message.from_user.username)
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

    # Колесо монстров
    game = wheel_games.get(uid)
    if game and game.get("state") == "wait_bet":
        bet = int(message.text)
        if bet <= 0:
            await message.answer("❌ Ставка больше 0.")
            return
        balance, _, _, _, _, _, _ = get_user(uid, message.from_user.username)
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
        head = f"{wheel_head}\n\nВыпал: {seg['emoji']} *{seg['name']}* (×{seg['mult']})\n\n"
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

    # Орёл и Решка
    game = coin_games.get(uid)
    if game and game.get("state") == "wait_bet":
        bet = int(message.text)
        if bet <= 0:
            await message.answer("❌ Ставка больше 0.")
            return
        balance, _, _, _, _, _, _ = get_user(uid, message.from_user.username)
        if balance < bet:
            await message.answer(f"❌ Не хватает. У тебя {balance}.")
            return
        cur.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (bet, uid))
        db.commit()
        choice = game["choice"]
        del coin_games[uid]
        my_choice_emoji = "🦅" if choice == "heads" else "🪙"
        my_choice_name = "Орёл" if choice == "heads" else "Монета"
        coin_head = f"🪙 *Орёл и Решка* — @{username}\nТвой выбор: {my_choice_emoji} {my_choice_name}\n💰 Ставка: {bet}"
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


# ==================== ВВОД ТЕКСТА (поиск по картам / трейду) ====================
def user_has_pending_input(uid) -> bool:
    """Игрок сейчас вводит ставку/поиск — RP-команды его не трогают."""
    for d in (color_games, miner_games, coin_games, wheel_games, rad_convert_games):
        if uid in d:
            return True
    g = cards_view_games.get(uid)
    if g and g.get("state") == "wait_search":
        return True
    g = trade_games.get(uid)
    if g and g.get("state") == "wait_search_my":
        return True
    return False


def _wait_search_text(m: Message) -> bool:
    """Фильтр: хендлер срабатывает ТОЛЬКО если юзер ждёт ввода поиска.
    Иначе текст идёт дальше (в RP-обработчик)."""
    if not m.from_user or not m.text or m.text.startswith("/"):
        return False
    uid = m.from_user.id
    g = cards_view_games.get(uid)
    if g and g.get("state") == "wait_search":
        return True
    g = trade_games.get(uid)
    return bool(g and g.get("state") == "wait_search_my")


@cr.message(F.text, _wait_search_text)
async def handle_text(message: types.Message):
    uid = message.from_user.id
    g = cards_view_games.get(uid)
    if g and g.get("state") == "wait_search":
        g["filter"] = message.text.strip()
        g["page"] = 0
        g["state"] = None
        await send_cards_page(message, uid)
        return
    g = trade_games.get(uid)
    if g and g.get("state") == "wait_search_my":
        query = message.text.strip().lower()
        filtered = [n for n in g["my_cards"] if query in n.lower()]
        if not filtered:
            await message.answer("🔍 Ничего не найдено.")
            return
        g["my_cards"] = filtered
        g["page"] = 0
        g["state"] = None
        await send_trade_my_page(message, uid)
        return


# ═════════════════════════════════════════════════════════════════
# ═══════════════════════  RP-ДЕЙСТВИЯ  ═════════════════════════════
# ═════════════════════════════════════════════════════════════════
ACTION_COMMANDS = {
    # ==== СТАРЫЕ ====
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

    # ==== ФИЗИЧЕСКИЕ ====
    "ударить":           "👊 Ударил {user}",
    "пнуть":             "🦶 Пнул {user}",
    "шлёпнуть":          "🍑 Шлёпнул {user}",
    "толкнуть":          "💥 Толкнул {user}",
    "схватить":          "🤏 Схватил {user}",
    "уронить":           "⬇️ Уронил {user}",
    "поднять":           "⬆️ Поднял {user}",
    "обнять":            "🤗 Обнял {user}",
    "поцеловать":        "💋 Поцеловал {user}",
    "прижать":           "🫂 Прижал {user}",
    "задушить":          "🤏 Задушил {user}",
    "укусить":           "🦷 Укусил {user}",
    "ущипнуть":          "👌 Ущипнул {user}",
    "погладить":         "🤚 Погладил {user}",
    "пощекотать":        "🪶 Пощекотал {user}",
    "лизнуть":           "👅 Лизнул {user}",
    "облизать":          "😋 Облизал {user}",
    "жмякнуть":          "👆 Жмякнул {user}",
    "потрогать":         "🤚 Потрогал {user}",
    "нокаутировать":     "💫 Нокаутировал {user}",
    "перепрыгнуть":      "🦘 Перепрыгнул {user}",

    # ==== НАРКОТИКИ ====
    "дать наркоты":      "💊 Дал наркоты {user}",
    "покурить":          "🚬 Покурил с {user}",
    "уколоть":           "💉 Уколол {user}",
    "подсадить":         "🌿 Подсадил {user}",
    "вылечить":          "💚 Вылечил {user}",
    "откачать":          "⚡ Откачал {user}",
    "напоить":           "🍷 Напоил {user}",
    "оплодотворить":     "🧬 Оплодотворил {user}",
    "осеменить":         "🌱 Осеменил {user}",

    # ==== ВЛАСТЬ ====
    "приказать":         "📢 Приказал {user}",
    "запретить":         "🚫 Запретил {user}",
    "разрешить":         "✅ Разрешил {user}",
    "наказать":          "⚖️ Наказал {user}",
    "наградить":         "🏅 Наградил {user}",
    "повысить":          "⬆️ Повысил {user}",
    "понизить":          "⬇️ Понизил {user}",
    "короновать":        "👑 Короновал {user}",
    "уволить":           "💼 Уволил {user}",

    # ==== ДЕЛОВЫЕ ====
    "нанять":            "🤝 Нанял {user}",
    "заплатить":         "💵 Заплатил {user}",
    "кинуть":            "🎭 Кинул {user}",
    "продать":           "💰 Продал {user}",
    "купить":            "🛒 Купил {user}",
    "обменять":          "🔄 Обменял {user}",
    "задолжать":         "📝 Задолжал {user}",

    # ==== СМЕШНЫЕ ====
    "пёрнуть в лицо":    "💨 Пёрнул в лицо {user}",
    "обоссать":          "💦 Обоссал {user}",
    "обосрать":          "💩 Обосрал {user}",
    "рыгнуть":           "🗣 Рыгнул на {user}",
    "плюнуть":           "💧 Плюнул на {user}",
    "чихнуть":           "🤧 Чихнул на {user}",
    "кашлянуть":         "😷 Кашлянул на {user}",
    "поковырять в носу": "👃 Поковырял в носу у {user}",
    "отрыгнуть":         "🤮 Отрыгнул на {user}",
    "вырвать":           "🤢 Вырвало на {user}",
    "подавиться":        "😵 Подавился {user}",

    # ==== МАГИЧЕСКИЕ ====
    "проклясть":         "🧙 Проклял {user}",
    "загипнотизировать": "🌀 Загипнотизировал {user}",
    "воскресить":        "✨ Воскресил {user}",
    "превратить":        "🪄 Превратил {user}",
    "телепортировать":   "🌌 Телепортировал {user}",
    "благословить":      "🙏 Благословил {user}",
    "сглазить":          "👁 Сглазил {user}",
    "вызвать дьявола":   "😈 Вызвал дьявола с {user}",

    # ==== ЖЁСТКИЕ ====
    "убить":             "🔪 Убил {user}",
    "зарезать":          "🗡 Зарезал {user}",
    "повесить":          "🪢 Повесил {user}",
    "утопить":           "🌊 Утопил {user}",
    "сжечь":             "🔥 Сжёг {user}",
    "взорвать":          "💣 Взорвал {user}",
    "отравить":          "☠️ Отравил {user}",
    "закопать":          "⚰️ Закопал {user}",
    "расчленить":        "🪓 Расчленил {user}",
    "съесть":            "🍽 Съел {user}",
    "уничтожить":        "💥 Уничтожил {user}",
    "изнасиловать":      "💀 Изнасиловал {user}",
    "застрелить":        "🔫 Застрелил {user}",
    "отомстить":         "😈 Отомстил {user}",

    # ==== ЭМОЦИИ ====
    "простить":          "🕊 Простил {user}",
    "извиниться":        "🙏 Извинился перед {user}",
    "пожалеть":          "🥺 Пожалел {user}",
    "утешить":           "🤗 Утешил {user}",
    "поздравить":        "🎉 Поздравил {user}",
    "обидеть":           "😢 Обидел {user}",

    # ==== НОВЫЕ 25 ====
    "пресследовать":     "📚 Преследую {user}",
    "наблюдать":         "👀 Наблюдаю за {user}",
    "влюбиться":         "❤️ Влюбился в {user}",
    "запереть":          "🔒 Запер {user} в клетке",
    "убить ради":        "🔪 Убил ради {user}",
    "стереть":           "🧽 Стёр {user} из жизни",
    "найти":             "🔍 Нашёл {user}",
    "стереть данные":    "💾 Стёр данные {user}",
    "хакнуть телефон":   "📱 Хакнул телефон {user}",
    "прочитать мысли":   "🧠 Прочитал мысли {user}",
    "отправить в прошлое": "⏰ Отправил {user} в прошлое",
    "сломать систему":   "🖥 Сломал систему {user}",
    "обнулить":          "💥 Обнулил {user}",
    "упаковать":         "🎁 Упаковал {user} в пакеты",
    "сдать в полицию":   "🚔 Сдал {user} в полицию",
    "принести в жертву": "🩸 Принёс {user} в жертву",
    "обезвредить":       "💉 Обезвредил {user}",
    "сдать кровь":       "🩸 Взял кровь у {user}",
    "поймать":           "🕸 Поймал {user}",
    "оценить":           "📊 Оценил {user} как жертву",
    "разбить голову":    "🔨 Разбил голову {user}",
    "ударить битой":     "🏏 Ударил битой {user}",
    "сбросить":          "🏢 Сбросил {user} с крыши",
    "проткнуть":         "🗡 Проткнул {user}",
    "раздавить":         "🦶 Раздавил {user}",
}

# длинные команды проверяем первыми («убить ради» раньше, чем «убить»)
ACTION_KEYS_SORTED = sorted(ACTION_COMMANDS.keys(), key=len, reverse=True)

ACTIONS_HELP = (
    "👋 *Бот-действия*\n\n"
    "📋 *Как использовать:*\n"
    "• Реплай на сообщение + команда\n"
    "• Или команда + @username\n"
    "• Или просто команда — сам с собой\n\n"
    "💪 *Физические:* ударить, пнуть, шлёпнуть, толкнуть, схватить, уронить, поднять, обнять, поцеловать, прижать, задушить, укусить, ущипнуть, погладить, пощекотать, лизнуть, облизать, жмякнуть, потрогать, нокаутировать, перепрыгнуть\n\n"
    "💊 *Наркотики:* выпить, набухаться, дать наркоты, покурить, уколоть, подсадить, вылечить, откачать, напоить, оплодотворить, осеменить\n\n"
    "👑 *Власть:* приказать, запретить, разрешить, наказать, наградить, повысить, понизить, короновать, уволить\n\n"
    "💼 *Деловые:* нанять, заплатить, кинуть, продать, купить, обменять, задолжать\n\n"
    "🤡 *Смешные:* напердеть, пёрнуть в лицо, обоссать, обосрать, рыгнуть, плюнуть, чихнуть, кашлянуть, поковырять в носу, отрыгнуть, вырвать, подавиться, брызнуть\n\n"
    "⚡ *Магические:* проклясть, загипнотизировать, воскресить, превратить, телепортировать, благословить, сглазить, вызвать дьявола\n\n"
    "😈 *Жёсткие:* убить, зарезать, повесить, утопить, сжечь, взорвать, отравить, закопать, расчленить, съесть, уничтожить, изнасиловать, застрелить, отомстить, убиться, разрубить, проткнуть, раздавить, разбить голову, ударить битой, сбросить\n\n"
    "🎭 *Эмоции:* простить, извиниться, пожалеть, утешить, поздравить, обидеть, трахнуть, кончить, принять участие, отсексафонить, нарисовать, обмануть, взломать\n\n"
    "🆕 *Новые:* пресследовать, наблюдать, влюбиться, запереть, убить ради, стереть, найти, стереть данные, хакнуть телефон, прочитать мысли, отправить в прошлое, сломать систему, обнулить, упаковать, сдать в полицию, принести в жертву, обезвредить, сдать кровь, поймать, оценить"
)


@rp.message(Command("actions"))
async def cmd_actions(message: Message):
    await message.answer(ACTIONS_HELP, parse_mode="Markdown")


# Этот обработчик ДОЛЖЕН быть последним: он ловит любой текст
@rp.message(F.text)
async def action_command(message: Message):
    if not message.from_user:
        return
    uid = message.from_user.id
    if ACTIONS_DEV_ONLY and uid != DEV_ID:
        return
    text = (message.text or "").strip()
    if not text or text.startswith("/"):
        return

    # игрок вводит ставку/поиск — не мешаем
    if user_has_pending_input(uid):
        return

    # пока в чате идёт мафия, RP-команды не мешают игре
    if not ACTIONS_DURING_GAME:
        g = games.get(message.chat.id)
        if g and g.state not in ("lobby", "ended"):
            return

    low = text.lower()
    matched = None
    for cmd in ACTION_KEYS_SORTED:
        if low == cmd or low.startswith(cmd + " ") or low.startswith(cmd + "@"):
            matched = cmd
            break
    if not matched:
        return

    target_mention = None

    # 1) Реплай
    if message.reply_to_message and message.reply_to_message.from_user:
        target_user = message.reply_to_message.from_user
        if target_user.id == uid:
            target_mention = "сам с собой"
        elif target_user.username:
            target_mention = f"@{target_user.username}"
        else:
            target_mention = target_user.full_name

    # 2) @username в тексте
    if not target_mention:
        rest = text[len(matched):].strip()
        if rest.startswith("@") and len(rest) > 1:
            uname = rest.split()[0].lstrip("@")
            target_mention = f"@{uname}"

    # 3) Без указания
    if not target_mention:
        target_mention = "сам с собой"

    result = ACTION_COMMANDS[matched].format(user=target_mention)
    # parse_mode=None: имена могут содержать < > &, а у бота по умолчанию HTML
    await message.reply(result, parse_mode=None)


# ───────────────────────── ЗАПУСК ─────────────────────────
async def main():
    global BOT_USERNAME
    me = await bot.get_me()
    BOT_USERNAME = me.username
    log.info("Бот @%s запущен", BOT_USERNAME)

    dp = Dispatcher()
    # тишина в группе во время мафии (ночью — никто, днём — только игроки)
    dp.message.outer_middleware(GroupGuard())
    # порядок важен: мафия -> карточки -> RP (RP ловит любой текст, поэтому последний)
    dp.include_router(router)
    dp.include_router(cr)
    dp.include_router(rp)

    await bot.delete_webhook(drop_pending_updates=True)
    prerender_task = asyncio.create_task(prerender_videos())
    try:
        await dp.start_polling(bot)
    finally:
        prerender_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
