import asyncio
import uuid
from datetime import datetime
from html import escape

from pyrogram import Client, enums, filters
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

import config
from YUKIWAFUS import app
from YUKIWAFUS.database.Mangodb import collectiondb, tradedb
from YUKIWAFUS.utils.helpers import sc

TRADE_TIMEOUT = 600   # 10 minutes

RARITY_EMOJI = {
    "Common":    "⚪",
    "Uncommon":  "🟢",
    "Rare":      "🔵",
    "Epic":      "🟣",
    "Legendary": "🟡",
    "Mythic":    "🔴",
}

# ── Spam lock ─────────────────────────────────────────────────────────────────
trade_lock: set = set()


# ── Helpers ───────────────────────────────────────────────────────────────────
def mention(user) -> str:
    return f"<a href='tg://user?id={user.id}'>{escape(user.first_name)}</a>"


def waifu_line(waifu: dict) -> str:
    rarity = waifu.get("rarity", "Common")
    emoji  = RARITY_EMOJI.get(rarity, "◈")
    return (
        f"📛 <b>{escape(waifu.get('name', 'Unknown'))}</b> "
        f"{emoji} <code>{rarity}</code>"
    )


async def get_waifu_from_collection(user_id: int, waifu_id: str) -> dict | None:
    user = await collectiondb.find_one({"user_id": user_id})
    if not user:
        return None
    for w in user.get("waifus", []):
        if str(w.get("waifu_id", "")) == waifu_id or str(w.get("_id", "")) == waifu_id:
            return w
    return None


async def remove_waifu_from_collection(user_id: int, waifu_id: str):
    await collectiondb.update_one(
        {"user_id": user_id},
        {"$pull": {"waifus": {"waifu_id": waifu_id}}},
    )


async def add_waifu_to_collection(user_id: int, username: str, first_name: str, waifu: dict):
    await collectiondb.update_one(
        {"user_id": user_id},
        {
            "$set":  {"username": username or "", "first_name": first_name},
            "$push": {"waifus": waifu},
        },
        upsert=True,
    )


def _trade_caption(
    trade_id: str,
    user_a, waifu_a: dict,
    user_b, waifu_b: dict,
    confirmed_a: bool,
    confirmed_b: bool,
) -> str:
    tick_a = "✅" if confirmed_a else "⏳"
    tick_b = "✅" if confirmed_b else "⏳"
    return (
        f"<blockquote>"
        f"<emoji id='5262770659267735289'>🔀</emoji> "
        f"<b>{sc('Trade Request')}!</b>\n"
        f"<code>{sc('ID')}: {trade_id[:8]}</code>"
        f"</blockquote>\n\n"
        f"{tick_a} <b>{mention(user_a)}</b> {sc('offers')}:\n"
        f"  {waifu_line(waifu_a)}\n\n"
        f"{tick_b} <b>{mention(user_b)}</b> {sc('offers')}:\n"
        f"  {waifu_line(waifu_b)}\n\n"
        f"<i>⏳ {sc('Both must confirm within 10 minutes')}~</i>"
    )


