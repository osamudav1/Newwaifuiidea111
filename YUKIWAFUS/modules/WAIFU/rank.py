import html

from pyrogram import Client, enums, filters
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

import config
from YUKIWAFUS import app
from YUKIWAFUS.database.Mangodb import (
    balancedb,
    collectiondb,
    chatsdb,
    game_statsdb,
)
from YUKIWAFUS.utils.helpers import sc

TOP_LIMIT = 10
MEDALS    = ["🥇", "🥈", "🥉"]

# Tab constants
TAB_WAIFUS   = "waifus"
TAB_COINS    = "coins"
TAB_GUESSERS = "guessers"
TAB_GROUPS   = "groups"


def _medal(i: int) -> str:
    return MEDALS[i] if i < 3 else f"<b>{i + 1}.</b>"


# ══════════════════════════════════════════════════════════════════════════════
# ✅ DATA FETCHERS
# ══════════════════════════════════════════════════════════════════════════════

async def _fetch_waifus() -> str:
    pipeline = [
        {
            "$project": {
                "user_id":    1,
                "first_name": 1,
                "waifu_count": {"$size": {"$ifNull": ["$waifus", []]}},
            }
        },
        {"$sort":  {"waifu_count": -1}},
        {"$limit": TOP_LIMIT},
    ]
    data = await collectiondb.aggregate(pipeline).to_list(TOP_LIMIT)

    text = (
        f"<blockquote>"
        f"<emoji id='6291837599254322363'>🌸</emoji> "
        f"<b>{sc('Top Waifu Collectors')}</b>"
        f"</blockquote>\n\n"
    )

    if not data:
        return text + f"<i>{sc('No data yet')}~</i>"

    for i, doc in enumerate(data):
        uid   = doc.get("user_id", 0)
        name  = html.escape(doc.get("first_name", str(uid)))[:18]
        count = doc.get("waifu_count", 0)
        text += f"{_medal(i)} <a href='tg://user?id={uid}'><b>{name}</b></a> — {count} 🌸\n"

    return text


async def _fetch_coins() -> str:
    data = await balancedb.find(
        {}, {"user_id": 1, "coins": 1}
    ).sort("coins", -1).limit(TOP_LIMIT).to_list(TOP_LIMIT)

    text = (
        f"<blockquote>"
        f"🪙 "
        f"<b>{sc('Top Sakura Holders')}</b>"
        f"</blockquote>\n\n"
    )

    if not data:
        return text + f"<i>{sc('No data yet')}~</i>"

    for i, doc in enumerate(data):
        uid   = doc.get("user_id", 0)
        coins = doc.get("coins", 0)
        # Try to get name from collectiondb (has first_name cached)
        col_doc = await collectiondb.find_one(
            {"user_id": uid}, {"first_name": 1}
        )
        name = html.escape(
            col_doc.get("first_name", str(uid)) if col_doc else str(uid)
        )[:18]
        text += f"{_medal(i)} <a href='tg://user?id={uid}'><b>{name}</b></a> — {coins:,} 🪙\n"

    return text


async def _fetch_guessers() -> str:
    data = await game_statsdb.find(
        {}, {"user_id": 1, "total_guesses": 1}
    ).sort("total_guesses", -1).limit(TOP_LIMIT).to_list(TOP_LIMIT)

    text = (
        f"<blockquote>"
        f"🎯 "
        f"<b>{sc('Top Guessers')}</b>"
        f"</blockquote>\n\n"
    )

    if not data:
        return text + f"<i>{sc('No data yet')}~</i>"

    for i, doc in enumerate(data):
        uid     = doc.get("user_id", 0)
        guesses = doc.get("total_guesses", 0)
        col_doc = await collectiondb.find_one(
            {"user_id": uid}, {"first_name": 1}
        )
        name = html.escape(
            col_doc.get("first_name", str(uid)) if col_doc else str(uid)
        )[:18]
        text += f"{_medal(i)} <a href='tg://user?id={uid}'><b>{name}</b></a> — {guesses} 🎯\n"

    return text


async def _fetch_groups() -> str:
    data = await chatsdb.find(
        {"guess_count": {"$exists": True, "$gt": 0}},
        {"chat_id": 1, "title": 1, "guess_count": 1},
    ).sort("guess_count", -1).limit(TOP_LIMIT).to_list(TOP_LIMIT)

    text = (
        f"<blockquote>"
        f"🏘 "
        f"<b>{sc('Top Groups')}</b>"
        f"</blockquote>\n\n"
    )

    if not data:
        return text + f"<i>{sc('Groups ranked after first correct guess')}~</i>"

    for i, doc in enumerate(data):
        name  = html.escape(doc.get("title", "Group"))[:20]
        count = doc.get("guess_count", 0)
        text += f"{_medal(i)} <b>{name}</b> — {count} 🎯\n"

    return text


