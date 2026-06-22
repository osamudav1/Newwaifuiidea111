from datetime import datetime
from html import escape

from pyrogram import Client, enums, filters
from pyrogram.types import Message

import config
from YUKIWAFUS import app
from YUKIWAFUS.logging import LOGGER
from YUKIWAFUS.utils.api import add_waifu, find_waifu

log = LOGGER(__name__)

RARITY_EMOJI = {
    "Common":    "⚪",
    "Uncommon":  "🟢",
    "Rare":      "🔵",
    "Epic":      "🟣",
    "Legendary": "🟡",
    "Mythic":    "🔴",
}

VALID_RARITIES = list(RARITY_EMOJI.keys())


# ── Logger Caption ────────────────────────────────────────────────────────────
def build_log_caption(
    name: str,
    rarity: str,
    event_tag: str,
    img_url: str,
    added_by_name: str,
    added_by_id: int,
    source_msg_id: int = 0,
) -> str:
    emoji = RARITY_EMOJI.get(rarity, "◈")
    now = datetime.utcnow().strftime("%d %b %Y • %H:%M UTC")

    return (
        f"<blockquote>"
        f"🌸 <b>New Waifu Added!</b>"
        f"</blockquote>\n\n"
        f"📛 <b>Name:</b> {escape(name)}\n"
        f"{emoji} <b>Rarity:</b> {rarity}\n"
        f"🏷 <b>Tag:</b> {event_tag}\n"
        f"🖼 <b>Image:</b> <a href='{img_url}'>View</a>\n\n"
        f"<blockquote>"
        f"👤 <b>Added by:</b> <a href='tg://user?id={added_by_id}'>{escape(added_by_name)}</a>\n"
        f"🕐 <b>Time:</b> {now}"
        f"</blockquote>"
    )


# ── /addwaifu Command ─────────────────────────────────────────────────────────
@app.on_message(filters.command("addwaifu") & filters.user(config.SUDO_USERS + [config.OWNER_ID]))
async def addwaifu_handler(client: Client, message: Message):
    """
    Usage:
      /addwaifu <name> | <img_url> | <rarity> | [event_tag]
    Or reply to an image:
      /addwaifu <name> | <rarity> | [event_tag]
    """
    user = message.from_user
    args_raw = " ".join(message.command[1:]).strip()

    # ── Parse args ────────────────────────────────────────────────────────────
    parts = [p.strip() for p in args_raw.split("|")]

    img_url = None
    # If replied to image — get url from caption or photo
    if message.reply_to_message and message.reply_to_message.photo:
        if len(parts) < 2:
            return await message.reply_text(
                "Usage (reply to image):\n"
                "<code>/addwaifu Name | Rarity | [EventTag]</code>",
                parse_mode=enums.ParseMode.HTML,
            )
        name = parts[0]
        rarity = parts[1].capitalize()
        event_tag = parts[2] if len(parts) > 2 else "Standard"

        # Download photo and reupload — for now use file_id
        photo = message.reply_to_message.photo
        file = await client.download_media(photo.file_id, in_memory=True)
        # img_url stays None — handle separately if needed
        return await message.reply_text(
            "⚠️ Direct photo upload not yet supported.\nPlease provide a direct image URL instead.",
        )
    else:
        if len(parts) < 3:
            return await message.reply_text(
                "Usage:\n"
                "<code>/addwaifu Name | img_url | Rarity | [EventTag]</code>\n\n"
                "Rarities: Common, Uncommon, Rare, Epic, Legendary, Mythic",
                parse_mode=enums.ParseMode.HTML,
            )
        name = parts[0]
        img_url = parts[1]
        rarity = parts[2].capitalize()
        event_tag = parts[3] if len(parts) > 3 else "Standard"

    # ── Validate ──────────────────────────────────────────────────────────────
    if rarity not in VALID_RARITIES:
        return await message.reply_text(
            f"❌ Invalid rarity: <b>{rarity}</b>\n"
            f"Valid: {', '.join(VALID_RARITIES)}",
            parse_mode=enums.ParseMode.HTML,
        )

    if img_url and not img_url.startswith(("http://", "https://")):
        return await message.reply_text("❌ Invalid image URL!")

    # ── Check duplicate ───────────────────────────────────────────────────────
    existing = await find_waifu(name)
    if existing:
        exact = [w for w in existing if w["name"].lower() == name.lower()]
        if exact:
            return await message.reply_text(
                f"⚠️ <b>{escape(name)}</b> already exists in database!",
                parse_mode=enums.ParseMode.HTML,
            )

    # ── Add via API ───────────────────────────────────────────────────────────
    processing = await message.reply_text("⏳ Adding waifu...")

    result = await add_waifu(
        api_key=config.WAIFU_API_KEY,
        name=name,
        img_url=img_url,
        rarity=rarity,
        event_tag=event_tag,
        source_message_id=message.id,
        added_by=user.first_name,
    )

    if not result:
        return await processing.edit_text("❌ Failed to add waifu. Check API or try again.")

    await processing.delete()

    # ── Success reply ─────────────────────────────────────────────────────────
    emoji = RARITY_EMOJI.get(rarity, "◈")
    await message.reply_photo(
        photo=img_url,
        caption=(
            f"✅ <b>Waifu Added!</b>\n\n"
            f"📛 <b>{escape(name)}</b>\n"
            f"{emoji} {rarity} • 🏷 {event_tag}"
        ),
        parse_mode=enums.ParseMode.HTML,
    )

    # ── Log to channel ────────────────────────────────────────────────────────
    try:
        log_caption = build_log_caption(
            name=name,
            rarity=rarity,
            event_tag=event_tag,
            img_url=img_url,
            added_by_name=user.first_name,
            added_by_id=user.id,
            source_msg_id=message.id,
        )
        await client.send_photo(
            chat_id=config.LOG_CHANNEL,
            photo=img_url,
            caption=log_caption,
            parse_mode=enums.ParseMode.HTML,
        )
    except Exception as e:
        log.error(f"Logger failed: {e}")


