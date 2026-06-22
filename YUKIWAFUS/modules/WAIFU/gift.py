import asyncio
from datetime import datetime, timedelta
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
from YUKIWAFUS.database.Mangodb import collectiondb, giftdb
from YUKIWAFUS.utils.helpers import sc

GIFT_TIMEOUT = 3600   # 1 hour auto-cancel

RARITY_EMOJI = {
    "Common":    "⚪",
    "Uncommon":  "🟢",
    "Rare":      "🔵",
    "Epic":      "🟣",
    "Legendary": "🟡",
    "Mythic":    "🔴",
}

# ── Spam lock ─────────────────────────────────────────────────────────────────
gift_lock: set = set()


# ── Helpers ───────────────────────────────────────────────────────────────────
def mention(user) -> str:
    return f"<a href='tg://user?id={user.id}'>{escape(user.first_name)}</a>"


async def get_waifu_from_collection(user_id: int, waifu_id: str) -> dict | None:
    user = await collectiondb.find_one({"user_id": user_id})
    if not user:
        return None
    for w in user.get("waifus", []):
        if str(w.get("_id", "")) == waifu_id or str(w.get("waifu_id", "")) == waifu_id:
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


# ── /gift <waifu_id> ──────────────────────────────────────────────────────────
@app.on_message(filters.command("gift"))
async def gift_cmd(client: Client, message: Message):
    sender = message.from_user

    if not message.reply_to_message or not message.reply_to_message.from_user:
        return await message.reply_text(
            f"<blockquote>"
            f"<emoji id='6001602353843672777'>⚠️</emoji> "
            f"<b>{sc('Reply to a user to gift them a waifu')}.</b>"
            f"</blockquote>\n\n"
            f"<b>{sc('Usage')} :</b> <code>/gift &lt;waifu_id&gt;</code>",
            parse_mode=enums.ParseMode.HTML,
        )

    receiver = message.reply_to_message.from_user

    if receiver.id == sender.id:
        return await message.reply_text(
            f"<blockquote>"
            f"<emoji id='5998834801472182366'>❌</emoji> "
            f"<b>{sc('You cannot gift yourself')}.</b>"
            f"</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    if receiver.is_bot:
        return await message.reply_text(
            f"<blockquote>"
            f"<emoji id='5998834801472182366'>❌</emoji> "
            f"<b>{sc('You cannot gift bots')}.</b>"
            f"</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    if len(message.command) < 2:
        return await message.reply_text(
            f"<blockquote>"
            f"<emoji id='6001602353843672777'>⚠️</emoji> "
            f"<b>{sc('Provide a waifu ID')}.</b>"
            f"</blockquote>\n\n"
            f"<b>{sc('Usage')} :</b> <code>/gift &lt;waifu_id&gt;</code>",
            parse_mode=enums.ParseMode.HTML,
        )

    waifu_id = message.command[1].strip()

    if sender.id in gift_lock:
        return await message.reply_text(
            f"<blockquote>⏳ <b>{sc('A gift is already pending from you')}.</b></blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    # Check waifu exists in sender's collection
    waifu = await get_waifu_from_collection(sender.id, waifu_id)
    if not waifu:
        return await message.reply_text(
            f"<blockquote>"
            f"<emoji id='5998834801472182366'>❌</emoji> "
            f"<b>{sc('Waifu not found in your collection')}.</b>"
            f"</blockquote>\n\n"
            f"<i>{sc('Check your harem with')} /harem~</i>",
            parse_mode=enums.ParseMode.HTML,
        )

    rarity = waifu.get("rarity", "Common")
    emoji  = RARITY_EMOJI.get(rarity, "◈")

    # Save pending gift in DB
    await giftdb.update_one(
        {"sender_id": sender.id},
        {
            "$set": {
                "sender_id":   sender.id,
                "receiver_id": receiver.id,
                "waifu_id":    waifu_id,
                "waifu":       waifu,
                "created_at":  datetime.utcnow(),
            }
        },
        upsert=True,
    )

    gift_lock.add(sender.id)

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f"✅ {sc('Confirm Gift')}",
                callback_data=f"gift_confirm:{sender.id}:{receiver.id}:{waifu_id}",
            ),
            InlineKeyboardButton(
                f"❌ {sc('Cancel')}",
                callback_data=f"gift_cancel:{sender.id}",
            ),
        ]
    ])

    sent = await message.reply_photo(
        photo=waifu.get("img_url", config.WAIFU_PICS[0]),
        caption=(
            f"<blockquote>"
            f"<emoji id='6294023338176028117'>🎁</emoji> "
            f"<b>{sc('Gift Confirmation')}!</b>"
            f"</blockquote>\n\n"
            f"<b>{sc('From')} :</b> {mention(sender)}\n"
            f"<b>{sc('To')} :</b>   {mention(receiver)}\n\n"
            f"📛 <b>{sc('Waifu')} :</b> {escape(waifu.get('name', 'Unknown'))}\n"
            f"{emoji} <b>{sc('Rarity')} :</b> {rarity}\n\n"
            f"<i>⏳ {sc('Auto-cancels in 1 hour')}~</i>"
        ),
        parse_mode=enums.ParseMode.HTML,
        reply_markup=keyboard,
        has_spoiler=True,
    )

    # Auto-cancel after 1 hour
    asyncio.create_task(_auto_cancel_gift(sender.id, sent))