# ── /trade <my_waifu_id> <their_waifu_id> reply ───────────────────────────────
@app.on_message(filters.command("trade"))
async def trade_cmd(client: Client, message: Message):
    user_a = message.from_user

    if not message.reply_to_message or not message.reply_to_message.from_user:
        return await message.reply_text(
            f"<blockquote>"
            f"<emoji id='6001602353843672777'>⚠️</emoji> "
            f"<b>{sc('Reply to a user to trade with them')}.</b>"
            f"</blockquote>\n\n"
            f"<b>{sc('Usage')} :</b> <code>/trade &lt;your_waifu_id&gt; &lt;their_waifu_id&gt;</code>",
            parse_mode=enums.ParseMode.HTML,
        )

    user_b = message.reply_to_message.from_user

    if user_b.id == user_a.id:
        return await message.reply_text(
            f"<blockquote>"
            f"<emoji id='5998834801472182366'>❌</emoji> "
            f"<b>{sc('Cannot trade with yourself')}.</b>"
            f"</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    if user_b.is_bot:
        return await message.reply_text(
            f"<blockquote>"
            f"<emoji id='5998834801472182366'>❌</emoji> "
            f"<b>{sc('Cannot trade with bots')}.</b>"
            f"</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    if len(message.command) < 3:
        return await message.reply_text(
            f"<blockquote>"
            f"<emoji id='6001602353843672777'>⚠️</emoji> "
            f"<b>{sc('Provide both waifu IDs')}.</b>"
            f"</blockquote>\n\n"
            f"<b>{sc('Usage')} :</b> <code>/trade &lt;your_id&gt; &lt;their_id&gt;</code>",
            parse_mode=enums.ParseMode.HTML,
        )

    waifu_id_a = message.command[1].strip()
    waifu_id_b = message.command[2].strip()

    if user_a.id in trade_lock:
        return await message.reply_text(
            f"<blockquote>⏳ <b>{sc('You already have a pending trade')}.</b></blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    if user_b.id in trade_lock:
        return await message.reply_text(
            f"<blockquote>⏳ <b>{sc('That user already has a pending trade')}.</b></blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    # Validate both waifus
    waifu_a = await get_waifu_from_collection(user_a.id, waifu_id_a)
    if not waifu_a:
        return await message.reply_text(
            f"<blockquote>"
            f"<emoji id='5998834801472182366'>❌</emoji> "
            f"<b>{sc('Your waifu ID not found in your collection')}.</b>"
            f"</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    waifu_b = await get_waifu_from_collection(user_b.id, waifu_id_b)
    if not waifu_b:
        return await message.reply_text(
            f"<blockquote>"
            f"<emoji id='5998834801472182366'>❌</emoji> "
            f"<b>{sc('Their waifu ID not found in their collection')}.</b>"
            f"</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    # Create trade
    trade_id = str(uuid.uuid4())

    await tradedb.insert_one({
        "trade_id":    trade_id,
        "user_a_id":   user_a.id,
        "user_b_id":   user_b.id,
        "waifu_id_a":  waifu_id_a,
        "waifu_id_b":  waifu_id_b,
        "waifu_a":     waifu_a,
        "waifu_b":     waifu_b,
        "confirmed_a": False,
        "confirmed_b": False,
        "created_at":  datetime.utcnow(),
    })

    trade_lock.add(user_a.id)
    trade_lock.add(user_b.id)

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            f"✅ {sc('Confirm')}",
            callback_data=f"trade_confirm:{trade_id}",
        ),
        InlineKeyboardButton(
            f"❌ {sc('Cancel')}",
            callback_data=f"trade_cancel:{trade_id}",
        ),
    ]])

    sent = await message.reply_photo(
        photo=waifu_a.get("img_url", config.WAIFU_PICS[0]),
        caption=_trade_caption(trade_id, user_a, waifu_a, user_b, waifu_b, False, False),
        parse_mode=enums.ParseMode.HTML,
        reply_markup=keyboard,
        has_spoiler=True,
    )

    # Auto cancel after 10 min
    asyncio.create_task(_auto_cancel_trade(trade_id, sent))


async def _auto_cancel_trade(trade_id: str, sent_msg):
    await asyncio.sleep(TRADE_TIMEOUT)

    doc = await tradedb.find_one({"trade_id": trade_id})
    if not doc:
        return

    trade_lock.discard(doc["user_a_id"])
    trade_lock.discard(doc["user_b_id"])
    await tradedb.delete_one({"trade_id": trade_id})

    try:
        await sent_msg.edit_caption(
            f"<blockquote>"
            f"<emoji id='5998834801472182366'>❌</emoji> "
            f"<b>{sc('Trade expired — auto cancelled after 10 minutes')}.</b>"
            f"</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )
    except Exception:
        pass


# ── Confirm callback ──────────────────────────────────────────────────────────
@app.on_callback_query(filters.regex(r"^trade_confirm:"))
async def trade_confirm_cb(client: Client, cq: CallbackQuery):
    trade_id = cq.data.split(":", 1)[1]
    user_id  = cq.from_user.id

    doc = await tradedb.find_one({"trade_id": trade_id})
    if not doc:
        return await cq.answer(sc("Trade expired or not found!"), show_alert=True)

    # Check if user is part of this trade
    if user_id not in (doc["user_a_id"], doc["user_b_id"]):
        return await cq.answer(sc("This trade is not for you!"), show_alert=True)

    is_a = user_id == doc["user_a_id"]

    # Already confirmed?
    if is_a and doc["confirmed_a"]:
        return await cq.answer(sc("You already confirmed!"), show_alert=True)
    if not is_a and doc["confirmed_b"]:
        return await cq.answer(sc("You already confirmed!"), show_alert=True)

    # Mark confirmed
    update_field = "confirmed_a" if is_a else "confirmed_b"
    await tradedb.update_one(
        {"trade_id": trade_id},
        {"$set": {update_field: True}},
    )
    doc[update_field] = True

    await cq.answer(sc("Confirmed! Waiting for other user..."), show_alert=False)

    # Fetch both users for caption update
    try:
        user_a = await client.get_users(doc["user_a_id"])
        user_b = await client.get_users(doc["user_b_id"])
    except Exception:
        return

    # Update caption with tick
    try:
        await cq.edit_message_caption(
            caption=_trade_caption(
                trade_id,
                user_a, doc["waifu_a"],
                user_b, doc["waifu_b"],
                doc["confirmed_a"],
                doc["confirmed_b"],
            ),
            parse_mode=enums.ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(f"✅ {sc('Confirm')}", callback_data=f"trade_confirm:{trade_id}"),
                InlineKeyboardButton(f"❌ {sc('Cancel')}",  callback_data=f"trade_cancel:{trade_id}"),
            ]]),
        )
    except Exception:
        pass

    # Both confirmed → execute trade
    if doc["confirmed_a"] and doc["confirmed_b"]:
        await _execute_trade(client, cq, doc, user_a, user_b)


