import asyncio
import math
import random
from datetime import datetime, timedelta
from html import escape
from itertools import groupby

from pyrogram import Client, enums, filters
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Message,
)

from YUKIWAFUS import app
from YUKIWAFUS.database.Mangodb import collectiondb
from YUKIWAFUS.utils.api import find_waifu, get_random_waifu

# ── Rarity Map ────────────────────────────────────────────────────────────────
RARITY_EMOJI = {
    "Common":    "⚪",
    "Uncommon":  "🟢",
    "Rare":      "🔵",
    "Epic":      "🟣",
    "Legendary": "🟡",
    "Mythic":    "🔴",
}

ITEMS_PER_PAGE = 15
AUTO_DELETE = 180  # 3 minutes


# ── DB Helpers ────────────────────────────────────────────────────────────────
async def get_user_collection(user_id: int) -> list:
    user = await collectiondb.find_one({"user_id": user_id})
    if not user or "waifus" not in user:
        return []
    return user["waifus"]


async def get_user_filter(user_id: int) -> str | None:
    user = await collectiondb.find_one({"user_id": user_id})
    return user.get("filter_rarity") if user else None


async def set_user_filter(user_id: int, rarity: str | None):
    await collectiondb.update_one(
        {"user_id": user_id},
        {"$set": {"filter_rarity": rarity}},
        upsert=True,
    )


# ── Harem Display ─────────────────────────────────────────────────────────────
async def build_harem_text(
    name: str,
    waifus: list,
    page: int,
    filter_rarity: str | None,
) -> tuple[str, int]:
    """Returns (message_text, total_pages)"""

    if filter_rarity:
        waifus = [w for w in waifus if w.get("rarity") == filter_rarity]

    # Sort by rarity then name
    waifus = sorted(waifus, key=lambda x: (x.get("rarity", ""), x.get("name", "")))

    # Deduplicate + count
    counts = {}
    unique = {}
    for w in waifus:
        wid = w.get("waifu_id", w.get("name"))
        counts[wid] = counts.get(wid, 0) + 1
        unique[wid] = w

    unique_list = list(unique.values())
    total_pages = max(1, math.ceil(len(unique_list) / ITEMS_PER_PAGE))
    page = max(0, min(page, total_pages - 1))

    current = unique_list[page * ITEMS_PER_PAGE: (page + 1) * ITEMS_PER_PAGE]

    text = f"<b>🌸 {escape(name)}'s Harem — Page {page + 1}/{total_pages}</b>\n"
    if filter_rarity:
        text += f"<b>Filter: {RARITY_EMOJI.get(filter_rarity, '')} {filter_rarity}</b>\n"
    text += "\n"

    # Group by rarity
    grouped = {}
    for w in current:
        r = w.get("rarity", "Common")
        grouped.setdefault(r, []).append(w)

    for rarity, chars in grouped.items():
        emoji = RARITY_EMOJI.get(rarity, "◈")
        text += f"<b>{emoji} {rarity}</b>\n"
        for w in chars:
            wid = w.get("waifu_id", w.get("name"))
            count = counts.get(wid, 1)
            marker = " [🎞️]" if (w.get("video") or w.get("video_id") or w.get("video_url") or w.get("animation")) else ""
            text += f"  ◈ {w['name']}{marker} ×{count}\n"
        text += "\n"

    return text, total_pages


def build_harem_keyboard(
    page: int,
    total_pages: int,
    user_id: int,
    filter_rarity: str | None,
) -> InlineKeyboardMarkup:
    fr = filter_rarity or "None"
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"harem:{page-1}:{user_id}:{fr}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"harem:{page+1}:{user_id}:{fr}"))

    keyboard = [
        [
            InlineKeyboardButton("🔍 Search", switch_inline_query_current_chat=f"col.{user_id}"),
            InlineKeyboardButton("🎨 Filter", callback_data=f"hmode:{user_id}"),
        ]
    ]
    if nav:
        keyboard.append(nav)

    return InlineKeyboardMarkup(keyboard)


async def get_display_waifu(user_id: int, waifus: list) -> dict | None:
    """Pick fav waifu for display, else random."""
    user = await collectiondb.find_one({"user_id": user_id})
    if user and user.get("favourites"):
        fav_id = user["favourites"][0]
        fav = next((w for w in waifus if w.get("waifu_id") == fav_id), None)
        if fav:
            return fav
    return random.choice(waifus) if waifus else None