async def _auto_cancel_gift(sender_id: int, sent_msg):
    await asyncio.sleep(GIFT_TIMEOUT)

    # Check if gift still pending
    doc = await giftdb.find_one({"sender_id": sender_id})
    if not doc:
        return  # Already completed

    await giftdb.delete_one({"sender_id": sender_id})
    gift_lock.discard(sender_id)

    try:
        await sent_msg.edit_caption(
            f"<blockquote>"
            f"<emoji id='5998834801472182366'>❌</emoji> "
            f"<b>{sc('Gift expired — auto cancelled after 1 hour')}.</b>"
            f"</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )
    except Exception:
        pass


# ── Confirm callback ──────────────────────────────────────────────────────────
@app.on_callback_query(filters.regex(r"^gift_confirm:"))
async def gift_confirm_cb(client: Client, cq: CallbackQuery):
    parts      = cq.data.split(":")
    sender_id  = int(parts[1])
    receiver_id = int(parts[2])
    waifu_id   = parts[3]

    # Only sender can confirm
    if cq.from_user.id != sender_id:
        return await cq.answer(sc("This is not your gift!"), show_alert=True)

    doc = await giftdb.find_one({"sender_id": sender_id})
    if not doc:
        return await cq.answer(sc("Gift expired or already sent!"), show_alert=True)

    waifu    = doc["waifu"]
    rarity   = waifu.get("rarity", "Common")
    emoji    = RARITY_EMOJI.get(rarity, "◈")

    try:
        receiver = await client.get_users(receiver_id)
    except Exception:
        return await cq.answer(sc("Could not find receiver!"), show_alert=True)

    try:
        sender = await client.get_users(sender_id)
    except Exception:
        sender = cq.from_user

    # Transfer waifu
    await remove_waifu_from_collection(sender_id, waifu_id)
    await add_waifu_to_collection(
        receiver_id,
        receiver.username or "",
        receiver.first_name,
        waifu,
    )

    # Clean up
    await giftdb.delete_one({"sender_id": sender_id})
    gift_lock.discard(sender_id)

    await cq.edit_message_caption(
        f"<blockquote>"
        f"<emoji id='6001483331709966655'>✅</emoji> "
        f"<b>{sc('Gift Sent Successfully')}!</b>"
        f"</blockquote>\n\n"
        f"<b>{sc('From')} :</b> {mention(sender)}\n"
        f"<b>{sc('To')} :</b>   {mention(receiver)}\n\n"
        f"📛 <b>{sc('Waifu')} :</b> {escape(waifu.get('name', 'Unknown'))}\n"
        f"{emoji} <b>{sc('Rarity')} :</b> {rarity}",
        parse_mode=enums.ParseMode.HTML,
    )
    await cq.answer(sc("Gift sent!"), show_alert=False)

    # Notify receiver in DM
    try:
        await client.send_message(
            receiver_id,
            f"<blockquote>"
            f"<emoji id='6294023338176028117'>🎁</emoji> "
            f"<b>{sc('You received a waifu gift')}!</b>"
            f"</blockquote>\n\n"
            f"<b>{sc('From')} :</b> {mention(sender)}\n"
            f"📛 <b>{sc('Waifu')} :</b> {escape(waifu.get('name', 'Unknown'))}\n"
            f"{emoji} <b>{sc('Rarity')} :</b> {rarity}\n\n"
            f"<i>{sc('Check your harem with')} /harem~</i>",
            parse_mode=enums.ParseMode.HTML,
        )
    except Exception:
        pass


# ── Cancel callback ───────────────────────────────────────────────────────────
@app.on_callback_query(filters.regex(r"^gift_cancel:"))
async def gift_cancel_cb(client: Client, cq: CallbackQuery):
    sender_id = int(cq.data.split(":")[1])

    if cq.from_user.id != sender_id:
        return await cq.answer(sc("This is not your gift!"), show_alert=True)

    await giftdb.delete_one({"sender_id": sender_id})
    gift_lock.discard(sender_id)

    await cq.edit_message_caption(
        f"<blockquote>"
        f"<emoji id='5998834801472182366'>❌</emoji> "
        f"<b>{sc('Gift cancelled')}.</b>"
        f"</blockquote>",
        parse_mode=enums.ParseMode.HTML,
    )
    await cq.answer(sc("Gift cancelled."), show_alert=False)
          