# ══════════════════════════════════════════════════════════════════════════════
# ✅ KEYBOARD BUILDER
# ══════════════════════════════════════════════════════════════════════════════

def _build_keyboard(active: str) -> InlineKeyboardMarkup:
    def _btn(label: str, tab: str) -> InlineKeyboardButton:
        prefix = "• " if tab == active else ""
        return InlineKeyboardButton(
            f"{prefix}{label}", callback_data=f"rank:{tab}"
        )

    return InlineKeyboardMarkup([
        [
            _btn("🌸 Waifus",   TAB_WAIFUS),
            _btn("🪙 Coins",    TAB_COINS),
        ],
        [
            _btn("🎯 Guessers", TAB_GUESSERS),
            _btn("🏘 Groups",   TAB_GROUPS),
        ],
    ])


# ══════════════════════════════════════════════════════════════════════════════
# ✅ TAB FETCHER MAP
# ══════════════════════════════════════════════════════════════════════════════

_TAB_FETCH = {
    TAB_WAIFUS:   _fetch_waifus,
    TAB_COINS:    _fetch_coins,
    TAB_GUESSERS: _fetch_guessers,
    TAB_GROUPS:   _fetch_groups,
}


# ══════════════════════════════════════════════════════════════════════════════
# ✅ /rank COMMAND
# ══════════════════════════════════════════════════════════════════════════════

@app.on_message(filters.command(["rank", "leaderboard", "top", "lb"]))
async def rank_cmd(client: Client, message: Message):
    loading = await message.reply_text(
        f"<blockquote>⏳ <b>{sc('Loading leaderboard')}...</b></blockquote>",
        parse_mode=enums.ParseMode.HTML,
    )

    text     = await _fetch_waifus()
    keyboard = _build_keyboard(TAB_WAIFUS)

    await loading.delete()

    await message.reply_photo(
        photo        = config.WAIFU_PICS[0],
        caption      = text,
        parse_mode   = enums.ParseMode.HTML,
        reply_markup = keyboard,
        has_spoiler  = True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# ✅ TAB SWITCH CALLBACK
# ══════════════════════════════════════════════════════════════════════════════

@app.on_callback_query(filters.regex(r"^rank:(\w+)$"))
async def rank_tab_cb(client: Client, cq: CallbackQuery):
    tab = cq.data.split(":")[1]

    fetch = _TAB_FETCH.get(tab)
    if not fetch:
        return await cq.answer()

    # Show loading indicator
    await cq.answer(f"⏳ {sc('Loading')}...")

    text     = await fetch()
    keyboard = _build_keyboard(tab)

    try:
        await cq.message.edit_caption(
            text,
            parse_mode   = enums.ParseMode.HTML,
            reply_markup = keyboard,
        )
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# ✅ /ctop — GROUP TOP (in-chat leaderboard)
# ══════════════════════════════════════════════════════════════════════════════

@app.on_message(filters.command("ctop") & filters.group)
async def ctop_cmd(client: Client, message: Message):
    chat_id = message.chat.id

    pipeline = [
        {"$match": {"chat_id": chat_id}},
        {"$unwind": "$user_guesses"},
        {
            "$group": {
                "_id":       "$user_guesses.user_id",
                "count":     {"$sum": "$user_guesses.count"},
                "first_name": {"$first": "$user_guesses.first_name"},
            }
        },
        {"$sort":  {"count": -1}},
        {"$limit": TOP_LIMIT},
    ]

    # Fallback: use game_statsdb (global guesses, not per-group)
    # For per-group tracking, guess.py needs to write to chatsdb user_guesses
    # For now use game_statsdb as approximation
    data = await game_statsdb.find(
        {}, {"user_id": 1, "total_guesses": 1}
    ).sort("total_guesses", -1).limit(TOP_LIMIT).to_list(TOP_LIMIT)

    text = (
        f"<blockquote>"
        f"🎯 <b>{sc('Group Top Guessers')}</b>\n"
        f"<b>{html.escape(message.chat.title or '')}</b>"
        f"</blockquote>\n\n"
    )

    if not data:
        text += f"<i>{sc('No guesses yet in this group')}~</i>"
    else:
        for i, doc in enumerate(data):
            uid     = doc.get("user_id", 0)
            guesses = doc.get("total_guesses", 0)
            col_doc = await collectiondb.find_one({"user_id": uid}, {"first_name": 1})
            name    = html.escape(
                col_doc.get("first_name", str(uid)) if col_doc else str(uid)
            )[:18]
            text += f"{_medal(i)} <a href='tg://user?id={uid}'><b>{name}</b></a> — {guesses} 🎯\n"

    await message.reply_photo(
        photo       = config.WAIFU_PICS[0],
        caption     = text,
        parse_mode  = enums.ParseMode.HTML,
        has_spoiler = True,
  )
  