async def _execute_trade(client, cq, doc, user_a, user_b):
    trade_id = doc["trade_id"]

    # Swap waifus
    await remove_waifu_from_collection(doc["user_a_id"], doc["waifu_id_a"])
    await remove_waifu_from_collection(doc["user_b_id"], doc["waifu_id_b"])

    await add_waifu_to_collection(
        doc["user_b_id"],
        user_b.username or "",
        user_b.first_name,
        doc["waifu_a"],
    )
    await add_waifu_to_collection(
        doc["user_a_id"],
        user_a.username or "",
        user_a.first_name,
        doc["waifu_b"],
    )

    # Clean up
    await tradedb.delete_one({"trade_id": trade_id})
    trade_lock.discard(doc["user_a_id"])
    trade_lock.discard(doc["user_b_id"])

    try:
        await cq.edit_message_caption(
            f"<blockquote>"
            f"<emoji id='6001483331709966655'>✅</emoji> "
            f"<b>{sc('Trade Completed')}!</b>"
            f"</blockquote>\n\n"
            f"<b>{mention(user_a)}</b> {sc('got')} → {waifu_line(doc['waifu_b'])}\n"
            f"<b>{mention(user_b)}</b> {sc('got')} → {waifu_line(doc['waifu_a'])}\n\n"
            f"<i>{sc('Check your harem with')} /harem~</i>",
            parse_mode=enums.ParseMode.HTML,
        )
    except Exception:
        pass


def waifu_line(waifu: dict) -> str:
    rarity = waifu.get("rarity", "Common")
    emoji  = RARITY_EMOJI.get(rarity, "◈")
    return (
        f"📛 <b>{escape(waifu.get('name', 'Unknown'))}</b> "
        f"{emoji} <code>{rarity}</code>"
    )


# ── Cancel callback ───────────────────────────────────────────────────────────
@app.on_callback_query(filters.regex(r"^trade_cancel:"))
async def trade_cancel_cb(client: Client, cq: CallbackQuery):
    trade_id = cq.data.split(":", 1)[1]
    user_id  = cq.from_user.id

    doc = await tradedb.find_one({"trade_id": trade_id})
    if not doc:
        return await cq.answer(sc("Trade already expired!"), show_alert=True)

    if user_id not in (doc["user_a_id"], doc["user_b_id"]):
        return await cq.answer(sc("This trade is not for you!"), show_alert=True)

    await tradedb.delete_one({"trade_id": trade_id})
    trade_lock.discard(doc["user_a_id"])
    trade_lock.discard(doc["user_b_id"])

    try:
        await cq.edit_message_caption(
            f"<blockquote>"
            f"<emoji id='5998834801472182366'>❌</emoji> "
            f"<b>{sc('Trade cancelled by')} {mention(cq.from_user)}.</b>"
            f"</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )
    except Exception:
        pass

    await cq.answer(sc("Trade cancelled."), show_alert=False)
          
