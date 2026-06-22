import time
import random
import asyncio
import aiohttp
from html import escape

from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

import config
from YUKIWAFUS import app
from YUKIWAFUS.database.Mangodb import usersdb, chatsdb, onoffdb

# ══════════════════════════════════════════════════════════════════════════════
# ✅ BOOT TIME
# ══════════════════════════════════════════════════════════════════════════════
_BOOT_TIME = time.time()


def _uptime() -> str:
    secs = int(time.time() - _BOOT_TIME)
    h, rem = divmod(secs, 3600)
    m, s   = divmod(rem, 60)
    parts  = []
    if h: parts.append(f"{h}ʜ")
    if m: parts.append(f"{m}ᴍ")
    if s: parts.append(f"{s}s")
    return ":".join(parts) or "0s"


# ══════════════════════════════════════════════════════════════════════════════
# ✅ PREMIUM EFFECT IDs
# ══════════════════════════════════════════════════════════════════════════════
EFFECT_HEARTS   = getattr(config, "EFFECT_HEARTS",   "5159385139981059251")
EFFECT_FIRE     = getattr(config, "EFFECT_FIRE",     "5104841245755180586")
EFFECT_CONFETTI = getattr(config, "EFFECT_CONFETTI", "5046509860389126442")

START_REACTION_EMOJI = getattr(config, "START_REACTION_EMOJI", "🌸")
START_REACTION_BIG   = getattr(config, "START_REACTION_BIG",   False)
GROUP_REACTION_EMOJI = getattr(config, "GROUP_REACTION_EMOJI", "❤️")
FIRE_EMOJI           = getattr(config, "FIRE_EMOJI",           "🔥")

WAIFU_PICS = getattr(config, "WAIFU_PICS", ["https://files.catbox.moe/08ge3a.jpg"])


# ══════════════════════════════════════════════════════════════════════════════
# ✅ START CAPTIONS
# ══════════════════════════════════════════════════════════════════════════════
_START_PRIVATE = (
    "┌─── ˹ <b>ɪɴғᴏʀᴍᴀᴛɪᴏɴ</b> ˼ ─── ⏤‌‌●\n"
    "<emoji id='5262770659267735289'>😈</emoji> ┆ <b>ʜєʏ, {mention}</b>\n"
    "<emoji id='6291835288561917135'>😎</emoji> ┆ <b>ɪ ᴀᴍ {bot_mention}</b>\n"
    "└──────────────────────•\n\n"
    "<blockquote>"
    "<spoiler>"
    "<b><emoji id='6294070144729619431'>💀</emoji> "
    "ᴛʜᴇ ᴍᴏsᴛ ᴘᴏᴡᴇʀғᴜʟ & ᴄᴜᴛᴇsᴛ ᴡᴀɪғᴜ ʙᴏᴛ ᴏɴ ᴛᴇʟᴇɢʀᴀᴍ!</b>"
    "</spoiler>"
    "</blockquote>\n"
    "<blockquote>"
    "<b><emoji id='6294063539069917326'>😉</emoji> ᴜᴘᴛɪᴍᴇ :</b> <spoiler>{uptime}</spoiler>\n"
    "<b><emoji id='6291837599254322363'>🌸</emoji> ᴛᴏᴛᴀʟ ᴜsᴇʀs :</b> <spoiler>{users}</spoiler>\n"
    "<b><emoji id='6291837599254322363'>🏘</emoji> ᴛᴏᴛᴀʟ ɢʀᴏᴜᴘs :</b> <spoiler>{chats}</spoiler>"
    "</blockquote>\n"
    "•──────────────────────•\n"
    "<blockquote>"
    "<b><emoji id='6294023338176028117'>💀</emoji> "
    "✦ᴘᴏᴡєʀєᴅ ʙʏ » "
    "<a href='https://t.me/yukiwafus'>"
    "<spoiler>── ʏᴜᴋɪ ᴡᴀғᴜs ──</spoiler>"
    "</a></b>"
    "</blockquote>\n"
    "•──────────────────────•"
)

_START_GROUP = (
    "<blockquote>"
    "<emoji id='6080176744709495278'>🐾</emoji> {bot_mention} "
    "<b>ɪs ᴀʟɪᴠᴇ ᴀɴᴅ ᴋɪᴄᴋɪɴɢ</b>\n\n"
    "<b><emoji id='5413415116756500503'>☠️</emoji> ᴜᴘᴛɪᴍᴇ :</b> {uptime}"
    "</blockquote>"
)


