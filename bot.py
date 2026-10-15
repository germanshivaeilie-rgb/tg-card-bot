# -*- coding: utf-8 -*-
"""
🎴 bot_features.py — все новые механики для бота-карточек (aiogram 3.x).

Подключение (см. инструкцию в чате):
    import bot_features as bf
    fx = bf.setup(bot=bot, db=db, get_user=get_user, cards=cards, RARITY_CHANCES=RARITY_CHANCES,
                  find_any_card=find_any_card, card_rarity=card_rarity,
                  get_all_cards_unique=get_all_cards_unique, roll_card=roll_card,
                  send_reveal=send_reveal, make_profile_image=make_profile_image,
                  VIDEO_DIR=VIDEO_DIR, render_sem=render_sem, FONT_PATH=FONT_PATH,
                  DEV_ID=DEV_ID, format_date_ru=format_date_ru, DAILY_TOKENS=DAILY_TOKENS,
                  exclusive_file=BG_PATH)
    dp.include_router(router); dp.include_router(fx); dp.include_router(cr); dp.include_router(rp)
    bf.install(dp)
"""
import asyncio
import hashlib
import html
import io
import json
import logging
import math
import os
import random
import time
from collections import Counter
from datetime import date, datetime, timedelta
from types import SimpleNamespace

from aiogram import BaseMiddleware, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import (BufferedInputFile, CallbackQuery, FSInputFile, InlineKeyboardButton,
                           InlineKeyboardMarkup, Message)

try:
    import game_video as GV
    VIDEO_OK = True
except Exception as _e:  # noqa
    print("game_video отключён:", _e)
    GV = None
    VIDEO_OK = False

log = logging.getLogger("fx")
fx = Router()
D = None
bot = None
db = None

# ═════════════════════════ КОНСТАНТЫ ═════════════════════════
RARITY_ORDER = ["⚪ Обычная", "🔷 Редкая", "🔮 Эпическая", "👑 Легендарная", "♣️ Секретная", "🌌 Бесконечная"]
PTS = {"⚪ Обычная": 1, "🔷 Редкая": 2, "🔮 Эпическая": 3, "👑 Легендарная": 5,
       "♣️ Секретная": 8, "🌌 Бесконечная": 12, "💠 Специальная": 10}
RC = {"⚪": (160, 160, 170), "🔷": (60, 140, 255), "🔮": (170, 80, 255), "👑": (255, 200, 40),
      "♣": (60, 200, 90), "🌌": (0, 220, 230), "💠": (255, 90, 160)}
CRAFT_CHAIN = ["⚪ Обычная", "🔷 Редкая", "🔮 Эпическая", "👑 Легендарная"]
SHARD_VALUE = {"⚪ Обычная": 1, "🔷 Редкая": 5, "🔮 Эпическая": 15, "👑 Легендарная": 50}
ALWAYS = "Всегда рядом"
KING = "Побеждённый король 👑"
EXCL_NAME = "Мастер коллекции 🏆"
SUITS = "♠♥♦♣"
UPGRADE_COST = 10000
SHARPEN_COST = 50000
BANK_MAX = 5_000_000
BET_SECONDS = 20
DUEL_CD = 300

CASES = {
    "c1": ("📦 Обычный кейс", 10000, {"⚪ Обычная": 60, "🔷 Редкая": 28, "🔮 Эпическая": 10, "👑 Легендарная": 2}),
    "c2": ("🎁 Редкий кейс", 50000, {"🔷 Редкая": 50, "🔮 Эпическая": 35, "👑 Легендарная": 13, "♣️ Секретная": 2}),
    "c3": ("💎 Легендарный кейс", 500000, {"🔮 Эпическая": 40, "👑 Легендарная": 45, "♣️ Секретная": 12, "🌌 Бесконечная": 3}),
}
SPIN_COST = 5000
SPIN_W = {"⚪ Обычная": 70, "🔷 Редкая": 20, "🔮 Эпическая": 7, "👑 Легендарная": 2.6, "♣️ Секретная": 0.4}

COS = {  # key: (категория, название, цена, значение)
    "frame_gold": ("frame", "🟡 Золотая рамка", 50000, (255, 215, 0)),
    "frame_neon": ("frame", "🟢 Неоновая рамка", 60000, (57, 255, 20)),
    "frame_blood": ("frame", "🔴 Кровавая рамка", 60000, (220, 20, 40)),
    "title_col": ("title", "Титул «Коллекционер»", 30000, "Коллекционер"),
    "title_maf": ("title", "Титул «Мафиози»", 40000, "Мафиози"),
    "title_pum": ("title", "Титул «Тыква»", 25000, "Тыква"),
    "skin_dark": ("skin", "Скин: тёмный", 40000, (30, 30, 50)),
    "skin_gold": ("skin", "Скин: золотой", 80000, (255, 200, 40)),
    "bg_blue": ("bg", "Фон профиля: синий", 35000, (30, 80, 200)),
    "bg_red": ("bg", "Фон профиля: красный", 35000, (200, 40, 50)),
    "st_fire": ("status", "Статус 🔥", 20000, "🔥"),
    "st_crown": ("status", "Статус 👑", 50000, "👑"),
    "st_skull": ("status", "Статус 💀", 20000, "💀"),
}
CAT_NAMES = {"frame": "Рамка", "title": "Титул", "skin": "Скин карточек", "bg": "Фон профиля", "status": "Статус"}

PERKS = {  # key: (название, макс. уровень, описание)
    "drop": ("🎴 Удача дропа", 5, "+4% шанс бонусной карты за /card на уровень"),
    "speed": ("⏩ Скорость", 5, "−2 мин кулдауна /card на уровень"),
    "market": ("💰 Торговец", 5, "+3% к цене продажи на уровень"),
    "bank": ("🏦 Банкир", 3, "+1% в день по вкладу на уровень"),
}

DAILY_Q = {  # ключ-трекер: (описание, цель, награда)
    "drop": ("Выбей 3 карты", 3, 15000),
    "sell": ("Продай 3 карты", 3, 10000),
    "play": ("Сыграй 5 раз в мини-игры", 5, 20000),
    "duelwin": ("Выиграй дуэль или битву", 1, 25000),
    "daily": ("Забери /daily", 1, 5000),
    "spin": ("Крутани /spin 2 раза", 2, 12000),
    "craft": ("Скрафти карту", 1, 20000),
    "bank": ("Положи монеты в банк", 1, 8000),
    "upgrade": ("Улучши карту (/cardup)", 1, 10000),
}

WHEEL_COLORS = [(90, 90, 110), (60, 60, 60), (120, 70, 160), (170, 30, 50), (230, 120, 20), (240, 190, 30)]

HELP_TEXT = (
    "🆕 <b>НОВЫЕ ФУНКЦИИ</b>\n\n"
    "🎁 <b>Карты:</b> /craft, /cardup название, /fuse название, /shatter название [N], /shards, "
    "/sharpen название, /cardinfo название\n"
    "🏆 /ach — достижения, /collection [редкость] — коллекция\n"
    "💰 <b>Экономика:</b> /auction название цена, /auctions, /bid id сумма, /shop, /cases, "
    "/exchange, /buycard название, /bank, /deposit N, /withdraw\n"
    "🎮 <b>Игры:</b> /duel @user, /battle @user, /spin, /bj ставка, /poker ставка, "
    "/roulette красное|чёрное|зелёное|число ставка\n"
    "🎒 /profile [@user], /cosmetics, /tree, /quests\n"
    "👥 <b>Социальное:</b> /clan, /clan_create, /clan_invite, /clan_leave, /clan_disband, /clan_chat, "
    "/clan_put, /clan_take, /clan_battle, /add, /friends, /unfriend, /gift @user название, "
    "/marry @user, /divorce, /pair, /pair_put, /pair_take\n"
    "🎁 <b>Ежедневное:</b> /daily (стрик), /dcase, /dcard, /seasons, /seasongift\n"
    "📈 /stats, /toplist [cards|coins|duels|rep|xp]"
)


# ═════════════════════════ БАЗА ═════════════════════════
def setup(**deps):
    global D, bot, db
    D = SimpleNamespace(**deps)
    bot, db = D.bot, D.db
    db.executescript("""
    CREATE TABLE IF NOT EXISTS profile_ext (
        user_id INTEGER PRIMARY KEY, xp INTEGER DEFAULT 0, shards INTEGER DEFAULT 0,
        bank INTEGER DEFAULT 0, bank_time TEXT, bank_dep TEXT, streak INTEGER DEFAULT 0,
        last_streak TEXT, last_dcase TEXT, last_dcard TEXT, duel_wins INTEGER DEFAULT 0,
        total_sold INTEGER DEFAULT 0, spouse INTEGER DEFAULT 0, rep INTEGER DEFAULT 0,
        title TEXT, frame TEXT, status TEXT, skin TEXT, bg TEXT, perks TEXT DEFAULT '{}',
        clan_id INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS card_mods (inv_id INTEGER PRIMARY KEY, cname TEXT,
        upg INTEGER DEFAULT 0, merged INTEGER DEFAULT 0, sharp INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS achievements (uid INTEGER, akey TEXT, PRIMARY KEY(uid, akey));
    CREATE TABLE IF NOT EXISTS quest_progress (uid INTEGER, day TEXT, qkey TEXT,
        progress INTEGER DEFAULT 0, claimed INTEGER DEFAULT 0, PRIMARY KEY(uid, day, qkey));
    CREATE TABLE IF NOT EXISTS game_log (uid INTEGER, game TEXT, PRIMARY KEY(uid, game));
    CREATE TABLE IF NOT EXISTS activity (uid INTEGER, day TEXT, PRIMARY KEY(uid, day));
    CREATE TABLE IF NOT EXISTS auctions (id INTEGER PRIMARY KEY AUTOINCREMENT, seller INTEGER,
        card TEXT, upg INTEGER, merged INTEGER, sharp INTEGER, start_price INTEGER,
        bid INTEGER DEFAULT 0, bidder INTEGER DEFAULT 0, ends TEXT, chat_id INTEGER, done INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS shop_sales (slot INTEGER, idx INTEGER, buyer INTEGER, PRIMARY KEY(slot, idx));
    CREATE TABLE IF NOT EXISTS clans (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE,
        owner INTEGER, created TEXT, last_battle TEXT);
    CREATE TABLE IF NOT EXISTS clan_members (user_id INTEGER PRIMARY KEY, clan_id INTEGER);
    CREATE TABLE IF NOT EXISTS stash (owner TEXT, card_name TEXT, upg INTEGER DEFAULT 0,
        merged INTEGER DEFAULT 0, sharp INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS friends (a INTEGER, b INTEGER, PRIMARY KEY(a, b));
    CREATE TABLE IF NOT EXISTS rep_votes (voter INTEGER, target INTEGER, day TEXT, PRIMARY KEY(voter, target, day));
    CREATE TABLE IF NOT EXISTS cosmetics (uid INTEGER, ckey TEXT, PRIMARY KEY(uid, ckey));
    """)
    db.commit()
    for col in ("bank_dep",):
        try:
            db.execute(f"SELECT {col} FROM profile_ext LIMIT 1")
        except Exception:
            db.execute(f"ALTER TABLE profile_ext ADD COLUMN {col} TEXT")
            db.commit()
    if not any(c["name"] == EXCL_NAME for c in D.cards):
        D.cards.append({"name": EXCL_NAME, "rarity": "💠 Специальная", "price": 2000000,
                        "file": D.exclusive_file})
    return fx


def install(dp):
    mw = FxMW()
    dp.message.outer_middleware(mw)
    dp.callback_query.outer_middleware(mw)


def background_tasks():
    return [bg_loop()]


# ═════════════════════════ ХЕЛПЕРЫ ═════════════════════════
def esc(s):
    return html.escape(str(s))


def fmt(n):
    return f"{int(n):,}".replace(",", " ")


def today():
    return date.today().isoformat()


def KB(*rows):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t, callback_data=d) for t, d in r]
                                                 for r in rows])


def ensure(m):
    u = m.from_user
    D.get_user(u.id, u.username)
    ext(u.id)
    return u.id


def ext(uid):
    db.execute("INSERT OR IGNORE INTO profile_ext(user_id) VALUES(?)", (uid,))
    c = db.execute("SELECT * FROM profile_ext WHERE user_id=?", (uid,))
    row = c.fetchone()
    return dict(zip([x[0] for x in c.description], row))


def ext_set(uid, **kw):
    ext(uid)
    db.execute(f"UPDATE profile_ext SET {', '.join(k + '=?' for k in kw)} WHERE user_id=?", (*kw.values(), uid))
    db.commit()


def ext_add(uid, col, n):
    ext(uid)
    db.execute(f"UPDATE profile_ext SET {col}={col}+? WHERE user_id=?", (n, uid))
    db.commit()


def perk(uid, key):
    try:
        return int(json.loads(ext(uid)["perks"] or "{}").get(key, 0))
    except Exception:
        return 0


def bal(uid):
    return D.get_user(uid)[0]


def tok(uid):
    return D.get_user(uid)[6]


def add_coins(uid, n):
    db.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (int(n), uid))
    db.commit()


def spend(uid, n):
    if n <= 0 or bal(uid) < n:
        return False
    add_coins(uid, -n)
    return True


def nm(uid):
    r = db.execute("SELECT username FROM users WHERE user_id=?", (uid,)).fetchone()
    return f"@{r[0]}" if r and r[0] else f"ID{uid}"


def find_user(token):
    token = token.strip().lstrip("@")
    if token.isdigit():
        return db.execute("SELECT user_id, username FROM users WHERE user_id=?", (int(token),)).fetchone()
    return db.execute("SELECT user_id, username FROM users WHERE LOWER(username)=LOWER(?)", (token,)).fetchone()


