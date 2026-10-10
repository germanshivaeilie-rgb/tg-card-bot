# -*- coding: utf-8 -*-
"""
🎭 Mafia Bot + бот RP-действий (всё в одном) — Telegram (aiogram 3.x), запуск на Railway.

Роли: Дон, Мафия, Комиссар, Доктор, Мирный житель
Кастомные: Обманщик, Алкаш

Переменные окружения (Railway -> Variables):
  BOT_TOKEN     — токен от @BotFather (обязательно)
  MIN_PLAYERS   — минимум игроков (по умолчанию 4)
  MAX_PLAYERS   — максимум игроков (по умолчанию 20)
  REG_SECONDS   — время набора, сек (120)
  NIGHT_SECONDS — длительность ночи, сек (60)
  DAY_SECONDS   — обсуждение днём, сек (90)
  VOTE_SECONDS  — голосование, сек (45)
"""
import asyncio
import html
import logging
import os
import random
from collections import Counter
from dataclasses import dataclass
from typing import Optional

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatMemberStatus, ChatType, ParseMode
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("mafia")

# ───────────────────────── НАСТРОЙКИ ─────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN")
MIN_PLAYERS = int(os.getenv("MIN_PLAYERS", "4"))
MAX_PLAYERS = int(os.getenv("MAX_PLAYERS", "20"))
REG_SECONDS = int(os.getenv("REG_SECONDS", "120"))
NIGHT_SECONDS = int(os.getenv("NIGHT_SECONDS", "60"))
DAY_SECONDS = int(os.getenv("DAY_SECONDS", "90"))
VOTE_SECONDS = int(os.getenv("VOTE_SECONDS", "45"))
REVEAL_ROLES = True        # показывать роль погибшего/казнённого
DON_LOOKS_PEACEFUL = True  # комиссар видит Дона как мирного
ACTIONS_DURING_GAME = False  # False = RP-команды («ударить», «выпить»...) молчат, пока в чате идёт мафия

bot: Bot = None  # создаётся в main()
BOT_USERNAME = ""

# ───────────────────────── РОЛИ ─────────────────────────
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
         "Каждую ночь мафия голосует, кого убить. При равенстве голосов решает твой выбор. "
         "Комиссар видит тебя мирным жителем.",
    MAFIA: "Каждую ночь вместе с Доном выбираешь жертву. "
           "Ночью можешь писать союзникам прямо сюда — бот перешлёт им твои сообщения.",
    COMMISSAR: "Каждую ночь проверяешь одного игрока и узнаёшь, мафия он или нет. "
               "(Дон выглядит мирным.)",
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
    "check": "🕵️ Кого проверим этой ночью?",
    "heal": "💉 Кого вылечим этой ночью?",
    "drink": "🍺 Кого уведёшь домой выпивать?",
}

# Эти же тексты уходят в группу и от настоящих ролей, и от Обманщика
ANNOUNCE = {
    "kill": "🔪 Мафия сделала свой выбор...",
    "check": "🕵️ Комиссар отправился на поиски мафии...",
    "heal": "💉 Доктор поспешил кому-то на помощь...",
    "drink": "🍺 Алкаш утащил кого-то домой выпивать...",
}

FAKE_LABEL = {
    "kill": "🔪 Убить (как мафия)",
    "check": "🕵️ Проверить (как комиссар)",
    "heal": "💉 Вылечить (как доктор)",
    "drink": "🍺 Увести бухать (как алкаш)",
}

RULES_TEXT = (
    "📖 <b>Правила</b>\n\n"
    "Город делится на мирных и мафию. Игра идёт кругами: ночь → день → голосование.\n\n"
    "🌙 <b>Ночью</b> роли получают меню в личке бота и делают ход.\n"
    "☀️ <b>Днём</b> все обсуждают, кто мафия.\n"
    "⚖️ <b>Голосование</b> — кого казнить (кнопки в группе).\n\n"
    "<b>Роли:</b>\n"
    + "\n\n".join(f"{ROLE_TITLE[r]}\n{ROLE_DESC[r]}" for r in
                  (DON, MAFIA, COMMISSAR, DOCTOR, CIVILIAN, DECEIVER, ALCOHOLIC))
    + "\n\n🏆 <b>Победа мирных:</b> убиты Дон и вся мафия.\n"
      "🏆 <b>Победа мафии:</b> мафия (с Обманщиком) сравнялась по числу с остальными."
)

HELP_TEXT = (
    "🎭 <b>Бот для игры в Мафию</b>\n\n"
    "1. Добавь меня в группу (лучше сделай админом).\n"
    "2. В группе напиши /game — начнётся набор.\n"
    "3. Каждый игрок жмёт «Присоединиться» и здесь нажимает «Запустить».\n"
    "4. Когда все готовы — /startgame (или игра стартует сама по таймеру).\n\n"
    "Команды:\n"
    "/game — новая игра\n/startgame — начать сейчас\n/leave — выйти из набора\n"
    "/alive — кто жив\n/stop — остановить игру (админ)\n/rules — правила\n\n"
    "🎬 <b>RP-действия</b> (ударить, обнять, выпить...) — список: /actions"
)


# ───────────────────────── МОДЕЛИ ─────────────────────────
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
router = Router()
GROUP_TYPES = {ChatType.GROUP, ChatType.SUPERGROUP}


# ───────────────────────── ХЕЛПЕРЫ ─────────────────────────
async def send(chat_id: int, text: str, **kw) -> Optional[Message]:
    try:
        return await bot.send_message(chat_id, text, **kw)
    except TelegramAPIError as e:
        log.warning("send to %s failed: %s", chat_id, e)
        return None


async def safe_edit(cb: CallbackQuery, text: str, markup=None):
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
    cur = asyncio.current_task()
    for t in (g.lobby_task, g.task):
        if t and t is not cur and not t.done():
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


# ───────────────────────── ЛОББИ ─────────────────────────
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


# ───────────────────────── КОМАНДЫ ─────────────────────────
@router.message(CommandStart(deep_link=True), F.chat.type == ChatType.PRIVATE)
async def start_deeplink(m: Message, command: CommandObject):
    arg = command.args or ""
    if not arg.startswith("join_"):
        await m.answer(HELP_TEXT)
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


@router.message(CommandStart(), F.chat.type == ChatType.PRIVATE)
async def start_plain(m: Message):
    await m.answer(HELP_TEXT)


@router.message(Command("help"))
async def cmd_help(m: Message):
    await m.answer(HELP_TEXT)


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


# ───────────────────────── ИГРОВОЙ ЦИКЛ ─────────────────────────
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


# ───────────────────────── НОЧЬ ─────────────────────────
def night_targets(g: Game, p: Player, kind: str) -> list[Player]:
    alive = g.alive()
    if kind == "kill":
        return [q for q in alive if q.role not in KILLERS]
    if kind == "heal":
        return [q for q in alive
                if q.user_id != p.last_heal and not (q.user_id == p.user_id and p.self_healed)]
    return [q for q in alive if q.user_id != p.user_id]  # check / drink


def skip_row(g: Game):
    return InlineKeyboardButton(text="😴 Пропустить", callback_data=f"skip:{g.chat_id}")


def targets_kb(g: Game, prefix: str, targets: list[Player], back: bool = False):
    b = InlineKeyboardBuilder()
    for t in targets:
        b.button(text=t.name[:30], callback_data=f"{prefix}:{t.user_id}")
    b.adjust(2)
    if back:
        b.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"fkb:{g.chat_id}"))
    b.row(skip_row(g))
    if g.chat_link:
        b.row(InlineKeyboardButton(text="Перейти в группу", url=g.chat_link))
    return b.as_markup()


def deceiver_menu_kb(g: Game):
    b = InlineKeyboardBuilder()
    for kind in ("kill", "check", "heal", "drink"):
        b.row(InlineKeyboardButton(text=FAKE_LABEL[kind], callback_data=f"fk:{g.chat_id}:{kind}"))
    b.row(skip_row(g))
    if g.chat_link:
        b.row(InlineKeyboardButton(text="Перейти в группу", url=g.chat_link))
    return b.as_markup()


def deceiver_menu_text(g: Game) -> str:
    return (f"🌙 <b>Ночь {g.day}</b>\n🎭 Ты Обманщик. Выбери действие — в группе появится "
            f"такое же сообщение, как от настоящей роли (на деле ничего не произойдёт). "
            f"Можно одно действие за ночь.")


async def send_night_menu(g: Game, p: Player):
    if p.role == DECEIVER:
        await send(p.user_id, deceiver_menu_text(g), reply_markup=deceiver_menu_kb(g))
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
    g.doctor_target = g.commissar_target = g.drunk_target = None
    g.acted = set()
    g.announced = set()
    g.night_event = asyncio.Event()

    await send(g.chat_id,
               f"🌙 <b>Ночь {g.day}</b>\n\nГород засыпает, просыпается мафия...\n"
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
    if ROLE_ACTION.get(p.role) != kind:
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
    await safe_edit(cb, f"Ваш выбор: {t.mention}")

    if kind == "kill":
        g.mafia_votes[p.user_id] = tid
        await to_killers(g, f"{p.mention} выбрал(а) {t.mention}", exclude=p.user_id)
    elif kind == "check":
        g.commissar_target = tid
        mafia_like = t.role in MAFIA_TEAM and not (t.role == DON and DON_LOOKS_PEACEFUL)
        verdict = "🔴 <b>МАФИЯ</b>" if mafia_like else "🟢 <b>не мафия</b>"
        await send(p.user_id, f"🕵️ Результат проверки: {t.mention} — {verdict}")
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
    await safe_edit(cb, f"🎭 {FAKE_LABEL[kind]}\nКого выбрать? (это фейк)",
                    targets_kb(g, f"fkt:{chat_id}:{kind}", targets, back=True))


@router.callback_query(F.data.startswith("fkb:"))
async def cb_fake_back(cb: CallbackQuery):
    g, p = night_ctx(cb, int(cb.data.split(":")[1]))
    if not g or p.role != DECEIVER or p.user_id in g.acted:
        await cb.answer("Это действие уже недоступно", show_alert=True)
        return
    await cb.answer()
    await safe_edit(cb, deceiver_menu_text(g), deceiver_menu_kb(g))


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
    await safe_edit(cb, f"🎭 Ты сымитировал: {FAKE_LABEL[kind]}\nЦель: {t.mention}\n"
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
    await safe_edit(cb, "😴 Ты пропустил ход.")
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
    votes = {uid: t for uid, t in g.mafia_votes.items()}
    if not votes:
        return None
    counts = Counter(votes.values())
    top = max(counts.values())
    cands = [t for t, c in counts.items() if c == top]
    if len(cands) == 1:
        return cands[0]
    don = next((p for p in g.alive() if p.role == DON), None)
    if don and votes.get(don.user_id) in cands:
        return votes[don.user_id]
    return random.choice(cands)


async def resolve_night(g: Game):
    target_id = pick_mafia_target(g)
    killed: Optional[Player] = None

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
            killed = t
            t.alive = False
            await send(t.user_id, "💀 Этой ночью тебя убила мафия. Ты выбыл из игры.")

    text = f"☀️ <b>Наступило утро. День {g.day}</b>\n\n"
    if killed:
        text += f"Этой ночью был убит(а) {killed.mention}"
        text += f" — {ROLE_TITLE[killed.role]}.\n" if REVEAL_ROLES else ".\n"
    else:
        text += "Этой ночью никто не погиб. 🙏\n"
    text += f"\n👥 <b>Живые ({len(g.alive())}):</b>\n{alive_list_text(g)}"
    await send(g.chat_id, text)


# ───────────────────────── ДЕНЬ / ГОЛОСОВАНИЕ ─────────────────────────
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
    top = max(counts.values())
    cands = [t for t, c in counts.items() if c == top]
    if len(cands) > 1 or cands[0] == 0:
        await send(g.chat_id, "⚖️ Мнения разделились (или выбрано «никого»). Сегодня никого не казнят.")
        return
    victim = g.players[cands[0]]
    victim.alive = False
    text = f"⚖️ Город решил казнить {victim.mention} ({top} гол.)"
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


# ───────────────────────── ПОБЕДА ─────────────────────────
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


# ───────────────────────── RP-ДЕЙСТВИЯ ─────────────────────────
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


@router.message(Command("actions"))
async def cmd_actions(message: Message):
    await message.answer(ACTIONS_HELP, parse_mode="Markdown")


# Этот обработчик должен стоять ПОСЛЕ всех обработчиков мафии
@router.message(F.text)
async def action_command(message: Message):
    if not message.from_user:
        return
    text = (message.text or "").strip()
    if not text or text.startswith("/"):
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
        if target_user.id == message.from_user.id:
            target_mention = "сам с собой"
        elif target_user.username:
            target_mention = f"@{target_user.username}"
        else:
            target_mention = target_user.full_name

    # 2) @username в тексте
    if not target_mention:
        rest = text[len(matched):].strip()
        if rest.startswith("@"):
            uname = rest.split()[0].lstrip("@")
            target_mention = f"@{uname}"

    # 3) Без указания
    if not target_mention:
        target_mention = "сам с собой"

    result = ACTION_COMMANDS[matched].format(user=target_mention)
    # parse_mode=None: имена людей могут содержать < > &, а у бота по умолчанию HTML
    await message.reply(result, parse_mode=None)


# ───────────────────────── ЗАПУСК ─────────────────────────
async def main():
    global bot, BOT_USERNAME
    if not BOT_TOKEN:
        raise SystemExit("Не задана переменная BOT_TOKEN")
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    me = await bot.get_me()
    BOT_USERNAME = me.username
    log.info("Бот @%s запущен", BOT_USERNAME)
    dp = Dispatcher()
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