# ══════════════════════════════════════════════════════════════════════════════
# ✅ BUTTON BUILDER — safe URL validation
# ══════════════════════════════════════════════════════════════════════════════
def btn(
    text: str,
    callback_data: str = None,
    url: str            = None,
    style: str          = None,
    emoji_id: str       = None,
) -> dict | None:
    """Returns button dict, or None if URL is invalid/empty."""
    b = {"text": text}

    if callback_data:
        b["callback_data"] = callback_data
    elif url:
        u = str(url).strip()
        # Validate URL — must be a real link
        if not u:
            return None
        if not u.startswith("http") and not u.startswith("tg://"):
            u = f"https://t.me/{u.lstrip('@')}"
        # Extra guard: bare https://t.me/ is invalid
        if u in ("https://t.me/", "https://t.me", "http://t.me/"):
            return None
        b["url"] = u
    else:
        return None   # no action = useless button

    if style in ("primary", "success", "danger"):
        b["style"] = style
    if emoji_id:
        b["icon_custom_emoji_id"] = str(emoji_id)
    return b


def _row(*buttons) -> list:
    """Build a row, skipping None buttons."""
    return [b for b in buttons if b is not None]


def _private_panel() -> list:
    bot_username = app.username or ""
    rows = []

    rows.append(_row(
        btn("𝚫ᴅᴅ ᴛᴏ ɢʀᴏᴜᴘ ✧",
            url=f"https://t.me/{bot_username}?startgroup=true",
            style="success", emoji_id="5235682785863153026"),
    ))

    support_btn = btn("˹ 𝐒ᴜᴘᴘᴏʀᴛ ˼",
        url=config.SUPPORT_CHAT, style="danger",  emoji_id="5206523956537865948")
    update_btn  = btn("˹ 𝐔ᴘᴅᴀᴛᴇs ˼",
        url=config.UPDATE_CHANNEL, style="primary", emoji_id="5253539825360843975")

    row2 = _row(support_btn, update_btn)
    if row2:
        rows.append(row2)

    rows.append(_row(
        btn("˹ 𝐌ʏ ʜᴀʀᴇᴍ ˼",
            callback_data="my_harem_inline", style="primary", emoji_id="5249244862359812334"),
        btn("˹ ʜᴇʟᴘ ˼",
            callback_data="waifu_help", style="primary", emoji_id="5238162283368035495"),
    ))

    return rows


def _group_panel() -> list:
    bot_username = app.username or ""
    return [_row(
        btn("˹ 𝐃ᴍ ᴍᴇ ˼",
            url=f"https://t.me/{bot_username}?start=hi",
            style="success", emoji_id="5249244862359812334"),
        btn("˹ 𝐒ᴜᴘᴘᴏʀᴛ ˼",
            url=config.SUPPORT_CHAT, style="danger", emoji_id="5206523956537865948"),
    )]


# ══════════════════════════════════════════════════════════════════════════════
# ✅ RAW BOT API
# ══════════════════════════════════════════════════════════════════════════════
def _token() -> str:
    return getattr(config, "BOT_TOKEN", "")