# ── /delwaifu Command ─────────────────────────────────────────────────────────
@app.on_message(filters.command("delwaifu") & filters.user(config.SUDO_USERS + [config.OWNER_ID]))
async def delwaifu_handler(client: Client, message: Message):
    name = " ".join(message.command[1:]).strip()
    if not name:
        return await message.reply_text("Usage: <code>/delwaifu &lt;name&gt;</code>", parse_mode=enums.ParseMode.HTML)

    processing = await message.reply_text(f"🗑 Deleting <b>{escape(name)}</b>...", parse_mode=enums.ParseMode.HTML)
    result = await __import__("YUKIWAFUS.utils.api", fromlist=["delete_waifu"]).delete_waifu(
        api_key=config.WAIFU_API_KEY,
        name=name,
    )
    if result:
        await processing.edit_text(f"✅ <b>{escape(name)}</b> deleted from database.", parse_mode=enums.ParseMode.HTML)
        try:
            await client.send_message(
                config.LOG_CHANNEL,
                f"🗑 <b>Waifu Deleted</b>\n📛 {escape(name)}\n👤 By: <a href='tg://user?id={message.from_user.id}'>{escape(message.from_user.first_name)}</a>",
                parse_mode=enums.ParseMode.HTML,
            )
        except Exception:
            pass
    else:
        await processing.edit_text(f"❌ Failed to delete <b>{escape(name)}</b>.", parse_mode=enums.ParseMode.HTML)


# ── /findwaifu Command ────────────────────────────────────────────────────────
@app.on_message(filters.command("findwaifu"))
async def findwaifu_handler(client: Client, message: Message):
    name = " ".join(message.command[1:]).strip()
    if not name:
        return await message.reply_text("Usage: <code>/findwaifu &lt;name&gt;</code>", parse_mode=enums.ParseMode.HTML)

    results = await find_waifu(name)
    if not results:
        return await message.reply_text(f"❌ No waifu found matching <b>{escape(name)}</b>", parse_mode=enums.ParseMode.HTML)

    text = f"🔍 <b>Found {len(results)} result(s):</b>\n\n"
    for w in results[:5]:
        emoji = RARITY_EMOJI.get(w.get("rarity", "Common"), "◈")
        text += f"{emoji} <b>{escape(w['name'])}</b> — {w.get('rarity')} • {w.get('event_tag', 'Standard')}\n"

    if len(results) > 5:
        text += f"\n<i>...and {len(results) - 5} more</i>"

    await message.reply_text(text, parse_mode=enums.ParseMode.HTML)
  