def get_target(m, args):
    """→ (target_id | None, остаток_аргументов)"""
    args = (args or "").strip()
    rm = m.reply_to_message
    if rm and rm.from_user and not rm.from_user.is_bot:
        u = rm.from_user
        D.get_user(u.id, u.username)
        return u.id, args
    parts = args.split(maxsplit=1)
    if parts and (parts[0].startswith("@") or parts[0].isdigit()):
        r = find_user(parts[0])
        return (r[0] if r else None), (parts[1] if len(parts) > 1 else "")
    return None, args


async def say(chat_id, text, kb=None):
    try:
        return await bot.send_message(chat_id, text, reply_markup=kb)
    except Exception as e:
        log.debug("say fail %s", e)


async def edit(call, text, kb=None):
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        pass


def rarity_color(r):
    return RC.get((r or "?")[:1], (130, 130, 170))


# ── карты и инвентарь
def rar(name):
    return D.card_rarity(name)


def base_price(name):
    c = D.find_any_card(name)
    return c["price"] if c else 0


def pts(name):
    r = rar(name)
    if r in PTS:
        return PTS[r]
    return max(1, int(math.log10(max(base_price(name), 10)) * 1.5))


def inv_rows(uid):
    return db.execute("SELECT rowid, card_name FROM inventory WHERE user_id=?", (uid,)).fetchall()


def inv_count(uid):
    return db.execute("SELECT COUNT(*) FROM inventory WHERE user_id=?", (uid,)).fetchone()[0]


def mods_of(rid, name):
    r = db.execute("SELECT cname, upg, merged, sharp FROM card_mods WHERE inv_id=?", (rid,)).fetchone()
    if r and r[0] == name:
        return {"upg": r[1], "merged": r[2], "sharp": r[3]}
    return {"upg": 0, "merged": 0, "sharp": 0}


def mods_set(rid, name, mods):
    db.execute("DELETE FROM card_mods WHERE inv_id=?", (rid,))
    if mods["upg"] or mods["merged"] or mods["sharp"]:
        db.execute("INSERT INTO card_mods VALUES(?,?,?,?,?)", (rid, name, mods["upg"], mods["merged"], mods["sharp"]))
    db.commit()


def is_plain(rid, name):
    m = mods_of(rid, name)
    return not (m["upg"] or m["merged"] or m["sharp"])


def mod_price(base, m, uid=None):
    p = base * min(1 + 0.1 * m["upg"], 5.0) * (3 if m["merged"] else 1) * (1.1 if m["sharp"] else 1)
    if uid:
        p *= 1 + 0.03 * perk(uid, "market")
    return int(p)


def copies(uid, name):
    base = base_price(name)
    out = []
    for rid, n in inv_rows(uid):
        if n == name:
            m = mods_of(rid, name)
            out.append({"id": rid, "mods": m, "price": mod_price(base, m, uid)})
    return out


def add_card(uid, name, mods=None):
    rid = db.execute("INSERT INTO inventory(user_id, card_name) VALUES(?,?)", (uid, name)).lastrowid
    mods_set(rid, name, mods or {"upg": 0, "merged": 0, "sharp": 0})
    return rid


def del_card(rid):
    db.execute("DELETE FROM inventory WHERE rowid=?", (rid,))
    db.execute("DELETE FROM card_mods WHERE inv_id=?", (rid,))
    db.commit()


def resolve_owned(uid, text):
    text = (text or "").strip().lower()
    if not text:
        return None
    names = sorted({n for _, n in inv_rows(uid)})
    for n in names:
        if n.lower() == text:
            return n
    part = [n for n in names if text in n.lower()]
    return part[0] if len(part) == 1 else None


def roll_rarity_card(weights):
    r = random.choices(list(weights), weights=list(weights.values()))[0]
    pool = [c for c in D.cards if c["rarity"] == r and c["name"] != EXCL_NAME]
    return (random.choice(pool) if pool else D.roll_card()), r


async def reveal(message, card, caption, kb=None):
    ok = False
    try:
        ok = await D.send_reveal(message, card, card.get("rarity") or rar(card["name"]), caption,
                                 reply_markup=kb, parse_mode="HTML")
    except Exception as e:
        log.debug("reveal: %s", e)
    if not ok:
        try:
            await message.answer_photo(FSInputFile(card["file"]), caption=caption, reply_markup=kb)
        except Exception:
            await message.answer(caption, reply_markup=kb)


# ═════════════════════════ ВИДЕО ДЛЯ МИНИ-ИГР ═════════════════════════
_vid_ids = {}


async def send_game_video(message, key, render_fn, args, caption=""):
    """render_fn(*args, path, font_path). Возвращает отправленное сообщение или None."""
    if not VIDEO_OK:
        return None
    path = os.path.join(D.VIDEO_DIR, "g_" + hashlib.md5(key.encode()).hexdigest() + ".mp4")
    made = False
    try:
        media = _vid_ids.get(key)
        if media is None:
            async with D.render_sem:
                await asyncio.to_thread(render_fn, *args, path, D.FONT_PATH)
            media = FSInputFile(path)
            made = True
        sent = await message.answer_animation(media, caption=caption, width=GV.GAME_W, height=GV.GAME_H)
        fid = sent.animation.file_id if sent.animation else (sent.video.file_id if sent.video else None)
        if fid:
            _vid_ids[key] = fid
        return sent
    except Exception as e:
        print("Ошибка видео мини-игры:", e)
        return None
    finally:
        if made and os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass


async def play(message, key, fn, args, secs, head, result_text, kb=None):
    """Видео → через secs сек. подпись заменяется итогом. Без видео — просто итог."""
    sent = await send_game_video(message, key, fn, args, head)
    if sent:
        await asyncio.sleep(secs + 0.3)
        try:
            await sent.edit_caption(caption=result_text, reply_markup=kb)
            return
        except Exception:
            pass
    await message.answer(result_text, reply_markup=kb)


# обёртки для старых игр в основном файле (coin / wheel / miner)
async def video_coin(message, result, caption):
    return await send_game_video(message, f"coin_{result}", GV.render_coin_video, (result,), caption) if VIDEO_OK else None


async def video_wheel(message, names, idx, caption):
    segs = [(n, WHEEL_COLORS[i % len(WHEEL_COLORS)]) for i, n in enumerate(names)]
    key = "wheel_" + "_".join(names) + f"_{idx}"
    return await send_game_video(message, key, GV.render_wheel_video, (segs, idx), caption) if VIDEO_OK else None


async def video_miner(message, kind, text, caption):
    return await send_game_video(message, f"miner_{kind}_{text}", GV.render_miner_video, (kind, text), caption) if VIDEO_OK else None


# ═════════════════════════ ОПЫТ / КВЕСТЫ / ДОСТИЖЕНИЯ ═════════════════════════
def xp_level(xp):
    return int(math.sqrt(max(xp, 0) / 100)) + 1


def add_xp(uid, n):
    old = xp_level(ext(uid)["xp"])
    ext_add(uid, "xp", n)
    new = xp_level(ext(uid)["xp"])
    return new if new > old else 0


def quests_for(uid, day):
    return random.Random(f"{uid}{day}").sample(list(DAILY_Q), 3)


def track(uid, key, n=1):
    msgs = []
    day = today()
    if key not in quests_for(uid, day):
        return msgs
    desc, target, reward = DAILY_Q[key]
    row = db.execute("SELECT progress, claimed FROM quest_progress WHERE uid=? AND day=? AND qkey=?",
                     (uid, day, key)).fetchone()
    prog, claimed = (row if row else (0, 0))
    if claimed:
        return msgs
    prog += n
    if prog >= target:
        db.execute("INSERT OR REPLACE INTO quest_progress VALUES(?,?,?,?,1)", (uid, day, key, target))
        add_coins(uid, reward)
        msgs.append(f"📜 Квест выполнен: «{desc}» — +{fmt(reward)} монет!")
    else:
        db.execute("INSERT OR REPLACE INTO quest_progress VALUES(?,?,?,?,0)", (uid, day, key, prog))
    db.commit()
    return msgs


async def tr(chat_id, uid, key, n=1):
    for t in track(uid, key, n):
        await say(chat_id, t)


def mark_play(uid, game):
    db.execute("INSERT OR IGNORE INTO game_log VALUES(?,?)", (uid, game))
    db.commit()
    add_xp(uid, 3)
    return track(uid, "play")


def ach_state(uid):
    names = {n for _, n in inv_rows(uid)}
    allc = [c["name"] for c in D.get_all_cards_unique() if c["name"] != EXCL_NAME]
    e = ext(uid)
    return {
        "cards": inv_count(uid), "uniq": len(names & set(allc)), "total": len(allc),
        "rars": {rar(n) for n in names}, "sold": e["total_sold"], "bal": bal(uid),
        "duel": e["duel_wins"], "games": db.execute("SELECT COUNT(*) FROM game_log WHERE uid=?", (uid,)).fetchone()[0],
        "married": bool(e["spouse"]), "clan": bool(e["clan_id"]), "bank": e["bank"] > 0,
    }


ACH = [  # key, группа, название, награда, условие
    ("c1", "Карты", "Первая карта", 5000, lambda s: s["cards"] >= 1),
    ("c10", "Карты", "10 карт", 10000, lambda s: s["cards"] >= 10),
    ("c50", "Карты", "50 карт", 50000, lambda s: s["cards"] >= 50),
    ("c100", "Карты", "100 карт", 200000, lambda s: s["cards"] >= 100),
    ("r_leg", "Редкости", "Первая легендарка", 30000, lambda s: "👑 Легендарная" in s["rars"]),
    ("r_inf", "Редкости", "Первая бесконечная", 100000, lambda s: "🌌 Бесконечная" in s["rars"]),
    ("r_sec", "Редкости", "Первая секретная", 50000, lambda s: "♣️ Секретная" in s["rars"]),
    ("s100k", "Экономика", "Продал на 100к", 5000, lambda s: s["sold"] >= 100_000),
    ("s1m", "Экономика", "Продал на 1 млн", 50000, lambda s: s["sold"] >= 1_000_000),
    ("s10m", "Экономика", "Продал на 10 млн", 500000, lambda s: s["sold"] >= 10_000_000),
    ("b1m", "Экономика", "Баланс 1 млн", 100000, lambda s: s["bal"] >= 1_000_000),
    ("d10", "Дуэли", "10 побед", 10000, lambda s: s["duel"] >= 10),
    ("d50", "Дуэли", "50 побед", 50000, lambda s: s["duel"] >= 50),
    ("d100", "Дуэли", "100 побед", 200000, lambda s: s["duel"] >= 100),
    ("k5", "Коллекция", "Собрал 5 разных", 10000, lambda s: s["uniq"] >= 5),
    ("k15", "Коллекция", "Собрал 15 разных", 100000, lambda s: s["uniq"] >= 15),
    ("kall", "Коллекция", "Собрал ВСЕ (+эксклюзивная карта)", 1_000_000, lambda s: s["uniq"] >= s["total"] > 0),
    ("q_rar", "Квесты", "Владей 4 разными редкостями", 40000, lambda s: len(s["rars"]) >= 4),
    ("q_games", "Квесты", "Сыграй в 5 разных игр", 50000, lambda s: s["games"] >= 5),
    ("q_bank", "Квесты", "Открой вклад в банке", 15000, lambda s: s["bank"]),
    ("q_love", "Квесты", "Сыграй свадьбу", 30000, lambda s: s["married"]),
    ("q_clan", "Квесты", "Вступи в клан", 20000, lambda s: s["clan"]),
]


def check_ach(uid):
    s = ach_state(uid)
    done = {r[0] for r in db.execute("SELECT akey FROM achievements WHERE uid=?", (uid,)).fetchall()}
    msgs = []
    for key, grp, title, reward, cond in ACH:
        if key in done or not cond(s):
            continue
        db.execute("INSERT OR IGNORE INTO achievements VALUES(?,?)", (uid, key))
        add_coins(uid, reward)
        text = f"🏆 Достижение: «{title}» — +{fmt(reward)} монет!"
        if key == "kall":
            add_card(uid, EXCL_NAME)
            text += f"\n🎴 Эксклюзивная карта: {EXCL_NAME}"
        msgs.append(text)
    db.commit()
    return msgs


# ═════════════════════════ MIDDLEWARE ═════════════════════════
class FxMW(BaseMiddleware):
    async def __call__(self, handler, event, data):
        u = getattr(event, "from_user", None)
        text = getattr(event, "text", None)
        is_cb = isinstance(event, CallbackQuery)
        if not u or u.is_bot or not (is_cb or (text and (text.startswith("/") or text.isdigit()))):
            return await handler(event, data)
        chat = event.message.chat.id if is_cb and event.message else getattr(getattr(event, "chat", None), "id", u.id)
        before = inv_count(u.id)
        cmd = text.split()[0].split("@")[0].lower() if text and text.startswith("/") else None
        res = await handler(event, data)
        try:
            await post_hook(u, chat, before, cmd)
        except Exception:
            log.exception("post_hook")
        return res


async def post_hook(u, chat, before, cmd):
    uid = u.id
    D.get_user(uid, u.username)
    db.execute("INSERT OR IGNORE INTO activity VALUES(?,?)", (uid, today()))
    db.commit()
    msgs = []
    delta = inv_count(uid) - before
    if delta > 0:
        msgs += track(uid, "drop", delta)
        lv = add_xp(uid, 5 * delta)
        if lv:
            msgs.append(f"🆙 Новый уровень опыта: {lv}! (+1 очко в /tree)")
        if cmd == "/card":
            p = perk(uid, "drop")
            if p and random.random() < 0.04 * p:
                c = D.roll_card()
                add_card(uid, c["name"])
                msgs.append(f"🌳 Дерево прокачки: бонусная карта — {esc(c['name'])} ({c['rarity']})!")
            sp = perk(uid, "speed")
            if sp and uid != D.DEV_ID:
                r = db.execute("SELECT last_card FROM users WHERE user_id=?", (uid,)).fetchone()
                if r and r[0]:
                    new = (datetime.fromisoformat(r[0]) - timedelta(minutes=2 * sp)).isoformat()
                    db.execute("UPDATE users SET last_card=? WHERE user_id=?", (new, uid))
                    db.commit()
    msgs += check_ach(uid)
    for t in msgs:
        await say(chat, t)


# ═════════════════════════ КРАФТ / АПГРЕЙД / СЛИЯНИЕ / РАЗБОР / ЗАТОЧКА ═════════════════════════
def plain_of_rarity(uid, r):
    out = [(rid, n) for rid, n in inv_rows(uid) if n != ALWAYS and rar(n) == r and is_plain(rid, n)]
    return sorted(out, key=lambda x: base_price(x[1]))


@fx.message(Command("craft"))
async def cmd_craft(m: Message):
    uid = ensure(m)
    lines = ["🛠 <b>Крафт</b>\n5 карт одной редкости → 1 карта следующей\n(карты с улучшениями не берутся)\n"]
    rows = []
    for i, r in enumerate(CRAFT_CHAIN[:3]):
        have = len(plain_of_rarity(uid, r))
        lines.append(f"{r}: {have}/5 → {CRAFT_CHAIN[i + 1]}")
        rows.append([(f"{r} ×5 → {CRAFT_CHAIN[i + 1]}", f"fx_craft:{uid}:{i}")])
    await m.answer("\n".join(lines), reply_markup=KB(*rows))


@fx.callback_query(F.data.startswith("fx_craft:"))
async def cb_craft(call: CallbackQuery):
    _, u, i = call.data.split(":")
    uid, i = int(u), int(i)
    if call.from_user.id != uid:
        return await call.answer("Не твоё меню!", show_alert=True)
    have = plain_of_rarity(uid, CRAFT_CHAIN[i])
    if len(have) < 5:
        return await call.answer(f"Нужно 5, у тебя {len(have)}", show_alert=True)
    for rid, _n in have[:5]:
        del_card(rid)
    nxt = CRAFT_CHAIN[i + 1]
    pool = [c for c in D.cards if c["rarity"] == nxt and c["name"] != EXCL_NAME]
    card = random.choice(pool)
    add_card(uid, card["name"])
    await call.answer("🛠 Крафт!")
    await tr(call.message.chat.id, uid, "craft")
    await reveal(call.message, card, f"🛠 <b>Крафт удался!</b>\n🎴 {esc(card['name'])}\n{nxt} | 💰 {fmt(card['price'])}")


@fx.message(Command("cardup"))
async def cmd_cardup(m: Message, command: CommandObject):
    uid = ensure(m)
    name = resolve_owned(uid, command.args)
    if not name:
        return await m.answer("Использование: /cardup название_карты\n💰 10 000 монет = +10% к цене (максимум ×5).")
    best = max(copies(uid, name), key=lambda c: c["price"])
    if best["mods"]["upg"] >= 40:
        return await m.answer("⛔ Достигнут максимум ×5.")
    if not spend(uid, UPGRADE_COST):
        return await m.answer(f"❌ Нужно {fmt(UPGRADE_COST)} монет.")
    best["mods"]["upg"] += 1
    mods_set(best["id"], name, best["mods"])
    await tr(m.chat.id, uid, "upgrade")
    await m.answer(f"⬆️ {esc(name)}: уровень улучшения {best['mods']['upg']}/40\n"
                   f"💰 Новая цена: {fmt(mod_price(base_price(name), best['mods'], uid))}")


@fx.message(Command("fuse"))
async def cmd_fuse(m: Message, command: CommandObject):
    uid = ensure(m)
    name = resolve_owned(uid, command.args)
    if not name:
        return await m.answer("Использование: /fuse название\n2 одинаковые карты (без улучшений) → 1 усиленная ×3.")
    plain = [c for c in copies(uid, name) if not (c["mods"]["upg"] or c["mods"]["merged"] or c["mods"]["sharp"])]
    if len(plain) < 2:
        return await m.answer("❌ Нужно 2 одинаковые карты без улучшений.")
    del_card(plain[0]["id"])
    mods_set(plain[1]["id"], name, {"upg": 0, "merged": 1, "sharp": 0})
    await m.answer(f"🔗 Слияние! {esc(name)} теперь усиленная — цена ×3 ({fmt(base_price(name) * 3)}).")


@fx.message(Command("shatter"))
async def cmd_shatter(m: Message, command: CommandObject):
    uid = ensure(m)
    parts = (command.args or "").rsplit(maxsplit=1)
    n = 1
    text = command.args or ""
    if len(parts) == 2 and parts[1].isdigit():
        text, n = parts[0], max(1, int(parts[1]))
    name = resolve_owned(uid, text)
    if not name or name == ALWAYS:
        return await m.answer("Использование: /shatter название [кол-во]\n⚪1 🔷5 🔮15 👑50 осколков (прочие 100).")
    plain = [c for c in copies(uid, name) if not (c["mods"]["upg"] or c["mods"]["merged"] or c["mods"]["sharp"])]
    if not plain:
        return await m.answer("❌ Нет карт без улучшений.")
    n = min(n, len(plain))
    for c in plain[:n]:
        del_card(c["id"])
    gain = SHARD_VALUE.get(rar(name), 100) * n
    ext_add(uid, "shards", gain)
    await m.answer(f"💎 Разбито: {esc(name)} ×{n}\n+{gain} осколков (всего {ext(uid)['shards']}). /shards")


@fx.message(Command("shards"))
async def cmd_shards(m: Message):
    uid = ensure(m)
    s = ext(uid)["shards"]
    await m.answer(f"💎 Осколков: {s}\n10 осколков → 1 случайная 🔷 Редкая карта",
                   reply_markup=KB([("🔷 Собрать карту (10)", f"fx_shard:{uid}")]))


@fx.callback_query(F.data.startswith("fx_shard:"))
async def cb_shard(call: CallbackQuery):
    uid = int(call.data.split(":")[1])
    if call.from_user.id != uid:
        return await call.answer("Не твоё!", show_alert=True)
    if ext(uid)["shards"] < 10:
        return await call.answer("Нужно 10 осколков", show_alert=True)
    ext_add(uid, "shards", -10)
    card = random.choice([c for c in D.cards if c["rarity"] == "🔷 Редкая"])
    add_card(uid, card["name"])
    await call.answer("Собрано!")
    await reveal(call.message, card, f"💎 Из осколков собрана карта!\n🎴 {esc(card['name'])}\n{card['rarity']}")


@fx.message(Command("sharpen"))
async def cmd_sharpen(m: Message, command: CommandObject):
    uid = ensure(m)
    name = resolve_owned(uid, command.args)
    if not name:
        return await m.answer(f"Использование: /sharpen название\n💰 {fmt(SHARPEN_COST)} монет = +10% к цене продажи (1 раз на карту).")
    cand = [c for c in copies(uid, name) if not c["mods"]["sharp"]]
    if not cand:
        return await m.answer("⛔ Все копии уже заточены.")
    best = max(cand, key=lambda c: c["price"])
    if not spend(uid, SHARPEN_COST):
        return await m.answer(f"❌ Нужно {fmt(SHARPEN_COST)} монет.")
    best["mods"]["sharp"] = 1
    mods_set(best["id"], name, best["mods"])
    await m.answer(f"🔪 {esc(name)} заточена! Новая цена: {fmt(mod_price(base_price(name), best['mods'], uid))}")