async def _bot_api(method: str, payload: dict) -> dict:
    url = f"https://api.telegram.org/bot{_token()}/{method}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                return await resp.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def _inject_markup(chat_id: int, message_id: int, raw_kb: list) -> None:
    if not raw_kb:
        return
    try:
        await _bot_api("editMessageReplyMarkup", {
            "chat_id":      chat_id,
            "message_id":   message_id,
            "reply_markup": {"inline_keyboard": raw_kb},
        })
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# ✅ SEND MAGIC START — photo + effect + colored buttons
# ══════════════════════════════════════════════════════════════════════════════
async def send_magic_start(
    chat_id:     int,
    photo_url:   str,
    caption:     str,
    raw_kb:      list,
    reply_to_id: int  = None,
    effect_id:   str  = None,
) -> int | None:
    if effect_id is None:
        effect_id = EFFECT_HEARTS

    payload = {
        "chat_id":           chat_id,
        "photo":             photo_url,
        "caption":           caption,
        "parse_mode":        "HTML",
        "has_spoiler":       True,
        "message_effect_id": effect_id,
    }
    if reply_to_id:
        payload["reply_to_message_id"] = reply_to_id

    # ── Try 1: photo + effect, then inject markup separately ─────────────────
    res = await _bot_api("sendPhoto", payload)
    if res.get("ok"):
        msg_id = res["result"]["message_id"]
        if raw_kb:
            await _inject_markup(chat_id, msg_id, raw_kb)
        return msg_id

    # ── Try 2: photo + markup together (no effect) ────────────────────────────
    payload2 = {k: v for k, v in payload.items() if k != "message_effect_id"}
    if raw_kb:
        payload2["reply_markup"] = {"inline_keyboard": raw_kb}

    res2 = await _bot_api("sendPhoto", payload2)
    if res2.get("ok"):
        return res2["result"]["message_id"]

    # ── Try 3: Pyrogram fallback (no effect, plain Pyrogram buttons) ──────────
    try:
        rows = []
        for row in raw_kb:
            r = []
            for b in row:
                if b.get("callback_data"):
                    r.append(InlineKeyboardButton(b["text"], callback_data=b["callback_data"]))
                elif b.get("url"):
                    r.append(InlineKeyboardButton(b["text"], url=b["url"]))
            if r:
                rows.append(r)

        msg = await app.send_photo(
            chat_id,
            photo=photo_url,
            caption=caption,
            has_spoiler=True,
            parse_mode=enums.ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(rows) if rows else None,
        )
        return msg.id
    except Exception:
        pass

    # ── Try 4: TEXT fallback (no photo at all) — last resort ──────────────────
    try:
        rows = []
        for row in raw_kb:
            r = []
            for b in row:
                if b.get("callback_data"):
                    r.append(InlineKeyboardButton(b["text"], callback_data=b["callback_data"]))
                elif b.get("url"):
                    r.append(InlineKeyboardButton(b["text"], url=b["url"]))
            if r:
                rows.append(r)

        msg = await app.send_message(
            chat_id,
            caption,
            parse_mode=enums.ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(rows) if rows else None,
        )
        return msg.id
    except Exception:
        pass

    return None


# ══════════════════════════════════════════════════════════════════════════════
# ✅ DB HELPERS
# ══════════════════════════════════════════════════════════════════════════════
async def is_logger_on() -> bool:
    doc = await onoffdb.find_one({"key": "logger"})
    return doc.get("value", True) if doc else True


async def set_logger(enabled: bool):
    await onoffdb.update_one(
        {"key": "logger"},
        {"$set": {"value": enabled}},
        upsert=True,
    )


async def _register_user(user_id: int, username: str, first_name: str):
    await usersdb.update_one(
        {"user_id": user_id},
        {
            "$set":         {"username": username or "", "first_name": first_name},
            "$setOnInsert": {"user_id": user_id},
        },
        upsert=True,
    )