# ── /harem Command ────────────────────────────────────────────────────────────
@app.on_message(filters.command(["harem", "collection"]))
async def harem_handler(client: Client, message: Message):
    user_id = message.from_user.id

    # Check if viewing someone else's harem
    if message.reply_to_message:
        target = message.reply_to_message.from_user
        user_id = target.id
        name = target.first_name
    else:
        name = message.from_user.first_name

    waifus = await get_user_collection(user_id)
    if not waifus:
        return await message.reply_text(
            f"<b>{escape(name)}</b> has no waifus yet! 😢\nUse /hclaim to get your first one.",
            parse_mode=enums.ParseMode.HTML,
        )

    filter_rarity = await get_user_filter(user_id)
    text, total_pages = await build_harem_text(name, waifus, 0, filter_rarity)
    keyboard = build_harem_keyboard(0, total_pages, user_id, filter_rarity)
    display = await get_display_waifu(user_id, waifus)

    if display and display.get("img_url"):
        msg = await message.reply_photo(
            photo=display["img_url"],
            caption=text,
            reply_markup=keyboard,
            parse_mode=enums.ParseMode.HTML,
        )
    else:
        msg = await message.reply_text(
            text,
            reply_markup=keyboard,
            parse_mode=enums.ParseMode.HTML,
        )

    await asyncio.sleep(AUTO_DELETE)
    try:
        await msg.delete()
    except Exception:
        pass


# ── Harem Pagination Callback ─────────────────────────────────────────────────
@app.on_callback_query(filters.regex(r"^harem:"))
async def harem_callback(client: Client, cq: CallbackQuery):
    _, page, user_id, fr = cq.data.split(":")
    page = int(page)
    user_id = int(user_id)
    filter_rarity = None if fr == "None" else fr

    if cq.from_user.id != user_id:
        return await cq.answer("This is not your harem! 😤", show_alert=True)

    user = await client.get_users(user_id)
    name = user.first_name

    waifus = await get_user_collection(user_id)
    if not waifus:
        return await cq.answer("No waifus found!", show_alert=True)

    text, total_pages = await build_harem_text(name, waifus, page, filter_rarity)
    keyboard = build_harem_keyboard(page, total_pages, user_id, filter_rarity)
    display = await get_display_waifu(user_id, waifus)

    try:
        if display and display.get("img_url"):
            await cq.message.edit_media(
                media=InputMediaPhoto(display["img_url"], caption=text, parse_mode=enums.ParseMode.HTML),
                reply_markup=keyboard,
            )
        else:
            await cq.message.edit_text(text, reply_markup=keyboard, parse_mode=enums.ParseMode.HTML)
    except Exception:
        pass

    await cq.answer()


# ── /hmode Filter ─────────────────────────────────────────────────────────────
@app.on_message(filters.command("hmode"))
async def hmode_handler(client: Client, message: Message):
    user_id = message.from_user.id
    keyboard = []
    row = []

    for i, (rarity, emoji) in enumerate(RARITY_EMOJI.items(), 1):
        row.append(InlineKeyboardButton(f"{emoji} {rarity}", callback_data=f"set_rarity:{user_id}:{rarity}"))
        if i % 2 == 0:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("🌸 Show All", callback_data=f"set_rarity:{user_id}:None")])

    await message.reply_text(
        "🎨 <b>Select rarity to filter your harem:</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=enums.ParseMode.HTML,
    )


@app.on_callback_query(filters.regex(r"^hmode:"))
async def hmode_callback(client: Client, cq: CallbackQuery):
    user_id = int(cq.data.split(":")[1])
    if cq.from_user.id != user_id:
        return await cq.answer("Not your harem!", show_alert=True)

    keyboard = []
    row = []
    for i, (rarity, emoji) in enumerate(RARITY_EMOJI.items(), 1):
        row.append(InlineKeyboardButton(f"{emoji} {rarity}", callback_data=f"set_rarity:{user_id}:{rarity}"))
        if i % 2 == 0:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🌸 Show All", callback_data=f"set_rarity:{user_id}:None")])

    await cq.message.edit_text(
        "🎨 <b>Select rarity to filter your harem:</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=enums.ParseMode.HTML,
    )
    await cq.answer()


@app.on_callback_query(filters.regex(r"^set_rarity:"))
async def set_rarity_callback(client: Client, cq: CallbackQuery):
    _, user_id, rarity = cq.data.split(":")
    user_id = int(user_id)
    filter_rarity = None if rarity == "None" else rarity

    if cq.from_user.id != user_id:
        return await cq.answer("Not your harem!", show_alert=True)

    await set_user_filter(user_id, filter_rarity)

    label = f"{RARITY_EMOJI.get(filter_rarity, '')} {filter_rarity}" if filter_rarity else "All Rarities"
    await cq.message.edit_text(f"✅ Filter set to: <b>{label}</b>", parse_mode=enums.ParseMode.HTML)
    await cq.answer(f"Filter → {label}", show_alert=False)