def skin_border(path, color):
    from PIL import Image, ImageOps
    im = Image.open(path).convert("RGB")
    im = ImageOps.expand(im, border=max(12, im.width // 40), fill=tuple(color))
    out = io.BytesIO()
    im.save(out, "PNG")
    out.seek(0)
    return out


@fx.message(Command("cardinfo"))
async def cmd_cardinfo(m: Message, command: CommandObject):
    uid = ensure(m)
    name = resolve_owned(uid, command.args)
    if not name:
        return await m.answer("Использование: /cardinfo название")
    cs = sorted(copies(uid, name), key=lambda c: -c["price"])
    lines = [f"🎴 <b>{esc(name)}</b>\n{rar(name)} | базовая цена {fmt(base_price(name))}\n"]
    for c in cs:
        mm = c["mods"]
        tags = [f"⬆️{mm['upg']}" if mm["upg"] else "", "🔗×3" if mm["merged"] else "", "🔪" if mm["sharp"] else ""]
        lines.append(f"• {fmt(c['price'])} монет {' '.join(t for t in tags if t)}")
    cap = "\n".join(lines)
    card = D.find_any_card(name)
    skin = ext(uid)["skin"]
    try:
        if skin and skin in COS:
            await m.answer_photo(BufferedInputFile(skin_border(card["file"], COS[skin][3]).read(), "c.png"), caption=cap)
        else:
            await m.answer_photo(FSInputFile(card["file"]), caption=cap)
    except Exception:
        await m.answer(cap)


# ═════════════════════════ ПРОДАЖА (с учётом улучшений) ═════════════════════════
@fx.message(Command("sell"))
async def cmd_sell(m: Message, command: CommandObject):
    uid = ensure(m)
    name = resolve_owned(uid, command.args)
    if not name:
        return await m.answer("Использование: /sell Название")
    if name == ALWAYS:
        return await m.answer("❌ «Всегда рядом» нельзя продать. Только трейд.")
    cheapest = min(copies(uid, name), key=lambda c: c["price"])
    del_card(cheapest["id"])
    if name == KING:
        db.execute("UPDATE users SET tokens=tokens+1000 WHERE user_id=?", (uid,))
        db.commit()
        return await m.answer(f"✅ Продано: {esc(name)} за 1000 ☢️")
    p = cheapest["price"]
    add_coins(uid, p)
    ext_add(uid, "total_sold", p)
    add_xp(uid, 2)
    await tr(m.chat.id, uid, "sell")
    await m.answer(f"✅ Продано: {esc(name)} за {fmt(p)} монет")


def sellall_calc(uid):
    money = tokens_ = 0
    lines = []
    for rid, n in inv_rows(uid):
        if n == ALWAYS:
            continue
        if n == KING:
            tokens_ += 1000
            continue
        p = mod_price(base_price(n), mods_of(rid, n), uid)
        money += p
    return money, tokens_


@fx.message(Command("sellall"))
async def cmd_sellall(m: Message):
    uid = ensure(m)
    money, t = sellall_calc(uid)
    if not money and not t:
        return await m.answer("❌ Нечего продавать.")
    txt = f"💰 Будет продано всё (кроме «{ALWAYS}»):\n💵 {fmt(money)} монет" + (f"\n☢️ {t} токенов" if t else "")
    await m.answer(txt, reply_markup=KB([("✅ Да", f"fx_sa:{uid}:1"), ("❌ Нет", f"fx_sa:{uid}:0")]))


@fx.callback_query(F.data.startswith("fx_sa:"))
async def cb_sellall(call: CallbackQuery):
    _, u, yes = call.data.split(":")
    uid = int(u)
    if call.from_user.id != uid:
        return await call.answer("Не твоё!", show_alert=True)
    if yes == "0":
        await edit(call, "❌ Отменено.")
        return await call.answer()
    money, t = sellall_calc(uid)
    cnt = 0
    for rid, n in inv_rows(uid):
        if n != ALWAYS:
            del_card(rid)
            cnt += 1
    db.execute("UPDATE users SET balance=balance+?, tokens=tokens+? WHERE user_id=?", (money, t, uid))
    db.commit()
    ext_add(uid, "total_sold", money)
    add_xp(uid, cnt)
    await edit(call, f"✅ Продано {cnt} карт!\n💰 +{fmt(money)} монет" + (f"\n☢️ +{t}" if t else ""))
    await call.answer("Готово!")
    await tr(call.message.chat.id, uid, "sell", cnt)


# ═════════════════════════ ДОСТИЖЕНИЯ / КОЛЛЕКЦИЯ ═════════════════════════
@fx.message(Command("ach"))
async def cmd_ach(m: Message):
    uid = ensure(m)
    for t in check_ach(uid):
        await m.answer(t)
    done = {r[0] for r in db.execute("SELECT akey FROM achievements WHERE uid=?", (uid,)).fetchall()}
    lines, grp = [f"🏆 <b>Достижения</b> ({len(done)}/{len(ACH)})"], None
    for key, g, title, reward, _c in ACH:
        if g != grp:
            grp = g
            lines.append(f"\n<b>{g}:</b>")
        lines.append(f"{'✅' if key in done else '⬜'} {title} — {fmt(reward)}")
    await m.answer("\n".join(lines))


@fx.message(Command("collection"))
async def cmd_collection(m: Message, command: CommandObject):
    uid = ensure(m)
    flt = (command.args or "").strip().lower()
    owned = {n for _, n in inv_rows(uid)}
    allc = [c for c in D.get_all_cards_unique() if c["name"] != EXCL_NAME]
    done = len([c for c in allc if c["name"] in owned])
    pct = int(done / len(allc) * 100) if allc else 0
    groups = {}
    for c in allc:
        groups.setdefault(rar(c["name"]), []).append(c["name"])
    out = [f"📦 <b>Коллекция:</b> {done}/{len(allc)} ({pct}%)\n🎁 За 100% — 1 000 000 монет + эксклюзивная карта\n"]
    for r, names in groups.items():
        if flt and flt not in r.lower():
            continue
        have = sum(1 for n in names if n in owned)
        out.append(f"\n<b>{r}</b> {have}/{len(names)}")
        out += [f"{'✅' if n in owned else '❌'} {esc(n)}" for n in names]
    text = "\n".join(out)
    for i in range(0, len(text), 3800):
        await m.answer(text[i:i + 3800])


# ═════════════════════════ БАНК ═════════════════════════
def bank_accrue(uid):
    e = ext(uid)
    if not e["bank"] or not e["bank_time"]:
        return e["bank"]
    days = int((datetime.now() - datetime.fromisoformat(e["bank_time"])).total_seconds() // 86400)
    if days <= 0:
        return e["bank"]
    rate = 0.05 + 0.01 * perk(uid, "bank")
    new = int(e["bank"] * (1 + rate) ** min(days, 7))
    new = min(new, BANK_MAX * 3)
    ext_set(uid, bank=new, bank_time=(datetime.now() if days > 7 else
                                      datetime.fromisoformat(e["bank_time"]) + timedelta(days=days)).isoformat())
    return new


@fx.message(Command("bank"))
async def cmd_bank(m: Message):
    uid = ensure(m)
    b = bank_accrue(uid)
    e = ext(uid)
    left = ""
    if e["bank_dep"]:
        rem = timedelta(hours=24) - (datetime.now() - datetime.fromisoformat(e["bank_dep"]))
        left = f"\n🔒 Снять можно через: {max(0, int(rem.total_seconds() // 3600))} ч" if rem.total_seconds() > 0 else "\n🔓 Можно снимать"
    await m.answer(f"🏦 <b>Банк</b>\n📈 {5 + perk(uid, 'bank')}% в день (максимум 7 дней начисления)\n"
                   f"💰 Вклад: {fmt(b)} (лимит {fmt(BANK_MAX)})\n💳 На руках: {fmt(bal(uid))}{left}\n\n"
                   f"/deposit сумма — положить\n/withdraw — снять (через 24 ч после вклада)")


@fx.message(Command("deposit"))
async def cmd_deposit(m: Message, command: CommandObject):
    uid = ensure(m)
    try:
        n = int((command.args or "").replace(" ", ""))
    except ValueError:
        return await m.answer("Использование: /deposit сумма")
    cur_b = bank_accrue(uid)
    if n <= 0 or cur_b + n > BANK_MAX:
        return await m.answer(f"❌ Сумма должна быть больше 0, лимит вклада {fmt(BANK_MAX)}.")
    if not spend(uid, n):
        return await m.answer("❌ Не хватает монет.")
    now = datetime.now().isoformat()
    ext_set(uid, bank=cur_b + n, bank_time=ext(uid)["bank_time"] if cur_b else now, bank_dep=now)
    await tr(m.chat.id, uid, "bank")
    await m.answer(f"🏦 Вклад: {fmt(cur_b + n)} монет. Снять можно через 24 часа.")


@fx.message(Command("withdraw"))
async def cmd_withdraw(m: Message):
    uid = ensure(m)
    b = bank_accrue(uid)
    e = ext(uid)
    if not b:
        return await m.answer("Вклад пуст.")
    if e["bank_dep"] and datetime.now() - datetime.fromisoformat(e["bank_dep"]) < timedelta(hours=24):
        return await m.answer("🔒 Снять можно через 24 часа после последнего вклада.")
    add_coins(uid, b)
    ext_set(uid, bank=0, bank_time=None, bank_dep=None)
    await m.answer(f"✅ Снято {fmt(b)} монет.")


# ═════════════════════════ КЕЙСЫ / МАГАЗИН / ОБМЕННИК ═════════════════════════
@fx.message(Command("cases"))
async def cmd_cases(m: Message):
    uid = ensure(m)
    lines, rows = ["🎁 <b>Кейсы за монеты</b>\n"], []
    for k, (title, price, w) in CASES.items():
        tot = sum(w.values())
        lines.append(f"{title} — {fmt(price)}\n   " + ", ".join(f"{r.split()[0]}{round(v / tot * 100)}%" for r, v in w.items()))
        rows.append([(f"{title} — {fmt(price)}", f"fx_case:{uid}:{k}")])
    await m.answer("\n".join(lines), reply_markup=KB(*rows))


@fx.callback_query(F.data.startswith("fx_case:"))
async def cb_case(call: CallbackQuery):
    _, u, k = call.data.split(":")
    uid = int(u)
    if call.from_user.id != uid:
        return await call.answer("Не твоё меню!", show_alert=True)
    title, price, w = CASES[k]
    if not spend(uid, price):
        return await call.answer(f"❌ Нужно {fmt(price)} монет", show_alert=True)
    card, r = roll_rarity_card(w)
    add_card(uid, card["name"])
    add_xp(uid, 4)
    await call.answer("Открываем...")
    kb = KB([("🔁 Ещё раз", f"fx_case:{uid}:{k}")])
    await reveal(call.message, card, f"{title}\n🎴 <b>{esc(card['name'])}</b>\n{r} | 💰 {fmt(card['price'])}", kb)


def shop_offers(slot):
    pool = sorted([c for c in D.cards if c["rarity"] in D.RARITY_CHANCES], key=lambda c: c["name"])
    rnd = random.Random(slot)
    return rnd.sample(pool, min(len(pool), rnd.randint(3, 5)))


@fx.message(Command("shop"))
async def cmd_shop(m: Message):
    uid = ensure(m)
    await m.answer(*shop_view(uid))


def shop_view(uid):
    slot = int(time.time() // 1800)
    left = 1800 - int(time.time() % 1800)
    db.execute("DELETE FROM shop_sales WHERE slot < ?", (slot - 3,))
    lines, rows = [f"🛒 <b>Магазин</b> (обновится через {left // 60} мин)\nЦены выше рыночных ×1.6\n"], []
    for i, c in enumerate(shop_offers(slot)):
        sold = db.execute("SELECT 1 FROM shop_sales WHERE slot=? AND idx=?", (slot, i)).fetchone()
        price = int(c["price"] * 1.6)
        lines.append(f"{'❌' if sold else '🎴'} {esc(c['name'])} — {c['rarity']} — {fmt(price)}")
        if not sold:
            rows.append([(f"Купить: {c['name']} ({fmt(price)})", f"fx_shop:{slot}:{i}")])
    return "\n".join(lines), KB(*rows) if rows else None


@fx.callback_query(F.data.startswith("fx_shop:"))
async def cb_shop(call: CallbackQuery):
    _, s, i = call.data.split(":")
    slot, i = int(s), int(i)
    uid = call.from_user.id
    D.get_user(uid, call.from_user.username)
    if slot != int(time.time() // 1800):
        return await call.answer("Ассортимент обновился!", show_alert=True)
    c = shop_offers(slot)[i]
    if db.execute("SELECT 1 FROM shop_sales WHERE slot=? AND idx=?", (slot, i)).fetchone():
        return await call.answer("Уже раскуплено!", show_alert=True)
    price = int(c["price"] * 1.6)
    if not spend(uid, price):
        return await call.answer(f"Нужно {fmt(price)} монет", show_alert=True)
    db.execute("INSERT INTO shop_sales VALUES(?,?,?)", (slot, i, uid))
    db.commit()
    add_card(uid, c["name"])
    await call.answer(f"Куплено: {c['name']}")
    text, kb = shop_view(uid)
    await edit(call, text, kb)


@fx.message(Command("exchange"))
async def cmd_exchange(m: Message):
    await m.answer("💱 <b>Обменник</b>\n\n• Карты → монеты: /sell название, /sellall\n"
                   "• Монеты → карты (×3 к цене): /buycard название\n"
                   "• Карты → осколки: /shatter, потом /shards")


@fx.message(Command("buycard"))
async def cmd_buycard(m: Message, command: CommandObject):
    uid = ensure(m)
    t = (command.args or "").strip().lower()
    pool = [c for c in D.cards if c["rarity"] in D.RARITY_CHANCES and t and t in c["name"].lower()]
    if len(pool) != 1:
        names = ", ".join(c["name"] for c in D.cards if c["rarity"] in D.RARITY_CHANCES)
        return await m.answer("Использование: /buycard название\nДоступны: " + esc(names))
    c = pool[0]
    price = c["price"] * 3
    if not spend(uid, price):
        return await m.answer(f"❌ Нужно {fmt(price)} монет.")
    add_card(uid, c["name"])
    await m.answer(f"✅ Куплено: {esc(c['name'])} за {fmt(price)}")


# ═════════════════════════ АУКЦИОН ═════════════════════════
@fx.message(Command("auction"))
async def cmd_auction(m: Message, command: CommandObject):
    uid = ensure(m)
    parts = (command.args or "").rsplit(maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        return await m.answer("Использование: /auction название стартовая_цена\nТаймер 24 часа, комиссия 5%.")
    name, start = resolve_owned(uid, parts[0]), int(parts[1])
    if not name or name == ALWAYS or start <= 0:
        return await m.answer("❌ Карта не найдена / нельзя выставить.")
    best = min(copies(uid, name), key=lambda c: c["price"])
    mm = best["mods"]
    del_card(best["id"])
    ends = (datetime.now() + timedelta(hours=24)).isoformat()
    aid = db.execute("INSERT INTO auctions(seller,card,upg,merged,sharp,start_price,ends,chat_id) VALUES(?,?,?,?,?,?,?,?)",
                     (uid, name, mm["upg"], mm["merged"], mm["sharp"], start, ends, m.chat.id)).lastrowid
    db.commit()
    await m.answer(f"🔨 Лот #{aid}: {esc(name)}\nСтарт: {fmt(start)} монет, 24 часа.\nСтавка: /bid {aid} сумма")


def auction_lines():
    rows = db.execute("SELECT id,card,start_price,bid,bidder,ends FROM auctions WHERE done=0 ORDER BY ends").fetchall()
    out = []
    for aid, card, sp, bid, bidder, ends in rows:
        left = max(0, int((datetime.fromisoformat(ends) - datetime.now()).total_seconds() // 60))
        out.append(f"#{aid} {esc(card)} — {'ставка ' + fmt(bid) + ' (' + nm(bidder) + ')' if bid else 'старт ' + fmt(sp)} — {left // 60}ч {left % 60}м")
    return out


@fx.message(Command("auctions"))
async def cmd_auctions(m: Message):
    ensure(m)
    lines = auction_lines()
    await m.answer("🔨 <b>Аукцион</b>\n\n" + ("\n".join(lines) if lines else "Лотов нет. /auction название цена"))


@fx.message(Command("bid"))
async def cmd_bid(m: Message, command: CommandObject):
    uid = ensure(m)
    a = (command.args or "").split()
    if len(a) != 2 or not a[0].isdigit() or not a[1].isdigit():
        return await m.answer("Использование: /bid id сумма")
    aid, amt = int(a[0]), int(a[1])
    r = db.execute("SELECT seller,card,start_price,bid,bidder,done FROM auctions WHERE id=?", (aid,)).fetchone()
    if not r or r[5]:
        return await m.answer("❌ Лот не найден или завершён.")
    seller, card, sp, bid, bidder, _ = r
    if seller == uid:
        return await m.answer("❌ Нельзя ставить на свой лот.")
    need = sp if not bid else int(bid * 1.05) + 1
    if amt < need:
        return await m.answer(f"❌ Минимальная ставка: {fmt(need)}")
    if not spend(uid, amt):
        return await m.answer("❌ Не хватает монет.")
    if bidder:
        add_coins(bidder, bid)
        await say(bidder, f"🔨 Вашу ставку на лот #{aid} перебили. Монеты возвращены ({fmt(bid)}).")
    db.execute("UPDATE auctions SET bid=?, bidder=? WHERE id=?", (amt, uid, aid))
    db.commit()
    await m.answer(f"✅ Ставка {fmt(amt)} на лот #{aid} ({esc(card)}) принята!")


async def settle_auctions():
    rows = db.execute("SELECT id,seller,card,upg,merged,sharp,bid,bidder,chat_id FROM auctions WHERE done=0 AND ends<=?",
                      (datetime.now().isoformat(),)).fetchall()
    for aid, seller, card, upg, merged, sharp, bid, bidder, chat in rows:
        db.execute("UPDATE auctions SET done=1 WHERE id=?", (aid,))
        db.commit()
        mods = {"upg": upg, "merged": merged, "sharp": sharp}
        if bidder:
            add_card(bidder, card, mods)
            add_coins(seller, int(bid * 0.95))
            await say(chat, f"🔨 Лот #{aid} завершён!\n🎴 {esc(card)} → {nm(bidder)} за {fmt(bid)}\n💰 Продавец {nm(seller)} получил {fmt(int(bid * 0.95))}")
        else:
            add_card(seller, card, mods)
            await say(chat, f"🔨 Лот #{aid} ({esc(card)}) не продан — карта возвращена {nm(seller)}.")


async def bg_loop():
    while True:
        try:
            await settle_auctions()
            now = time.time()
            for fid, f in list(fights.items()):
                if f["stage"] not in ("bets", "done") and now - f["ts"] > 600:
                    fights.pop(fid, None)
                    await say(f["chat_id"], "⌛ Бой отменён: время вышло.")
        except Exception:
            log.exception("bg_loop")
        await asyncio.sleep(30)


# ═════════════════════════ ДУЭЛИ И БИТВЫ ═════════════════════════
fights = {}
duel_cd = {}


def pick_list(uid):
    names = Counter(n for _, n in inv_rows(uid) if n != ALWAYS)
    return sorted(names.items(), key=lambda x: (-base_price(x[0]), x[0]))


def avail_for(f, uid):
    used = Counter(f["picks"][uid])
    return [(n, c - used[n]) for n, c in pick_list(uid) if c - used[n] > 0]


def picker_kb(f, uid, page):
    f["avail"] = avail_for(f, uid)
    ps = 6
    pages = max(1, (len(f["avail"]) + ps - 1) // ps)
    page %= pages
    rows = [[(f"{n} ×{c}", f"fx_fs:{f['id']}:{page * ps + i}")] for i, (n, c) in enumerate(f["avail"][page * ps:(page + 1) * ps])]
    if pages > 1:
        rows.append([("◀️", f"fx_fp:{f['id']}:{page - 1}"), (f"{page + 1}/{pages}", "cards_noop"), ("▶️", f"fx_fp:{f['id']}:{page + 1}")])
    rows.append([("❌ Отмена", f"fx_fc:{f['id']}")])
    return KB(*rows)


def picker_text(f, uid):
    who = nm(uid)
    kind = "⚔️ Дуэль" if f["mode"] == "duel" else "🛡 Битва (3 карты)"
    stake = "\nПобедитель забирает карту проигравшего!" if f["mode"] == "duel" else ""
    return f"{kind}: {nm(f['a'])} vs {nm(f['b'])}{stake}\n\n{who}, выбери карту ({len(f['picks'][uid])}/{f['need']}):"


@fx.message(Command("duel", "battle"))
async def cmd_duel(m: Message, command: CommandObject):
    uid = ensure(m)
    mode = "duel" if command.command == "duel" else "battle"
    need = 1 if mode == "duel" else 3
    tid, _ = get_target(m, command.args)
    if not tid or tid == uid:
        return await m.answer(f"Использование: /{command.command} @username (или ответом на сообщение)")
    if time.time() - duel_cd.get(uid, 0) < DUEL_CD:
        return await m.answer(f"⏳ Кулдаун: {int(DUEL_CD - (time.time() - duel_cd[uid]))} сек.")
    if sum(c for _, c in pick_list(uid)) < need or sum(c for _, c in pick_list(tid)) < need:
        return await m.answer(f"❌ У обоих игроков должно быть минимум {need} карт.")
    if any(f["a"] in (uid, tid) or f["b"] in (uid, tid) for f in fights.values()):
        return await m.answer("❌ Кто-то из вас уже в бою.")
    fid = os.urandom(3).hex()
    fights[fid] = {"id": fid, "mode": mode, "chat_id": m.chat.id, "a": uid, "b": tid, "need": need,
                   "stage": "invite", "picks": {uid: [], tid: []}, "bets": [], "ts": time.time(), "avail": []}
    duel_cd[uid] = time.time()
    await m.answer(f"{'⚔️ Дуэль' if mode == 'duel' else '🛡 Битва'}! {nm(uid)} вызывает {nm(tid)}\n"
                   f"{'Победитель забирает карту проигравшего.' if mode == 'duel' else 'Побеждает сильнейшая тройка.'}",
                   reply_markup=KB([("✅ Принять", f"fx_fa:{fid}:1"), ("❌ Отказаться", f"fx_fa:{fid}:0")]))


def get_fight(call, fid):
    f = fights.get(fid)
    return f


@fx.callback_query(F.data.startswith("fx_fa:"))
async def cb_fight_answer(call: CallbackQuery):
    _, fid, yes = call.data.split(":")
    f = fights.get(fid)
    if not f or f["stage"] != "invite":
        return await call.answer("Вызов неактуален.", show_alert=True)
    u = call.from_user.id
    if yes == "0":
        if u not in (f["a"], f["b"]):
            return await call.answer("Это не твой вызов!", show_alert=True)
        fights.pop(fid, None)
        await edit(call, "❌ Вызов отклонён.")
        return await call.answer()
    if u != f["b"]:
        return await call.answer("Принять может только вызванный игрок!", show_alert=True)
    f["stage"] = "pickA"
    f["ts"] = time.time()
    await edit(call, picker_text(f, f["a"]), picker_kb(f, f["a"], 0))
    await call.answer("Принято!")


def current_picker(f):
    return f["a"] if f["stage"] == "pickA" else f["b"]


@fx.callback_query(F.data.startswith("fx_fp:"))
async def cb_fight_page(call: CallbackQuery):
    _, fid, page = call.data.split(":")
    f = fights.get(fid)
    if not f or f["stage"] not in ("pickA", "pickB") or call.from_user.id != current_picker(f):
        return await call.answer("Не твой выбор!", show_alert=True)
    await edit(call, picker_text(f, call.from_user.id), picker_kb(f, call.from_user.id, int(page)))
    await call.answer()


@fx.callback_query(F.data.startswith("fx_fc:"))
async def cb_fight_cancel(call: CallbackQuery):
    f = fights.get(call.data.split(":")[1])
    if not f or call.from_user.id not in (f["a"], f["b"]) or f["stage"] in ("bets", "done"):
        return await call.answer("Нельзя отменить.", show_alert=True)
    fights.pop(f["id"], None)
    await edit(call, "❌ Бой отменён.")
    await call.answer()


@fx.callback_query(F.data.startswith("fx_fs:"))
async def cb_fight_select(call: CallbackQuery):
    _, fid, idx = call.data.split(":")
    f = fights.get(fid)
    if not f or f["stage"] not in ("pickA", "pickB") or call.from_user.id != current_picker(f):
        return await call.answer("Не твой выбор!", show_alert=True)
    uid = call.from_user.id
    f["avail"] = avail_for(f, uid)
    idx = int(idx)
    if idx >= len(f["avail"]):
        return await call.answer("Список обновился, выбери снова.", show_alert=True)
    f["picks"][uid].append(f["avail"][idx][0])
    f["ts"] = time.time()
    if len(f["picks"][uid]) < f["need"]:
        await edit(call, picker_text(f, uid), picker_kb(f, uid, 0))
        return await call.answer("Выбрано!")
    if f["stage"] == "pickA":
        f["stage"] = "pickB"
        await edit(call, picker_text(f, f["b"]), picker_kb(f, f["b"], 0))
        return await call.answer("Готово!")
    f["stage"] = "bets"
    await call.answer("Карты выбраны!")
    amts = (1000, 10000)
    rows = [[(f"Ставка {fmt(a)} на {nm(f['a'])}", f"fx_fb:{fid}:0:{a}") for a in amts],
            [(f"Ставка {fmt(a)} на {nm(f['b'])}", f"fx_fb:{fid}:1:{a}") for a in amts]]
    await edit(call, f"🎲 Карты выбраны! Приём ставок {BET_SECONDS} сек.\nПобедившая сторона: ×2 к ставке.\n"
                     f"{nm(f['a'])} vs {nm(f['b'])}", KB(*rows))
    asyncio.create_task(run_fight(f, call.message))


@fx.callback_query(F.data.startswith("fx_fb:"))
async def cb_fight_bet(call: CallbackQuery):
    _, fid, side, amt = call.data.split(":")
    f = fights.get(fid)
    uid = call.from_user.id
    if not f or f["stage"] != "bets":
        return await call.answer("Ставки закрыты.", show_alert=True)
    if uid in (f["a"], f["b"]):
        return await call.answer("Игроки не ставят на себя!", show_alert=True)
    D.get_user(uid, call.from_user.username)
    if not spend(uid, int(amt)):
        return await call.answer("Не хватает монет!", show_alert=True)
    f["bets"].append((uid, int(side), int(amt)))
    await call.answer(f"Ставка {fmt(int(amt))} принята!")


def power(names):
    return sum(pts(n) * random.uniform(0.75, 1.25) for n in names)


async def run_fight(f, msg):
    await asyncio.sleep(BET_SECONDS)
    fights.pop(f["id"], None)
    f["stage"] = "done"
    a, b = f["a"], f["b"]
    pa, pb = power(f["picks"][a]), power(f["picks"][b])
    win = 0 if pa >= pb else 1
    w, l = (a, b) if win == 0 else (b, a)
    try:
        await msg.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    def info(uid, p):
        names = f["picks"][uid]
        if f["mode"] == "duel":
            return {"name": nm(uid), "sub": f"{names[0]} {rar(names[0])}", "color": rarity_color(rar(names[0]))}
        return {"name": nm(uid), "sub": f"3 карты, сила {p:.1f}", "color": (255, 200, 40)}

    ext_add(w, "duel_wins", 1)
    add_xp(w, 30)
    add_xp(l, 5)
    track(w, "duelwin")
    res = [f"{'⚔️ Дуэль' if f['mode'] == 'duel' else '🛡 Битва'}: {nm(a)} ({pa:.1f}) vs {nm(b)} ({pb:.1f})", f"🏆 Победил {nm(w)}!"]
    if f["mode"] == "duel":
        lost = f["picks"][l][0]
        cs = copies(l, lost)
        if cs:
            c = min(cs, key=lambda x: x["price"])
            del_card(c["id"])
            add_card(w, lost, c["mods"])
            res.append(f"🎴 {nm(w)} забирает карту: {esc(lost)}")
        else:
            add_coins(w, base_price(lost))
            res.append(f"Карта {esc(lost)} уже продана — компенсация {fmt(base_price(lost))} монет.")
    else:
        reward = 15000 + int(sum(pts(n) for n in f["picks"][w]) * 3000)
        add_coins(w, reward)
        res.append(f"💰 {nm(w)} получает {fmt(reward)} монет")
    pool = sum(x[2] for x in f["bets"])
    won = [x for x in f["bets"] if x[1] == win]
    for uid, _s, amt in won:
        add_coins(uid, amt * 2)
    if f["bets"]:
        res.append(f"🎲 Ставки: {len(f['bets'])} на {fmt(pool)}, выиграли {len(won)} (×2)")
    key = f"vs_{f['id']}"
    await play(msg, key, GV.render_versus_video if VIDEO_OK else None,
               (info(a, pa), info(b, pb), win), GV.VERSUS_SECONDS if VIDEO_OK else 0,
               f"{nm(a)} ⚔️ {nm(b)}", "\n".join(res))
    await tr(f["chat_id"], w, "duelwin")


# ═════════════════════════ КРУТИЛКА / РУЛЕТКА ═════════════════════════
@fx.message(Command("spin"))
async def cmd_spin(m: Message):
    uid = ensure(m)
    await do_spin(m, uid)


async def do_spin(m, uid):
    if not spend(uid, SPIN_COST):
        return await m.answer(f"❌ Нужно {fmt(SPIN_COST)} монет.")
    card, r = roll_rarity_card(SPIN_W)
    add_card(uid, card["name"])
    pool = [c for c in D.cards if c["rarity"] in SPIN_W and c["name"] != card["name"]]
    items = [(card["name"], rarity_color(r))] + [(c["name"], rarity_color(c["rarity"])) for c in random.sample(pool, min(6, len(pool)))]
    key = f"spin_{uid}_{time.time()}"
    text = f"🎴 <b>Крутилка</b>\nВыпало: {esc(card['name'])}\n{r} | 💰 {fmt(card['price'])}"
    kb = KB([("🎴 Крутить снова (5 000)", f"fx_again:spin:{uid}")])
    await play(m, key, GV.render_strip_video if VIDEO_OK else None, (items, 0), GV.STRIP_SECONDS if VIDEO_OK else 0,
               "🎴 Крутим...", text, kb)
    await tr(m.chat.id, uid, "spin")
    for t in mark_play(uid, "spin"):
        await say(m.chat.id, t)


@fx.callback_query(F.data.startswith("fx_again:"))
async def cb_again(call: CallbackQuery):
    _, kind, u = call.data.split(":")
    if call.from_user.id != int(u):
        return await call.answer("Не твоё!", show_alert=True)
    await call.answer()
    await do_spin(call.message, int(u))


def roulette_parse(txt):
    t = txt.lower()
    if t in ("красное", "красный", "red", "к"):
        return "red"
    if t in ("чёрное", "черное", "чёрный", "черный", "black", "ч"):
        return "black"
    if t in ("зелёное", "зеленое", "зелёный", "зеленый", "green", "зеро", "г"):
        return "green"
    if t.isdigit() and 0 <= int(t) <= 36:
        return int(t)
    return None


@fx.message(Command("roulette"))
async def cmd_roulette(m: Message, command: CommandObject):
    uid = ensure(m)
    a = (command.args or "").split()
    if len(a) != 2 or not a[1].isdigit() or roulette_parse(a[0]) is None:
        return await m.answer("🎰 /roulette красное|чёрное|зелёное|число(0-36) ставка\n"
                              "Красное/чёрное ×2, зелёное ×14, число ×36.")
    ch, bet = roulette_parse(a[0]), int(a[1])
    if bet <= 0 or not spend(uid, bet):
        return await m.answer("❌ Неверная ставка или не хватает монет.")
    number = random.randint(0, 36)
    color = "green" if number == 0 else ("red" if (VIDEO_OK and number in GV.RED_NUMBERS) or (not VIDEO_OK and number in
              {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}) else "black")
    mult = 0
    if isinstance(ch, int):
        mult = 36 if ch == number else 0
    elif ch == color:
        mult = 14 if ch == "green" else 2
    win = bet * mult
    if win:
        add_coins(uid, win)
    cname = {"red": "🔴 красное", "black": "⚫ чёрное", "green": "🟢 зелёное"}[color]
    res = f"🎰 <b>Рулетка</b>\nВыпало: {number} ({cname})\n" + (f"🎉 Выигрыш {fmt(win)} (×{mult})!" if win else f"❌ Проигрыш {fmt(bet)}")
    await play(m, f"roul_{number}", GV.render_roulette_video if VIDEO_OK else None, (number,),
               GV.ROULETTE_SECONDS if VIDEO_OK else 0, f"🎰 Рулетка — ставка {fmt(bet)}", res)
    for t in mark_play(uid, "roulette"):
        await say(m.chat.id, t)


# ═════════════════════════ БЛЭКДЖЕК ═════════════════════════
bj_games = {}
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]


def bj_val(hand):
    t = sum(10 if r in ("J", "Q", "K", "10") else 11 if r == "A" else int(r) for r, _, _ in hand)
    aces = sum(1 for r, _, _ in hand if r == "A")
    while t > 21 and aces:
        t -= 10
        aces -= 1
    return t


def bj_txt(hand, hide=False):
    parts = [f"{fl}·{r}{SUITS[s]}" for r, s, fl in hand]
    if hide:
        parts = parts[:1] + ["🂠"]
    return "  ".join(parts)


def bj_draw(g):
    r, s = g["deck"].pop()
    return (r, s, random.choice(g["flavors"]))


def bj_kb(uid):
    return KB([("➕ Взять", f"fx_bj:{uid}:hit"), ("✋ Хватит", f"fx_bj:{uid}:stand")])


def bj_screen(g, hide=True):
    return (f"🃏 <b>Блэкджек</b> — ставка {fmt(g['bet'])}\n\n🤖 Дилер: {bj_val(g['dealer']) if not hide else '?'}\n"
            f"{bj_txt(g['dealer'], hide)}\n\n🙂 Ты: {bj_val(g['player'])}\n{bj_txt(g['player'])}")


@fx.message(Command("bj", "blackjack"))
async def cmd_bj(m: Message, command: CommandObject):
    uid = ensure(m)
    g0 = bj_games.get(uid)
    if g0 and time.time() - g0["ts"] < 600:
        return await m.answer("У тебя уже идёт партия — закончи её кнопками.")
    try:
        bet = int((command.args or "").strip())
    except ValueError:
        return await m.answer("Использование: /bj ставка")
    if bet <= 0 or not spend(uid, bet):
        return await m.answer("❌ Неверная ставка или не хватает монет.")
    names = [n for _, n in inv_rows(uid)] or [c["name"] for c in D.cards]
    deck = [(r, s) for r in RANKS for s in range(4)]
    random.shuffle(deck)
    g = {"deck": deck, "bet": bet, "flavors": names, "ts": time.time(), "chat": m.chat.id}
    g["player"] = [bj_draw(g), bj_draw(g)]
    g["dealer"] = [bj_draw(g), bj_draw(g)]
    bj_games[uid] = g
    if bj_val(g["player"]) == 21:
        return await bj_finish(m, uid)
    await m.answer(bj_screen(g), reply_markup=bj_kb(uid))


@fx.callback_query(F.data.startswith("fx_bj:"))
async def cb_bj(call: CallbackQuery):
    _, u, act = call.data.split(":")
    uid = int(u)
    g = bj_games.get(uid)
    if call.from_user.id != uid or not g:
        return await call.answer("Это не твоя партия!", show_alert=True)
    if act == "hit":
        g["player"].append(bj_draw(g))
        if bj_val(g["player"]) < 21:
            await edit(call, bj_screen(g), bj_kb(uid))
            return await call.answer()
    await call.answer()
    try:
        await call.message.delete()
    except Exception:
        pass
    await bj_finish(call.message, uid)


async def bj_finish(msg, uid):
    g = bj_games.pop(uid, None)
    if not g:
        return
    pv = bj_val(g["player"])
    natural = len(g["player"]) == 2 and pv == 21
    if pv <= 21:
        while bj_val(g["dealer"]) < 17:
            g["dealer"].append(bj_draw(g))
    dv = bj_val(g["dealer"])
    bet = g["bet"]
    if pv > 21:
        pay, res = 0, "💥 Перебор! Ты проиграл."
    elif natural and dv != 21:
        pay, res = int(bet * 2.5), "🎉 БЛЭКДЖЕК! ×2.5"
    elif dv > 21 or pv > dv:
        pay, res = bet * 2, "🎉 Победа! ×2"
    elif pv == dv:
        pay, res = bet, "🤝 Ничья — ставка возвращена."
    else:
        pay, res = 0, "❌ Дилер выиграл."
    if pay:
        add_coins(uid, pay)
    text = f"{bj_screen(g, hide=False)}\n\n{res}" + (f"\n💰 +{fmt(pay - bet)}" if pay > bet else "")
    pl = [(r, s) for r, s, _ in g["player"]]
    dl = [(r, s) for r, s, _ in g["dealer"]]
    await play(msg, f"bj_{uid}_{time.time()}", GV.render_deal_video if VIDEO_OK else None,
               (pl, dl, ("Ты", "Дилер"), res.split("!")[0][:20]),
               GV.deal_seconds(len(pl) + len(dl)) if VIDEO_OK else 0, "🃏 Раздача...", text)
    for t in mark_play(uid, "blackjack"):
        await say(g["chat"], t)


# ═════════════════════════ ПОКЕР ═════════════════════════
pk_games = {}
RS = {11: "J", 12: "Q", 13: "K", 14: "A"}
HAND_NAMES = ["Старшая карта", "Пара", "Две пары", "Сет", "Стрит", "Флеш", "Фулл-хаус", "Каре", "Стрит-флеш"]


def rk(c):
    return RS.get(c[0], str(c[0]))


def poker_eval(hand):
    ranks = sorted([c[0] for c in hand], reverse=True)
    cnt = Counter(ranks)
    groups = sorted(cnt.items(), key=lambda x: (x[1], x[0]), reverse=True)
    flush = len({c[1] for c in hand}) == 1
    uniq = sorted(set(ranks), reverse=True)
    straight, high = False, None
    if len(uniq) == 5:
        if uniq[0] - uniq[4] == 4:
            straight, high = True, uniq[0]
        elif uniq == [14, 5, 4, 3, 2]:
            straight, high = True, 5
    shape = [g[1] for g in groups]
    if straight and flush:
        cat = 8
    elif shape[0] == 4:
        cat = 7
    elif shape == [3, 2]:
        cat = 6
    elif flush:
        cat = 5
    elif straight:
        cat = 4
    elif shape[0] == 3:
        cat = 3
    elif shape[:2] == [2, 2]:
        cat = 2
    elif shape[0] == 2:
        cat = 1
    else:
        cat = 0
    return (cat, [high] if straight else [g[0] for g in groups])


def pk_kb(uid, g):
    row = [((("✅ " if i in g["hold"] else "") + f"{rk(c)}{SUITS[c[1]]}"), f"fx_pk:{uid}:{i}") for i, c in enumerate(g["hand"])]
    return KB(row, [("🔄 Обменять остальные", f"fx_pkd:{uid}")])


def pk_text(g):
    return (f"🂡 <b>Покер (5 карт, одна замена)</b> — ставка {fmt(g['bet'])}\n\nТвоя рука:\n"
            f"{'  '.join(rk(c) + SUITS[c[1]] for c in g['hand'])}\n🧾 {HAND_NAMES[poker_eval(g['hand'])[0]]}\n\n"
            f"Нажми на карты, которые хочешь ОСТАВИТЬ (✅), затем «Обменять».")


@fx.message(Command("poker"))
async def cmd_poker(m: Message, command: CommandObject):
    uid = ensure(m)
    g0 = pk_games.get(uid)
    if g0 and time.time() - g0["ts"] < 600:
        return await m.answer("У тебя уже идёт партия.")
    try:
        bet = int((command.args or "").strip())
    except ValueError:
        return await m.answer("Использование: /poker ставка (играешь против бота)")
    if bet <= 0 or not spend(uid, bet):
        return await m.answer("❌ Неверная ставка или не хватает монет.")
    deck = [(r, s) for r in range(2, 15) for s in range(4)]
    random.shuffle(deck)
    g = {"deck": deck, "bet": bet, "hand": [deck.pop() for _ in range(5)], "bot": [deck.pop() for _ in range(5)],
         "hold": set(), "ts": time.time(), "chat": m.chat.id}
    pk_games[uid] = g
    await m.answer(pk_text(g), reply_markup=pk_kb(uid, g))


@fx.callback_query(F.data.startswith("fx_pk:"))
async def cb_pk_toggle(call: CallbackQuery):
    _, u, i = call.data.split(":")
    uid, i = int(u), int(i)
    g = pk_games.get(uid)
    if call.from_user.id != uid or not g:
        return await call.answer("Это не твоя партия!", show_alert=True)
    g["hold"] ^= {i}
    await edit(call, pk_text(g), pk_kb(uid, g))
    await call.answer()


@fx.callback_query(F.data.startswith("fx_pkd:"))
async def cb_pk_draw(call: CallbackQuery):
    uid = int(call.data.split(":")[1])
    g = pk_games.pop(uid, None)
    if call.from_user.id != uid or not g:
        return await call.answer("Это не твоя партия!", show_alert=True)
    await call.answer()
    for i in range(5):
        if i not in g["hold"]:
            g["hand"][i] = g["deck"].pop()
    cnt = Counter(c[0] for c in g["bot"])
    keep = [c for c in g["bot"] if cnt[c[0]] >= 2] or sorted(g["bot"], reverse=True)[:2]
    g["bot"] = keep + [g["deck"].pop() for _ in range(5 - len(keep))]
    pe, be = poker_eval(g["hand"]), poker_eval(g["bot"])
    bet = g["bet"]
    if pe > be:
        pay, res = bet * 2, "🎉 Победа! ×2"
    elif pe == be:
        pay, res = bet, "🤝 Ничья — ставка возвращена."
    else:
        pay, res = 0, "❌ Бот выиграл."
    if pay:
        add_coins(uid, pay)
    try:
        await call.message.delete()
    except Exception:
        pass
    text = (f"🂡 <b>Покер</b> — ставка {fmt(bet)}\n\n🙂 Ты: {'  '.join(rk(c) + SUITS[c[1]] for c in g['hand'])} — {HAND_NAMES[pe[0]]}\n"
            f"🤖 Бот: {'  '.join(rk(c) + SUITS[c[1]] for c in g['bot'])} — {HAND_NAMES[be[0]]}\n\n{res}")
    pl = [(rk(c), c[1]) for c in g["hand"]]
    bt = [(rk(c), c[1]) for c in g["bot"]]
    await play(call.message, f"pk_{uid}_{time.time()}", GV.render_deal_video if VIDEO_OK else None,
               (pl, bt, ("Ты", "Бот"), res.split("!")[0][:20]),
               GV.deal_seconds(10) if VIDEO_OK else 0, "🂡 Вскрываемся...", text)
    for t in mark_play(uid, "poker"):
        await say(g["chat"], t)


# ═════════════════════════ КЛАНЫ ═════════════════════════
def clan_of(uid):
    r = db.execute("SELECT c.id, c.name, c.owner FROM clans c JOIN clan_members m ON m.clan_id=c.id WHERE m.user_id=?", (uid,)).fetchone()
    return r


def clan_members(cid):
    return [r[0] for r in db.execute("SELECT user_id FROM clan_members WHERE clan_id=?", (cid,)).fetchall()]


@fx.message(Command("clan_create"))
async def cmd_clan_create(m: Message, command: CommandObject):
    uid = ensure(m)
    name = (command.args or "").strip()[:30]
    if not name:
        return await m.answer("Использование: /clan_create Название (стоимость 100 000)")
    if clan_of(uid):
        return await m.answer("❌ Ты уже в клане.")
    if db.execute("SELECT 1 FROM clans WHERE LOWER(name)=LOWER(?)", (name,)).fetchone():
        return await m.answer("❌ Такое имя занято.")
    if not spend(uid, 100000):
        return await m.answer("❌ Нужно 100 000 монет.")
    cid = db.execute("INSERT INTO clans(name,owner,created) VALUES(?,?,?)", (name, uid, datetime.now().isoformat())).lastrowid
    db.execute("INSERT INTO clan_members VALUES(?,?)", (uid, cid))
    db.commit()
    ext_set(uid, clan_id=cid)
    await m.answer(f"🏰 Клан «{esc(name)}» создан! Приглашай: /clan_invite @user")


@fx.message(Command("clan"))
async def cmd_clan(m: Message, command: CommandObject):
    uid = ensure(m)
    if command.args:
        c = db.execute("SELECT id,name,owner FROM clans WHERE LOWER(name)=LOWER(?)", (command.args.strip(),)).fetchone()
    else:
        c = clan_of(uid)
    if not c:
        return await m.answer("Ты не в клане. /clan_create Название")
    cid, name, owner = c
    mem = clan_members(cid)
    stash = db.execute("SELECT COUNT(*) FROM stash WHERE owner=?", (f"clan:{cid}",)).fetchone()[0]
    await m.answer(f"🏰 <b>{esc(name)}</b>\n👑 Глава: {nm(owner)}\n👥 Участники ({len(mem)}): {', '.join(nm(x) for x in mem)}\n📦 Склад: {stash} карт")


@fx.message(Command("clan_invite"))
async def cmd_clan_invite(m: Message, command: CommandObject):
    uid = ensure(m)
    c = clan_of(uid)
    tid, _ = get_target(m, command.args)
    if not c or c[2] != uid:
        return await m.answer("❌ Приглашать может глава клана.")
    if not tid or clan_of(tid):
        return await m.answer("❌ Игрок не найден или уже в клане.")
    await m.answer(f"🏰 {nm(tid)}, клан «{esc(c[1])}» зовёт тебя!",
                   reply_markup=KB([("✅ Вступить", f"fx_ci:{c[0]}:{tid}:1"), ("❌ Отказ", f"fx_ci:{c[0]}:{tid}:0")]))


@fx.callback_query(F.data.startswith("fx_ci:"))
async def cb_clan_invite(call: CallbackQuery):
    _, cid, tid, yes = call.data.split(":")
    if call.from_user.id != int(tid):
        return await call.answer("Это приглашение не тебе!", show_alert=True)
    if yes == "1" and not clan_of(int(tid)):
        db.execute("INSERT OR REPLACE INTO clan_members VALUES(?,?)", (int(tid), int(cid)))
        db.commit()
        ext_set(int(tid), clan_id=int(cid))
        await edit(call, f"✅ {nm(int(tid))} вступил в клан!")
    else:
        await edit(call, "❌ Приглашение отклонено.")
    await call.answer()


@fx.message(Command("clan_leave"))
async def cmd_clan_leave(m: Message):
    uid = ensure(m)
    c = clan_of(uid)
    if not c:
        return await m.answer("Ты не в клане.")
    if c[2] == uid:
        return await m.answer("Глава не может выйти. Используй /clan_disband")
    db.execute("DELETE FROM clan_members WHERE user_id=?", (uid,))
    db.commit()
    ext_set(uid, clan_id=0)
    await m.answer("Ты покинул клан.")


@fx.message(Command("clan_disband"))
async def cmd_clan_disband(m: Message):
    uid = ensure(m)
    c = clan_of(uid)
    if not c or c[2] != uid:
        return await m.answer("❌ Только глава.")
    for u in clan_members(c[0]):
        ext_set(u, clan_id=0)
    # карты со склада возвращаются главе
    for n, upg, mg, sh in db.execute("SELECT card_name,upg,merged,sharp FROM stash WHERE owner=?", (f"clan:{c[0]}",)).fetchall():
        add_card(uid, n, {"upg": upg, "merged": mg, "sharp": sh})
    db.execute("DELETE FROM stash WHERE owner=?", (f"clan:{c[0]}",))
    db.execute("DELETE FROM clan_members WHERE clan_id=?", (c[0],))
    db.execute("DELETE FROM clans WHERE id=?", (c[0],))
    db.commit()
    await m.answer("🏰 Клан распущен. Карты склада возвращены главе.")


@fx.message(Command("clan_chat"))
async def cmd_clan_chat(m: Message, command: CommandObject):
    uid = ensure(m)
    c = clan_of(uid)
    if not c or not command.args:
        return await m.answer("Использование: /clan_chat текст (ты должен быть в клане)")
    for u in clan_members(c[0]):
        if u != uid:
            await say(u, f"🏰 [{esc(c[1])}] {nm(uid)}: {esc(command.args)}")
    await m.answer("📨 Отправлено клану.")


def stash_put(owner, uid, name):
    cs = copies(uid, name)
    if not cs:
        return False
    c = min(cs, key=lambda x: x["price"])
    del_card(c["id"])
    db.execute("INSERT INTO stash VALUES(?,?,?,?,?)", (owner, name, c["mods"]["upg"], c["mods"]["merged"], c["mods"]["sharp"]))
    db.commit()
    return True


def stash_take(owner, uid, text):
    rows = db.execute("SELECT rowid, card_name, upg, merged, sharp FROM stash WHERE owner=?", (owner,)).fetchall()
    t = text.strip().lower()
    for rid, n, upg, mg, sh in rows:
        if t and t in n.lower():
            db.execute("DELETE FROM stash WHERE rowid=?", (rid,))
            db.commit()
            add_card(uid, n, {"upg": upg, "merged": mg, "sharp": sh})
            return n
    return None


@fx.message(Command("clan_put"))
async def cmd_clan_put(m: Message, command: CommandObject):
    uid = ensure(m)
    c = clan_of(uid)
    name = resolve_owned(uid, command.args)
    if not c or not name or name == ALWAYS:
        return await m.answer("Использование: /clan_put название (нужен клан и карта)")
    stash_put(f"clan:{c[0]}", uid, name)
    await m.answer(f"📦 {esc(name)} отправлена на склад клана.")


@fx.message(Command("clan_take"))
async def cmd_clan_take(m: Message, command: CommandObject):
    uid = ensure(m)
    c = clan_of(uid)
    if not c or c[2] != uid:
        return await m.answer("❌ Брать со склада может только глава.")
    n = stash_take(f"clan:{c[0]}", uid, command.args or "")
    await m.answer(f"📦 Получено: {esc(n)}" if n else "❌ Такой карты на складе нет.")


@fx.message(Command("clan_battle"))
async def cmd_clan_battle(m: Message, command: CommandObject):
    uid = ensure(m)
    c = clan_of(uid)
    if not c or c[2] != uid:
        return await m.answer("❌ Вызывать на бой может только глава клана.")
    row = db.execute("SELECT id,name FROM clans WHERE LOWER(name)=LOWER(?)", ((command.args or "").strip(),)).fetchone()
    if not row or row[0] == c[0]:
        return await m.answer("Использование: /clan_battle Название_другого_клана")
    lb = db.execute("SELECT last_battle FROM clans WHERE id=?", (c[0],)).fetchone()[0]
    if lb and datetime.now() - datetime.fromisoformat(lb) < timedelta(hours=1):
        return await m.answer("⏳ Клановые битвы раз в час.")

    def cp(cid):
        allp = []
        for u in clan_members(cid):
            allp += [pts(n) for _, n in inv_rows(u)]
        return sum(sorted(allp, reverse=True)[:5]) * random.uniform(0.85, 1.15)

    pa, pb = cp(c[0]), cp(row[0])
    win = 0 if pa >= pb else 1
    wid, wname = (c[0], c[1]) if win == 0 else row
    db.execute("UPDATE clans SET last_battle=? WHERE id=?", (datetime.now().isoformat(), c[0]))
    db.commit()
    mem = clan_members(wid)
    for u in mem:
        add_coins(u, 20000)
    text = f"🏰 Клановая битва: {esc(c[1])} ({pa:.1f}) vs {esc(row[1])} ({pb:.1f})\n🏆 Победил «{esc(wname)}»! Каждый участник +20 000 монет"
    await play(m, f"cb_{time.time()}", GV.render_versus_video if VIDEO_OK else None,
               ({"name": c[1], "sub": f"сила {pa:.1f}", "color": (255, 200, 40)},
                {"name": row[1], "sub": f"сила {pb:.1f}", "color": (60, 140, 255)}, win),
               GV.VERSUS_SECONDS if VIDEO_OK else 0, "🏰 Битва кланов!", text)


# ═════════════════════════ ДРУЗЬЯ / ПОДАРКИ ═════════════════════════
def are_friends(a, b):
    return bool(db.execute("SELECT 1 FROM friends WHERE a=? AND b=?", (a, b)).fetchone())


@fx.message(Command("add"))
async def cmd_add(m: Message, command: CommandObject):
    uid = ensure(m)
    tid, _ = get_target(m, command.args)
    if not tid or tid == uid or are_friends(uid, tid):
        return await m.answer("Использование: /add @username (или ответом). Игрок должен существовать и не быть другом.")
    await m.answer(f"🤝 {nm(tid)}, {nm(uid)} хочет добавить тебя в друзья!",
                   reply_markup=KB([("✅ Принять", f"fx_fr:{uid}:{tid}:1"), ("❌ Нет", f"fx_fr:{uid}:{tid}:0")]))


@fx.callback_query(F.data.startswith("fx_fr:"))
async def cb_friend(call: CallbackQuery):
    _, a, b, yes = call.data.split(":")
    a, b = int(a), int(b)
    if call.from_user.id != b:
        return await call.answer("Это не тебе!", show_alert=True)
    if yes == "1":
        db.execute("INSERT OR IGNORE INTO friends VALUES(?,?)", (a, b))
        db.execute("INSERT OR IGNORE INTO friends VALUES(?,?)", (b, a))
        db.commit()
        await edit(call, f"🤝 {nm(a)} и {nm(b)} теперь друзья!")
    else:
        await edit(call, "❌ Заявка отклонена.")
    await call.answer()


@fx.message(Command("friends"))
async def cmd_friends(m: Message):
    uid = ensure(m)
    fr = [r[0] for r in db.execute("SELECT b FROM friends WHERE a=?", (uid,)).fetchall()]
    if not fr:
        return await m.answer("Друзей нет. /add @user")
    lines = [f"• {nm(f)} — 🎴 {inv_count(f)} карт, 💰 {fmt(bal(f))} (профиль: /profile {nm(f)})" for f in fr]
    await m.answer("👥 <b>Друзья</b>\n" + "\n".join(lines))


@fx.message(Command("unfriend"))
async def cmd_unfriend(m: Message, command: CommandObject):
    uid = ensure(m)
    tid, _ = get_target(m, command.args)
    if tid:
        db.execute("DELETE FROM friends WHERE (a=? AND b=?) OR (a=? AND b=?)", (uid, tid, tid, uid))
        db.commit()
    await m.answer("Готово.")


@fx.message(Command("gift"))
async def cmd_gift(m: Message, command: CommandObject):
    uid = ensure(m)
    tid, rest = get_target(m, command.args)
    name = resolve_owned(uid, rest)
    if not tid or not name or name == ALWAYS:
        return await m.answer("Использование: /gift @друг название_карты")
    if not are_friends(uid, tid):
        return await m.answer("❌ Дарить можно только друзьям (/add).")
    c = min(copies(uid, name), key=lambda x: x["price"])
    del_card(c["id"])
    add_card(tid, name, c["mods"])
    await m.answer(f"🎁 {nm(uid)} подарил {esc(name)} игроку {nm(tid)}!")


# ═════════════════════════ СВАДЬБА ═════════════════════════
@fx.message(Command("marry"))
async def cmd_marry(m: Message, command: CommandObject):
    uid = ensure(m)
    tid, _ = get_target(m, command.args)
    if not tid or tid == uid or ext(uid)["spouse"] or ext(tid)["spouse"]:
        return await m.answer("Использование: /marry @user (оба должны быть свободны)")
    await m.answer(f"💍 {nm(tid)}, {nm(uid)} делает тебе предложение!",
                   reply_markup=KB([("💖 Да!", f"fx_mr:{uid}:{tid}:1"), ("💔 Нет", f"fx_mr:{uid}:{tid}:0")]))


@fx.callback_query(F.data.startswith("fx_mr:"))
async def cb_marry(call: CallbackQuery):
    _, a, b, yes = call.data.split(":")
    a, b = int(a), int(b)
    if call.from_user.id != b:
        return await call.answer("Это не тебе!", show_alert=True)
    if yes == "1" and not ext(a)["spouse"] and not ext(b)["spouse"]:
        ext_set(a, spouse=b)
        ext_set(b, spouse=a)
        await edit(call, f"💒 {nm(a)} и {nm(b)} теперь женаты! Общий инвентарь: /pair")
    else:
        await edit(call, "💔 Предложение отклонено.")
    await call.answer()


@fx.message(Command("divorce"))
async def cmd_divorce(m: Message):
    uid = ensure(m)
    sp = ext(uid)["spouse"]
    if not sp:
        return await m.answer("Ты не в браке.")
    key = f"pair:{min(uid, sp)}:{max(uid, sp)}"
    for n, upg, mg, sh in db.execute("SELECT card_name,upg,merged,sharp FROM stash WHERE owner=?", (key,)).fetchall():
        add_card(uid, n, {"upg": upg, "merged": mg, "sharp": sh})  # общий склад достаётся инициатору
    db.execute("DELETE FROM stash WHERE owner=?", (key,))
    db.commit()
    ext_set(uid, spouse=0)
    ext_set(sp, spouse=0)
    await m.answer("💔 Развод оформлен. Общий склад достался инициатору.")


def pair_key(uid):
    sp = ext(uid)["spouse"]
    return f"pair:{min(uid, sp)}:{max(uid, sp)}" if sp else None


@fx.message(Command("pair"))
async def cmd_pair(m: Message):
    uid = ensure(m)
    k = pair_key(uid)
    if not k:
        return await m.answer("Ты не в браке. /marry @user")
    rows = db.execute("SELECT card_name FROM stash WHERE owner=?", (k,)).fetchall()
    await m.answer("💞 <b>Общий инвентарь</b>\n" + ("\n".join("• " + esc(r[0]) for r in rows) if rows else "Пусто.") +
                   "\n\n/pair_put название — положить, /pair_take название — взять")


@fx.message(Command("pair_put"))
async def cmd_pair_put(m: Message, command: CommandObject):
    uid = ensure(m)
    k, name = pair_key(uid), resolve_owned(uid, command.args)
    if not k or not name or name == ALWAYS:
        return await m.answer("Нужен брак и карта: /pair_put название")
    stash_put(k, uid, name)
    await m.answer(f"💞 {esc(name)} в общем инвентаре.")


@fx.message(Command("pair_take"))
async def cmd_pair_take(m: Message, command: CommandObject):
    uid = ensure(m)
    k = pair_key(uid)
    n = stash_take(k, uid, command.args or "") if k else None
    await m.answer(f"💞 Получено: {esc(n)}" if n else "❌ Не найдено.")


# ═════════════════════════ КОСМЕТИКА ═════════════════════════
def cos_view(uid):
    owned = {r[0] for r in db.execute("SELECT ckey FROM cosmetics WHERE uid=?", (uid,)).fetchall()}
    e = ext(uid)
    lines, rows = ["🎨 <b>Косметика</b>\nНажми на предмет: купить или надеть/снять.\n"], []
    for k, (cat, title, price, _v) in COS.items():
        on = e[cat] == k if cat in ("frame", "skin", "bg") else (e[cat] == COS[k][3])
        mark = "✅ надето" if on else ("🎒 есть" if k in owned else f"💰 {fmt(price)}")
        rows.append([(f"{title} — {mark}", f"fx_cos:{uid}:{k}")])
    return "\n".join(lines), KB(*rows)


@fx.message(Command("cosmetics"))
async def cmd_cos(m: Message):
    uid = ensure(m)
    t, kb = cos_view(uid)
    await m.answer(t, reply_markup=kb)


@fx.callback_query(F.data.startswith("fx_cos:"))
async def cb_cos(call: CallbackQuery):
    _, u, k = call.data.split(":")
    uid = int(u)
    if call.from_user.id != uid or k not in COS:
        return await call.answer("Не твоё!", show_alert=True)
    cat, title, price, val = COS[k]
    owned = db.execute("SELECT 1 FROM cosmetics WHERE uid=? AND ckey=?", (uid, k)).fetchone()
    if not owned:
        if not spend(uid, price):
            return await call.answer(f"Нужно {fmt(price)} монет", show_alert=True)
        db.execute("INSERT INTO cosmetics VALUES(?,?)", (uid, k))
        db.commit()
        await call.answer("Куплено!")
    stored = k if cat in ("frame", "skin", "bg") else val
    e = ext(uid)
    ext_set(uid, **{cat: None if e[cat] == stored else stored})
    t, kb = cos_view(uid)
    await edit(call, t, kb)


# ═════════════════════════ ПРОФИЛЬ / РЕПУТАЦИЯ ═════════════════════════
def profile_image(raw, e):
    from PIL import Image, ImageDraw
    im = Image.open(io.BytesIO(raw)).convert("RGBA")
    w, h = im.size
    if e["bg"] in COS:
        im = Image.alpha_composite(im, Image.new("RGBA", im.size, tuple(COS[e["bg"]][3]) + (70,)))
    if e["frame"] in COS:
        size = int(h * 0.5) + 16
        ax, ay = int(w * 0.10), (h - size) // 2
        ImageDraw.Draw(im).ellipse((ax - 8, ay - 8, ax + size + 8, ay + size + 8), outline=tuple(COS[e["frame"]][3]), width=10)
    out = io.BytesIO()
    im.save(out, "PNG")
    return out.getvalue()


@fx.message(Command("profile"))
async def cmd_profile(m: Message, command: CommandObject):
    me = ensure(m)
    tid, _ = get_target(m, command.args)
    if command.args and not tid and not m.reply_to_message:
        return await m.answer("❌ Игрок не найден.")
    tid = tid or me
    r = db.execute("SELECT username, balance, registered_at, tokens FROM users WHERE user_id=?", (tid,)).fetchone()
    if not r:
        return await m.answer("❌ Игрок не найден.")
    uname, balance, reg, tokens_ = r
    e = ext(tid)
    s = ach_state(tid)
    place = db.execute("SELECT COUNT(*) FROM users WHERE balance>?", (balance,)).fetchone()[0] + 1
    n_ach = db.execute("SELECT COUNT(*) FROM achievements WHERE uid=?", (tid,)).fetchone()[0]
    cl = clan_of(tid)
    st = e["status"] or ""
    caption = (f"{st} <b>@{esc(uname or 'Игрок')}</b> {('«' + esc(e['title']) + '»') if e['title'] else ''}\n"
               f"📅 С {D.format_date_ru(reg)}\n\n💰 {fmt(balance)} монет | ☢️ {tokens_}\n"
               f"⭐ Ур. {xp_level(e['xp'])} ({e['xp']} опыта)\n🏆 Место в топе: #{place}\n"
               f"🎴 Карт: {s['cards']} | 📦 Коллекция: {s['uniq']}/{s['total']}\n🏅 Достижений: {n_ach}/{len(ACH)}\n"
               f"👍 Репутация: {e['rep']}\n🏰 Клан: {esc(cl[1]) if cl else '—'}\n"
               f"💍 Брак: {nm(e['spouse']) if e['spouse'] else '—'}")
    kb = KB([("👍", f"fx_rep:{tid}:1"), ("👎", f"fx_rep:{tid}:-1")]) if tid != me else None
    try:
        raw = (await D.make_profile_image(tid, uname, balance, place, e["xp"] and xp_level(e["xp"]) or 1, s["cards"])).read()
        await m.answer_photo(BufferedInputFile(profile_image(raw, e), "profile.png"), caption=caption, reply_markup=kb)
    except Exception as ex:
        log.debug("profile img %s", ex)
        await m.answer(caption, reply_markup=kb)


@fx.callback_query(F.data.startswith("fx_rep:"))
async def cb_rep(call: CallbackQuery):
    _, t, d = call.data.split(":")
    t, d = int(t), int(d)
    v = call.from_user.id
    D.get_user(v, call.from_user.username)
    if v == t:
        return await call.answer("Себе нельзя!", show_alert=True)
    if db.execute("SELECT 1 FROM rep_votes WHERE voter=? AND target=? AND day=?", (v, t, today())).fetchone():
        return await call.answer("Сегодня ты уже голосовал за него.", show_alert=True)
    db.execute("INSERT INTO rep_votes VALUES(?,?,?)", (v, t, today()))
    db.commit()
    ext_add(t, "rep", d)
    await call.answer("👍 Голос учтён!" if d > 0 else "👎 Голос учтён!")


# ═════════════════════════ ЕЖЕДНЕВНОЕ ═════════════════════════
def active_event(d=None):
    d = d or date.today()
    md = (d.month, d.day)
    bd = os.getenv("BOT_BIRTHDAY", "10-08").split("-")
    try:
        bday = date(d.year, int(bd[0]), int(bd[1]))
    except Exception:
        bday = date(d.year, 10, 8)
    if md >= (12, 20) or md <= (1, 10):
        return ("ny", "🎄 Новый год", 2.0)
    if (2, 10) <= md <= (2, 16):
        return ("val", "💘 Валентинки", 2.0)
    if (6, 20) <= md <= (8, 20):
        return ("sum", "☀️ Летний ивент", 1.5)
    if abs((d - bday).days) <= 3:
        return ("bd", "🎂 День рождения бота", 3.0)
    return None


@fx.message(Command("daily"))
async def cmd_daily(m: Message):
    uid = ensure(m)
    row = db.execute("SELECT last_daily FROM users WHERE user_id=?", (uid,)).fetchone()
    if row and row[0]:
        el = datetime.now() - datetime.fromisoformat(row[0])
        if el < timedelta(days=1):
            secs = int((timedelta(days=1) - el).total_seconds())
            return await m.answer(f"⏳ Ты уже забрал награду.\nПриходи через: {secs // 3600} ч {(secs % 3600) // 60} мин")
    e = ext(uid)
    y = (date.today() - timedelta(days=1)).isoformat()
    streak = e["streak"] + 1 if e["last_streak"] == y else 1
    mult = 2 if streak % 7 == 0 else 1
    ev = active_event()
    em = ev[2] if ev else 1
    gain = int(D.DAILY_TOKENS * mult * em)
    db.execute("UPDATE users SET tokens=tokens+?, last_daily=? WHERE user_id=?", (gain, datetime.now().isoformat(), uid))
    db.commit()
    ext_set(uid, streak=streak, last_streak=today())
    add_xp(uid, 10)
    await m.answer(f"🎁 Ежедневная награда: +{gain} ☢️\n🔥 Стрик: {streak} дн." +
                   ("\n⭐ 7 дней подряд — бонус ×2!" if mult == 2 else f"\n(до бонуса ×2: {7 - streak % 7} дн.)") +
                   (f"\n{ev[1]}: награда ×{ev[2]}" if ev else ""))
    await tr(m.chat.id, uid, "daily")


@fx.message(Command("dcase"))
async def cmd_dcase(m: Message):
    uid = ensure(m)
    if ext(uid)["last_dcase"] == today():
        return await m.answer("📦 Ежедневный кейс уже открыт. Приходи завтра!")
    ext_set(uid, last_dcase=today())
    card = D.roll_card()
    add_card(uid, card["name"])
    await reveal(m, card, f"📦 <b>Ежедневный кейс</b>\n🎴 {esc(card['name'])}\n{card['rarity']} | 💰 {fmt(card['price'])}")


@fx.message(Command("dcard"))
async def cmd_dcard(m: Message):
    uid = ensure(m)
    if ext(uid)["last_dcard"] == today():
        return await m.answer("🎴 Карта дня уже получена.")
    pool = sorted([c for c in D.cards if c["rarity"] in D.RARITY_CHANCES], key=lambda c: c["name"])
    card = pool[date.today().toordinal() % len(pool)]
    ext_set(uid, last_dcard=today())
    add_card(uid, card["name"])
    await reveal(m, card, f"🎴 <b>Карта дня</b> (одна для всех)\n{esc(card['name'])}\n{card['rarity']} | 💰 {fmt(card['price'])}")


@fx.message(Command("quests"))
async def cmd_quests(m: Message):
    uid = ensure(m)
    day = today()
    lines = ["📜 <b>Ежедневные задания</b>\n"]
    for k in quests_for(uid, day):
        desc, target, reward = DAILY_Q[k]
        r = db.execute("SELECT progress, claimed FROM quest_progress WHERE uid=? AND day=? AND qkey=?", (uid, day, k)).fetchone()
        prog, cl = r if r else (0, 0)
        lines.append(f"{'✅' if cl else '⬜'} {desc} — {min(prog, target)}/{target} — {fmt(reward)} монет")
    lines.append("\n🎯 <b>Разнообразные квесты</b> (разовые) смотри в /ach → группа «Квесты».")
    await m.answer("\n".join(lines))


@fx.message(Command("tree"))
async def cmd_tree(m: Message):
    uid = ensure(m)
    await m.answer(*tree_view(uid))


def tree_view(uid):
    perks = json.loads(ext(uid)["perks"] or "{}")
    free = xp_level(ext(uid)["xp"]) - 1 - sum(perks.values())
    lines = [f"🌳 <b>Дерево прокачки</b>\nСвободных очков: {free} (1 за каждый уровень опыта)\n"]
    rows = []
    for k, (title, mx, desc) in PERKS.items():
        lv = perks.get(k, 0)
        lines.append(f"{title} {lv}/{mx} — {desc}")
        rows.append([(f"⬆️ {title} ({lv}/{mx})", f"fx_tree:{uid}:{k}")])
    return "\n".join(lines), KB(*rows)


@fx.callback_query(F.data.startswith("fx_tree:"))
async def cb_tree(call: CallbackQuery):
    _, u, k = call.data.split(":")
    uid = int(u)
    if call.from_user.id != uid or k not in PERKS:
        return await call.answer("Не твоё!", show_alert=True)
    perks = json.loads(ext(uid)["perks"] or "{}")
    free = xp_level(ext(uid)["xp"]) - 1 - sum(perks.values())
    if free <= 0:
        return await call.answer("Нет свободных очков (качай опыт: игры, карты, дуэли).", show_alert=True)
    if perks.get(k, 0) >= PERKS[k][1]:
        return await call.answer("Максимальный уровень!", show_alert=True)
    perks[k] = perks.get(k, 0) + 1
    ext_set(uid, perks=json.dumps(perks))
    t, kb = tree_view(uid)
    await edit(call, t, kb)
    await call.answer("Улучшено!")


# ═════════════════════════ ИВЕНТЫ / СТАТИСТИКА / ТОПЫ ═════════════════════════
@fx.message(Command("seasons"))
async def cmd_seasons(m: Message):
    ev = active_event()
    await m.answer("🏰 <b>Сезонные ивенты</b>\n🎄 Новый год: 20 дек — 10 янв (×2)\n💘 Валентинки: 10–16 фев (×2)\n"
                   "☀️ Летний: 20 июн — 20 авг (×1.5)\n🎂 День рождения бота: ±3 дня от даты (×3)\n\n"
                   + (f"Сейчас идёт: {ev[1]}! Бонус к /daily ×{ev[2]} и подарок: /seasongift" if ev else "Сейчас ивента нет."))


@fx.message(Command("seasongift"))
async def cmd_seasongift(m: Message):
    uid = ensure(m)
    ev = active_event()
    if not ev:
        return await m.answer("Сейчас нет ивента. /seasons")
    key = f"ev_{ev[0]}_{date.today().year}"
    if db.execute("SELECT 1 FROM achievements WHERE uid=? AND akey=?", (uid, key)).fetchone():
        return await m.answer("🎁 Подарок этого ивента уже получен.")
    db.execute("INSERT INTO achievements VALUES(?,?)", (uid, key))
    db.commit()
    card = D.roll_card()
    add_card(uid, card["name"])
    add_coins(uid, 25000)
    db.execute("UPDATE users SET tokens=tokens+5 WHERE user_id=?", (uid,))
    db.commit()
    await reveal(m, card, f"{ev[1]} — подарок!\n🎴 {esc(card['name'])} ({card['rarity']})\n💰 +25 000 монет, ☢️ +5")


@fx.message(Command("stats"))
async def cmd_stats(m: Message):
    ensure(m)
    users = db.execute("SELECT COUNT(*), COALESCE(SUM(balance),0), COALESCE(AVG(balance),0) FROM users").fetchone()
    cards_n = db.execute("SELECT COUNT(*) FROM inventory").fetchone()[0]
    act = db.execute("SELECT COUNT(*) FROM activity WHERE day=?", (today(),)).fetchone()[0]
    duels = db.execute("SELECT COALESCE(SUM(duel_wins),0) FROM profile_ext").fetchone()[0]
    await m.answer(f"📈 <b>Статистика бота</b>\n👥 Игроков: {users[0]}\n🔥 Активны сегодня: {act}\n🎴 Карт у игроков: {fmt(cards_n)}\n"
                   f"💰 Монет в обороте: {fmt(users[1])}\n📊 Средний баланс: {fmt(users[2])}\n⚔️ Дуэльных побед: {duels}")


@fx.message(Command("toplist"))
async def cmd_toplist(m: Message, command: CommandObject):
    ensure(m)
    k = (command.args or "coins").strip().lower()
    q = {
        "coins": ("💰 Топ по монетам", "SELECT username, balance FROM users ORDER BY balance DESC LIMIT 10"),
        "cards": ("🎴 Топ по картам", "SELECT u.username, COUNT(i.card_name) c FROM users u JOIN inventory i ON i.user_id=u.user_id GROUP BY u.user_id ORDER BY c DESC LIMIT 10"),
        "duels": ("⚔️ Топ по дуэлям", "SELECT u.username, p.duel_wins FROM profile_ext p JOIN users u ON u.user_id=p.user_id ORDER BY p.duel_wins DESC LIMIT 10"),
        "rep": ("👍 Топ по репутации", "SELECT u.username, p.rep FROM profile_ext p JOIN users u ON u.user_id=p.user_id ORDER BY p.rep DESC LIMIT 10"),
        "xp": ("⭐ Топ по опыту", "SELECT u.username, p.xp FROM profile_ext p JOIN users u ON u.user_id=p.user_id ORDER BY p.xp DESC LIMIT 10"),
    }.get(k)
    if not q:
        return await m.answer("Использование: /toplist cards|coins|duels|rep|xp")
    rows = db.execute(q[1]).fetchall()
    medals = ["🥇", "🥈", "🥉"] + ["▫️"] * 7
    await m.answer(f"<b>{q[0]}</b>\n\n" + "\n".join(f"{medals[i]} {('@' + esc(u)) if u else 'Игрок'} — {fmt(v)}" for i, (u, v) in enumerate(rows)))


@fx.message(Command("newhelp"))
async def cmd_newhelp(m: Message):
    await m.answer(HELP_TEXT)