async def _register_chat(chat_id: int, title: str):
    await chatsdb.update_one(
        {"chat_id": chat_id},
        {
            "$set":         {"title": title},
            "$setOnInsert": {"chat_id": chat_id},
        },
        upsert=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# ✅ /start — PRIVATE
# ══════════════════════════════════════════════════════════════════════════════
@app.on_message(filters.command("start") & filters.private)
async def start_private(client: Client, message: Message):
    user    = message.from_user
    chat_id = message.chat.id

    await _register_user(user.id, user.username or "", user.first_name)

    # Reaction
    try:
        await client.send_reaction(
            chat_id=chat_id,
            message_id=message.id,
            emoji=START_REACTION_EMOJI,
            big=START_REACTION_BIG,
        )
    except Exception:
        pass

    # Fire effect
    try:
        await _bot_api("sendMessage", {
            "chat_id":           chat_id,
            "text":              FIRE_EMOJI,
            "message_effect_id": EFFECT_FIRE,
        })
    except Exception:
        pass

    await asyncio.sleep(0.5)

    # Build caption
    bot_me      = await client.get_me()
    mention     = f"<a href='tg://user?id={user.id}'>{escape(user.first_name)}</a>"
    bot_mention = f"<a href='tg://user?id={bot_me.id}'>{escape(bot_me.first_name)}</a>"
    users       = await usersdb.count_documents({})
    chats_count = await chatsdb.count_documents({})

    caption = _START_PRIVATE.format(
        mention=mention,
        bot_mention=bot_mention,
        uptime=_uptime(),
        users=users,
        chats=chats_count,
    )

    sent_id = await send_magic_start(
        chat_id,
        random.choice(WAIFU_PICS),
        caption,
        _private_panel(),
        effect_id=EFFECT_HEARTS,
    )

    if sent_id:
        try:
            await _bot_api("setMessageReaction", {
                "chat_id":    chat_id,
                "message_id": sent_id,
                "reaction":   [{"type": "emoji", "emoji": START_REACTION_EMOJI}],
                "is_big":     START_REACTION_BIG,
            })
        except Exception:
            pass

    # Logger
    if await is_logger_on() and config.LOG_CHANNEL:
        try:
            await app.send_message(
                config.LOG_CHANNEL,
                f"<blockquote>"
                f"<emoji id='6080176744709495278'>🐾</emoji> "
                f"{mention} <b>started the bot.</b>\n\n"
                f"<b>ᴜsᴇʀ ɪᴅ :</b> <code>{user.id}</code>\n"
                f"<b>ᴜsᴇʀɴᴀᴍᴇ :</b> @{user.username or 'N/A'}"
                f"</blockquote>",
                parse_mode=enums.ParseMode.HTML,
            )
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# ✅ /start — GROUP
# ══════════════════════════════════════════════════════════════════════════════
@app.on_message(filters.command("start") & filters.group)
async def start_group(client: Client, message: Message):
    user    = message.from_user
    chat_id = message.chat.id

    await _register_user(user.id, user.username or "", user.first_name)
    await _register_chat(chat_id, message.chat.title or "")

    try:
        await client.send_reaction(
            chat_id=chat_id,
            message_id=message.id,
            emoji=GROUP_REACTION_EMOJI,
        )
    except Exception:
        pass

    bot_me      = await client.get_me()
    bot_mention = f"<a href='tg://user?id={bot_me.id}'>{escape(bot_me.first_name)}</a>"
    caption     = _START_GROUP.format(bot_mention=bot_mention, uptime=_uptime())

    msg_id = await send_magic_start(
        chat_id,
        random.choice(WAIFU_PICS),
        caption,
        _group_panel(),
        reply_to_id=message.id,
        effect_id=EFFECT_CONFETTI,
    )

    if msg_id:
        await asyncio.sleep(60)
        try:
            await _bot_api("deleteMessage", {"chat_id": chat_id, "message_id": msg_id})
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# ✅ Bot Added To Group
# ══════════════════════════════════════════════════════════════════════════════
@app.on_message(filters.new_chat_members)
async def on_bot_added(client: Client, message: Message):
    bot_me = await client.get_me()

    for member in message.new_chat_members:
        if member.id != bot_me.id:
            continue

        await _register_chat(message.chat.id, message.chat.title or "")

        adder       = message.from_user
        mention     = (
            f"<a href='tg://user?id={adder.id}'>{escape(adder.first_name)}</a>"
            if adder else "ꜱᴏᴍᴇᴏɴᴇ"
        )
        bot_mention = f"<a href='tg://user?id={bot_me.id}'>{escape(bot_me.first_name)}</a>"

        text = (
            f"<blockquote>"
            f"<emoji id='6291835288561917135'>🌸</emoji> "
            f"<b>ʜᴇʏ! ᴛʜᴀɴᴋs ғᴏʀ ᴀᴅᴅɪɴɢ ᴍᴇ ~</b>"
            f"</blockquote>\n\n"
            f"<emoji id='5262770659267735289'>😈</emoji> ɪ ᴀᴍ {bot_mention}, "
            f"ʏᴏᴜʀ ᴡᴀɪғᴜ ᴄᴏᴍᴘᴀɴɪᴏɴ!\n\n"
            f"<emoji id='6294063539069917326'>⚡</emoji> ᴡᴀɪғᴜs sᴘᴀᴡɴ ᴀs ʏᴏᴜʀ ɢʀᴏᴜᴘ ᴄʜᴀᴛs\n"
            f"<emoji id='6294023338176028117'>🎯</emoji> ɢᴜᴇss ᴛʜᴇɪʀ ɴᴀᴍᴇs ᴛᴏ ᴄᴏʟʟᴇᴄᴛ ᴛʜᴇᴍ\n"
            f"<emoji id='6291837599254322363'>🪙</emoji> ᴇᴀʀɴ ᴄᴏɪɴs & ʙᴜɪʟᴅ ʏᴏᴜʀ ʜᴀʀᴇᴍ\n\n"
            f"<i>ᴀᴅᴅᴇᴅ ʙʏ : {mention} ❤️</i>"
        )

        msg = await message.reply_text(text, parse_mode=enums.ParseMode.HTML)
        await _inject_markup(message.chat.id, msg.id, _group_panel())

        if await is_logger_on() and config.LOG_CHANNEL:
            try:
                await app.send_message(
                    config.LOG_CHANNEL,
                    f"<blockquote>"
                    f"<emoji id='6080176744709495278'>🐾</emoji> "
                    f"<b>ʙᴏᴛ ᴀᴅᴅᴇᴅ ᴛᴏ ɢʀᴏᴜᴘ!</b>\n\n"
                    f"<b>ɢʀᴏᴜᴘ :</b> {escape(message.chat.title or '')}\n"
                    f"<b>ɪᴅ :</b> <code>{message.chat.id}</code>\n"
                    f"<b>ᴀᴅᴅᴇᴅ ʙʏ :</b> {mention}"
                    f"</blockquote>",
                    parse_mode=enums.ParseMode.HTML,
                )
            except Exception:
                pass

        await asyncio.sleep(90)
        try:
            await msg.delete()
        except Exception:
            pass

        break


# ══════════════════════════════════════════════════════════════════════════════
# ✅ back_to_start_home callback (from Help panel → back to start)
# ══════════════════════════════════════════════════════════════════════════════
@app.on_callback_query(filters.regex("^back_to_start_home$"))
async def back_to_home_cb(client, cq):
    try:
        await cq.answer("🏠 Going back...", show_alert=False)
    except Exception:
        pass

    user        = cq.from_user
    chat_id     = cq.message.chat.id
    bot_me      = await client.get_me()
    mention     = f"<a href='tg://user?id={user.id}'>{escape(user.first_name)}</a>"
    bot_mention = f"<a href='tg://user?id={bot_me.id}'>{escape(bot_me.first_name)}</a>"
    users       = await usersdb.count_documents({})
    chats_count = await chatsdb.count_documents({})

    caption = _START_PRIVATE.format(
        mention=mention,
        bot_mention=bot_mention,
        uptime=_uptime(),
        users=users,
        chats=chats_count,
    )

    ok = await _bot_api("editMessageCaption", {
        "chat_id":      chat_id,
        "message_id":   cq.message.id,
        "caption":      caption,
        "parse_mode":   "HTML",
        "reply_markup": {"inline_keyboard": _private_panel()},
    })

    if not ok.get("ok"):
        try:
            await cq.edit_message_caption(
                caption=caption,
                parse_mode=enums.ParseMode.HTML,
            )
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# ✅ /logger toggle
# ══════════════════════════════════════════════════════════════════════════════
@app.on_message(
    filters.command("logger")
    & filters.user(config.SUDO_USERS + [config.OWNER_ID])
)
async def logger_cmd(client: Client, message: Message):
    if len(message.command) < 2:
        state = await is_logger_on()
        label = "ᴇɴᴀʙʟᴇᴅ ✅" if state else "ᴅɪsᴀʙʟᴇᴅ ❌"
        return await message.reply_text(
            f"<blockquote>"
            f"<emoji id='6080176744709495278'>🐾</emoji> "
            f"<b>ʟᴏɢɢᴇʀ :</b> {label}"
            f"</blockquote>\n\n"
            f"<b>ᴜsᴀɢᴇ :</b> "
            f"<code>/logger enable</code> | <code>/logger disable</code>",
            parse_mode=enums.ParseMode.HTML,
        )

    arg = message.command[1].lower()
    if arg == "enable":
        await set_logger(True)
        await message.reply_text(
            f"<blockquote><emoji id='6001483331709966655'>✅</emoji> "
            f"<b>ʟᴏɢɢᴇʀ ᴇɴᴀʙʟᴇᴅ!</b></blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )
    elif arg == "disable":
        await set_logger(False)
        await message.reply_text(
            f"<blockquote><emoji id='5998834801472182366'>❌</emoji> "
            f"<b>ʟᴏɢɢᴇʀ ᴅɪsᴀʙʟᴇᴅ!</b></blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )
    else:
        await message.reply_text(
            f"<blockquote><emoji id='6001602353843672777'>⚠️</emoji> "
            f"<b>ɪɴᴠᴀʟɪᴅ.</b> Use <code>enable</code> or <code>disable</code>.</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )
