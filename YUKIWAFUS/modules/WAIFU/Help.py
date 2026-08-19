import aiohttp
from typing import Union

from pyrogram import Client, enums, filters
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

import config
from YUKIWAFUS import app
from YUKIWAFUS.utils.helpers import sc

# ══════════════════════════════════════════════════════════════════════════════
# ✅ RAW BOT API HELPERS  (same pattern as start.py)
# ══════════════════════════════════════════════════════════════════════════════
def _token() -> str:
    return getattr(config, "BOT_TOKEN", "")


async def _bot_api(method: str, payload: dict) -> dict:
    url = f"https://api.telegram.org/bot{_token()}/{method}"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json=payload) as resp:
                return await resp.json()
    except Exception as e:
        print(f"[help/_bot_api] {e}")
        return {}


async def _raw_edit(chat_id: int, message_id: int, caption: str, markup: list) -> bool:
    res = await _bot_api("editMessageCaption", {
        "chat_id":      chat_id,
        "message_id":   message_id,
        "caption":      caption,
        "parse_mode":   "HTML",
        "reply_markup": {"inline_keyboard": markup},
    })
    return res.get("ok", False)


async def _raw_edit_text(chat_id: int, message_id: int, text: str, markup: list) -> bool:
    res = await _bot_api("editMessageText", {
        "chat_id":      chat_id,
        "message_id":   message_id,
        "text":         text,
        "parse_mode":   "HTML",
        "reply_markup": {"inline_keyboard": markup},
    })
    return res.get("ok", False)


# ── Colored button builder (same as start.py) ─────────────────────────────────
def btn(
    text: str,
    callback_data: str = None,
    url: str            = None,
    style: str          = None,
    emoji_id: str       = None,
) -> dict:
    b = {"text": text}
    if callback_data:
        b["callback_data"] = callback_data
    if url:
        u = str(url)
        if not u.startswith("http") and not u.startswith("tg://"):
            u = f"https://t.me/{u.lstrip('@')}"
        b["url"] = u
    if style in ("primary", "success", "danger"):
        b["style"] = style
    if emoji_id:
        b["icon_custom_emoji_id"] = str(emoji_id)
    return b


# ══════════════════════════════════════════════════════════════════════════════
# ✅ HELP CATEGORIES — text content
# ══════════════════════════════════════════════════════════════════════════════
_HELP = {

    "waifu": (
        "┌─── ˹ <b>ᴡᴀɪғᴜ ᴄᴏᴍᴍᴀɴᴅs</b> ˼ ───●\n\n"
        "<blockquote>"
        "<emoji id='6291837599254322363'>🌸</emoji> "
        "<b>/hclaim</b> — <code>ᴄʟᴀɪᴍ ʏᴏᴜʀ ᴅᴀɪʟʏ ᴡᴀɪғᴜ + ᴄᴏɪɴs</code>\n"
        "<emoji id='6294063539069917326'>⚡</emoji> "
        "<b>/guess</b> <code>&lt;name&gt;</code> — <code>ɢᴜᴇss sᴘᴀᴡɴᴇᴅ ᴡᴀɪғᴜ</code>\n"
        "<emoji id='5249244862359812334'>📚</emoji> "
        "<b>/harem</b> — <code>ᴠɪᴇᴡ ʏᴏᴜʀ ᴡᴀɪғᴜ ᴄᴏʟʟᴇᴄᴛɪᴏɴ</code>\n"
        "<emoji id='6291837599254322363'>💖</emoji> "
        "<b>/fav</b> <code>&lt;waifu_id&gt;</code> — <code>ᴀᴅᴅ ᴛᴏ ғᴀᴠᴏᴜʀɪᴛᴇs</code>\n"
        "<emoji id='5238162283368035495'>🎴</emoji> "
        "<b>/spawnon</b> / <b>/spawnoff</b> — <code>ᴛᴏɢɢʟᴇ ᴡᴀɪғᴜ sᴘᴀᴡɴ</code>\n"
        "<emoji id='6294023338176028117'>🔧</emoji> "
        "<b>/setspawn</b> <code>&lt;n&gt;</code> — <code>sᴘᴀᴡɴ ᴇᴠᴇʀʏ ɴ ᴍᴇssᴀɢᴇs</code>\n"
        "<emoji id='6294063539069917326'>🔍</emoji> "
        "<b>/search</b> — <code>sᴇᴀʀᴄʜ ᴡᴀɪғᴜs ɪɴ ᴅᴀᴛᴀʙᴀsᴇ</code>"
        "</blockquote>"
    ),

    "battle": (
        "┌─── ˹ <b>ʙᴀᴛᴛʟᴇ ᴄᴏᴍᴍᴀɴᴅs</b> ˼ ───●\n\n"
        "<blockquote>"
        "<emoji id='6294023338176028117'>⚔️</emoji> "
        "<b>/battle</b> — <code>ʀᴇᴘʟʏ ᴛᴏ ᴄʜᴀʟʟᴇɴɢᴇ ᴀ ᴜsᴇʀ</code>\n"
        "<emoji id='6291835288561917135'>🏆</emoji> "
        "<b>/battlestats</b> — <code>ᴠɪᴇᴡ ʏᴏᴜʀ ʙᴀᴛᴛʟᴇ ʀᴇᴄᴏʀᴅ</code>\n\n"
        "<emoji id='6001602353843672777'>💡</emoji> "
        "<i>ʙᴀᴛᴛʟᴇ ᴜsᴇs ʏᴏᴜʀ ʜɪɢʜᴇsᴛ ʀᴀʀɪᴛʏ ᴡᴀɪғᴜ\n"
        "ᴡɪɴɴᴇʀ ᴇᴀʀɴs ᴄᴏɪɴs ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ~</i>"
        "</blockquote>"
    ),

    "economy": (
        "┌─── ˹ <b>ᴇᴄᴏɴᴏᴍʏ ᴄᴏᴍᴍᴀɴᴅs</b> ˼ ───●\n\n"
        "<blockquote>"
        "<emoji id='6291837599254322363'>🌸</emoji> "
        "<b>/balance</b> — <code>ᴄʜᴇᴄᴋ sᴀᴋᴜʀᴀ ᴄᴏɪɴ ʙᴀʟᴀɴᴄᴇ</code>\n"
        "<emoji id='5249244862359812334'>💸</emoji> "
        "<b>/pay</b> <code>&lt;amount&gt;</code> — <code>sᴇɴᴅ ᴄᴏɪɴs ᴛᴏ ᴜsᴇʀ</code>\n"
        "<emoji id='6294063539069917326'>⚡</emoji> "
        "<b>/daily</b> — <code>ᴄʟᴀɪᴍ sᴛʀᴇᴀᴋ ʙᴏɴᴜs ᴄᴏɪɴs</code>\n"
        "<emoji id='6294023338176028117'>🎁</emoji> "
        "<b>/gift</b> <code>&lt;waifu_id&gt;</code> — <code>ɢɪғᴛ ᴀ ᴡᴀɪғᴜ ᴛᴏ ᴜsᴇʀ</code>\n"
        "<emoji id='5262770659267735289'>🔀</emoji> "
        "<b>/trade</b> <code>&lt;my_id&gt; &lt;their_id&gt;</code> — <code>ᴛʀᴀᴅᴇ ᴡᴀɪғᴜs</code>\n"
        "<emoji id='6291835288561917135'>🛒</emoji> "
        "<b>/shop</b> — <code>ʙʀᴏᴡsᴇ ᴛʜᴇ ᴡᴀɪғᴜ sʜᴏᴘ</code>\n"
        "<emoji id='5238162283368035495'>🎰</emoji> "
        "<b>/gacha</b> — <code>sᴘᴇɴᴅ ᴛᴏᴋᴇɴs ғᴏʀ ʀᴀʀɪᴛʏ ᴘᴜʟʟ</code>"
        "</blockquote>"
    ),

    "rank": (
        "┌─── ˹ <b>ʀᴀɴᴋ & ᴛᴏᴘ</b> ˼ ───●\n\n"
        "<blockquote>"
        "<emoji id='6291835288561917135'>🏆</emoji> "
        "<b>/rank</b> — <code>ɢʟᴏʙᴀʟ ᴡᴀɪғᴜ / ᴄᴏɪɴ ʟᴇᴀᴅᴇʀʙᴏᴀʀᴅ</code>\n"
        "<emoji id='6294023338176028117'>📊</emoji> "
        "<b>/ctop</b> — <code>ᴛᴏᴘ ɢʀᴏᴜᴘs ʙʏ ᴡᴀɪғᴜ ᴄᴏᴜɴᴛ</code>\n"
        "<emoji id='6291837599254322363'>🌸</emoji> "
        "<b>/top</b> — <code>ᴛᴏᴘ ᴄᴏɪɴ ʜᴏʟᴅᴇʀs</code>\n\n"
        "<emoji id='6001602353843672777'>💡</emoji> "
        "<i>ʀᴀɴᴋ ʜᴀs 4 ᴛᴀʙs — ᴡᴀɪғᴜs, ᴄᴏɪɴs,\n"
        "ɢᴜᴇssᴇʀs & ɢʀᴏᴜᴘs~</i>"
        "</blockquote>"
    ),

    "profile": (
        "┌─── ˹ <b>ᴘʀᴏғɪʟᴇ & ᴛɪᴛʟᴇs</b> ˼ ───●\n\n"
        "<blockquote>"
        "<emoji id='5249244862359812334'>🪪</emoji> "
        "<b>/profile</b> — <code>ᴠɪᴇᴡ ʏᴏᴜʀ ᴘʀᴏғɪʟᴇ ᴄᴀʀᴅ</code>\n"
        "<emoji id='6291837599254322363'>👑</emoji> "
        "<b>/title</b> — <code>ᴠɪᴇᴡ & ᴇǫᴜɪᴘ ᴛɪᴛʟᴇs</code>\n"
        "<emoji id='6294063539069917326'>🏷</emoji> "
        "<b>/buytitle</b> <code>&lt;title&gt;</code> — <code>ʙᴜʏ ᴀ ᴛɪᴛʟᴇ</code>\n"
        "<emoji id='5262770659267735289'>✨</emoji> "
        "<b>/equip</b> <code>&lt;title&gt;</code> — <code>ᴇǫᴜɪᴘ ᴀ ᴛɪᴛʟᴇ</code>\n"
        "<emoji id='6294023338176028117'>🔓</emoji> "
        "<b>/unequip</b> — <code>ʀᴇᴍᴏᴠᴇ ᴇǫᴜɪᴘᴘᴇᴅ ᴛɪᴛʟᴇ</code>"
        "</blockquote>"
    ),

    "tools": (
        "┌─── ˹ <b>ᴛᴏᴏʟs</b> ˼ ───●\n\n"
        "<blockquote>"
        "<emoji id='6294063539069917326'>⚡</emoji> "
        "<b>/ping</b> — <code>ʙᴏᴛ ᴘɪɴɢ & sʏsᴛᴇᴍ sᴛᴀᴛs</code>\n"
        "<emoji id='5249244862359812334'>📈</emoji> "
        "<b>/stats</b> — <code>ɢʟᴏʙᴀʟ ʙᴏᴛ sᴛᴀᴛɪsᴛɪᴄs</code>\n"
        "<emoji id='6291837599254322363'>📋</emoji> "
        "<b>/chatlog</b> — <code>ᴠɪᴇᴡ ɢʀᴏᴜᴘ ᴄʜᴀᴛ ʟᴏɢ</code>"
        "</blockquote>"
    ),

    "admin": (
        "┌─── ˹ <b>ᴀᴅᴍɪɴ ᴄᴏᴍᴍᴀɴᴅs</b> ˼ ───●\n\n"
        "<blockquote>"
        "<emoji id='6294023338176028117'>🌸</emoji> "
        "<b>/addwaifu</b> — <code>ᴀᴅᴅ ᴡᴀɪғᴜ ᴛᴏ ᴅᴀᴛᴀʙᴀsᴇ</code>\n"
        "<emoji id='5262770659267735289'>👑</emoji> "
        "<b>/addsudo</b> / <b>/rmsudo</b> — <code>ᴍᴀɴᴀɢᴇ sᴜᴅᴏ ᴜsᴇʀs</code>\n"
        "<emoji id='6294063539069917326'>📢</emoji> "
        "<b>/broadcast</b> — <code>ʙʀᴏᴀᴅᴄᴀsᴛ ᴛᴏ ᴀʟʟ ᴜsᴇʀs</code>\n"
        "<emoji id='5998834801472182366'>❌</emoji> "
        "<b>/gban</b> / <b>/ungban</b> — <code>ɢʟᴏʙᴀʟ ʙᴀɴ ᴜsᴇʀ</code>\n"
        "<emoji id='6291837599254322363'>🏷</emoji> "
        "<b>/addtitle</b> / <b>/deltitle</b> — <code>ᴍᴀɴᴀɢᴇ ᴛɪᴛʟᴇs</code>\n"
        "<emoji id='6001483331709966655'>💰</emoji> "
        "<b>/addcoins</b> / <b>/deduct</b> — <code>ᴍᴀɴᴀɢᴇ ᴄᴏɪɴs</code>\n"
        "<emoji id='5249244862359812334'>🛒</emoji> "
        "<b>/addshop</b> — <code>ᴀᴅᴅ ᴡᴀɪғᴜ ᴛᴏ sʜᴏᴘ</code>\n"
        "<emoji id='6291835288561917135'>⚡</emoji> "
        "<b>/fspawn</b> — <code>ғᴏʀᴄᴇ sᴘᴀᴡɴ ᴀ ᴡᴀɪғᴜ</code>"
        "</blockquote>"
    ),
}

# ══════════════════════════════════════════════════════════════════════════════
# ✅ HELP MAIN PANEL CAPTION
# ══════════════════════════════════════════════════════════════════════════════
_HELP_CAPTION = (
    "┌─── ˹ <b>ʜᴇʟᴘ ᴍᴇɴᴜ</b> ˼ ───●\n\n"
    "<blockquote>"
    "<emoji id='6291837599254322363'>🌸</emoji> "
    "<b>ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴏsᴀᴍᴜ ʜᴇʟᴘ!</b>\n\n"
    "<emoji id='6294063539069917326'>⚡</emoji> "
    "ᴄʜᴏᴏsᴇ ᴀ ᴄᴀᴛᴇɢᴏʀʏ ʙᴇʟᴏᴡ ᴛᴏ sᴇᴇ ᴄᴏᴍᴍᴀɴᴅs~"
    "</blockquote>\n\n"
    "•──────────────────────•\n"
    "<blockquote>"
    "<b><emoji id='6294023338176028117'>💀</emoji> "
    "✦ᴘᴏᴡєʀєᴅ ʙʏ » "
    "<a href='https://t.me/osamu1123'>"
    "<spoiler>── ᴏsᴀᴍᴜ ──</spoiler>"
    "</a></b>"
    "</blockquote>\n"
    "•──────────────────────•"
)

# ══════════════════════════════════════════════════════════════════════════════
# ✅ BUTTON PANELS
# ══════════════════════════════════════════════════════════════════════════════
def _help_main_panel(back_to_start: bool = False) -> list:
    """Main help category grid — raw list for Bot API."""
    rows = [
        [
            btn("🎴 ᴡᴀɪғᴜ",    callback_data="help_cat waifu",   style="primary",  emoji_id="6291837599254322363"),
            btn("⚔️ ʙᴀᴛᴛʟᴇ",   callback_data="help_cat battle",  style="danger",   emoji_id="6294023338176028117"),
            btn("💰 ᴇᴄᴏɴᴏᴍʏ",  callback_data="help_cat economy", style="success",  emoji_id="5249244862359812334"),
        ],
        [
            btn("🏆 ʀᴀɴᴋ",      callback_data="help_cat rank",    style="primary",  emoji_id="6291835288561917135"),
            btn("🪪 ᴘʀᴏғɪʟᴇ",  callback_data="help_cat profile", style="primary",  emoji_id="5262770659267735289"),
            btn("🛠 ᴛᴏᴏʟs",     callback_data="help_cat tools",   style="primary",  emoji_id="6294063539069917326"),
        ],
        [
            btn("👑 ᴀᴅᴍɪɴ",     callback_data="help_cat admin",   style="danger",   emoji_id="6294063539069917326"),
            btn("💬 sᴜᴘᴘᴏʀᴛ",  url=config.SUPPORT_CHAT,          style="success",  emoji_id="5206523956537865948"),
        ],
    ]
    # Bottom row
    if back_to_start:
        rows.append([
            btn("🏠 ʜᴏᴍᴇ",   callback_data="back_to_start_home", style="primary"),
            btn("✖ ᴄʟᴏsᴇ",   callback_data="help_close",          style="danger"),
        ])
    else:
        rows.append([
            btn("✖ ᴄʟᴏsᴇ",   callback_data="help_close",          style="danger"),
        ])
    return rows


def _help_back_panel() -> list:
    """Back button from individual category → back to help main."""
    return [[
        btn("« ʙᴀᴄᴋ",  callback_data="waifu_help",  style="primary",  emoji_id="5238162283368035495"),
        btn("✖ ᴄʟᴏsᴇ", callback_data="help_close",  style="danger"),
    ]]


def _group_help_panel() -> list:
    """Group help → DM bot button."""
    bot_username = app.username or ""
    return [[
        InlineKeyboardButton(
            "˹ ʜᴇʟᴘ ɪɴ ᴅᴍ ˼",
            url=f"https://t.me/{bot_username}?start=help",
        )
    ]]


# ══════════════════════════════════════════════════════════════════════════════
# ✅ /help — PRIVATE
# ══════════════════════════════════════════════════════════════════════════════
@app.on_message(filters.command("help") & filters.private)
async def help_private_cmd(client: Client, message: Message):
    try:
        await message.delete()
    except Exception:
        pass

    chat_id = message.chat.id
    markup  = {"inline_keyboard": _help_main_panel(back_to_start=False)}

    # ── Try 1: photo via raw Bot API ──────────────────────────────────────────
    res = await _bot_api("sendPhoto", {
        "chat_id":     chat_id,
        "photo":       config.WAIFU_PICS[0],
        "caption":     _HELP_CAPTION,
        "parse_mode":  "HTML",
        "has_spoiler": True,
    })
    if res.get("ok"):
        msg_id = res["result"]["message_id"]
        await _bot_api("editMessageReplyMarkup", {
            "chat_id":      chat_id,
            "message_id":   msg_id,
            "reply_markup": markup,
        })
        return

    # ── Try 2: photo via Pyrogram ─────────────────────────────────────────────
    try:
        rows = []
        for row in _help_main_panel(back_to_start=False):
            r = []
            for b in row:
                if b.get("callback_data"):
                    r.append(InlineKeyboardButton(b["text"], callback_data=b["callback_data"]))
                elif b.get("url"):
                    r.append(InlineKeyboardButton(b["text"], url=b["url"]))
            if r:
                rows.append(r)
        await client.send_photo(
            chat_id,
            photo=config.WAIFU_PICS[0],
            caption=_HELP_CAPTION,
            parse_mode=enums.ParseMode.HTML,
            has_spoiler=True,
            reply_markup=InlineKeyboardMarkup(rows) if rows else None,
        )
        return
    except Exception:
        pass

    # ── Try 3: text fallback (no photo) — last resort ─────────────────────────
    try:
        rows = []
        for row in _help_main_panel(back_to_start=False):
            r = []
            for b in row:
                if b.get("callback_data"):
                    r.append(InlineKeyboardButton(b["text"], callback_data=b["callback_data"]))
                elif b.get("url"):
                    r.append(InlineKeyboardButton(b["text"], url=b["url"]))
            if r:
                rows.append(r)
        await client.send_message(
            chat_id,
            _HELP_CAPTION,
            parse_mode=enums.ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(rows) if rows else None,
        )
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# ✅ /help — GROUP
# ══════════════════════════════════════════════════════════════════════════════
@app.on_message(filters.command("help") & filters.group)
async def help_group_cmd(client: Client, message: Message):
    try:
        bot_username = (await client.get_me()).username or ""
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "˹ ʜᴇʟᴘ ɪɴ ᴅᴍ ˼",
                url=f"https://t.me/{bot_username}?start=help",
            )
        ]]) if bot_username else None

        await message.reply_text(
            f"<blockquote>"
            f"<emoji id='6291837599254322363'>🌸</emoji> "
            f"<b>{sc('Help is available in DM')}!</b>"
            f"</blockquote>\n\n"
            f"<i>{sc('Click the button below to get full help menu')}~</i>",
            parse_mode=enums.ParseMode.HTML,
            reply_markup=keyboard,
        )
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# ✅ "˹ ʜᴇʟᴘ ˼" BUTTON from start.py → opens help panel (edit caption)
# ══════════════════════════════════════════════════════════════════════════════
@app.on_callback_query(filters.regex("^waifu_help$"))
async def help_main_cb(client: Client, cq: CallbackQuery):
    try:
        await cq.answer("🌸 Help Menu", show_alert=False)
    except Exception:
        pass

    ok = await _raw_edit(
        cq.message.chat.id,
        cq.message.id,
        _HELP_CAPTION,
        _help_main_panel(back_to_start=True),   # back_to_start=True → shows Home button
    )

    if not ok:
        # Fallback — plain Pyrogram edit
        try:
            from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            rows = []
            for row in _help_main_panel(back_to_start=True):
                r = []
                for b in row:
                    if b.get("callback_data"):
                        r.append(InlineKeyboardButton(b["text"], callback_data=b["callback_data"]))
                    elif b.get("url"):
                        r.append(InlineKeyboardButton(b["text"], url=b["url"]))
                if r:
                    rows.append(r)
            await cq.edit_message_caption(
                caption=_HELP_CAPTION,
                reply_markup=InlineKeyboardMarkup(rows),
                parse_mode=enums.ParseMode.HTML,
            )
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# ✅ CATEGORY BUTTON → show commands
# ══════════════════════════════════════════════════════════════════════════════
@app.on_callback_query(filters.regex("^help_cat "))
async def help_category_cb(client: Client, cq: CallbackQuery):
    cat = cq.data.split(None, 1)[1].strip()
    text = _HELP.get(cat)

    if not text:
        return await cq.answer(sc("Unknown category!"), show_alert=True)

    try:
        await cq.answer(show_alert=False)
    except Exception:
        pass

    ok = await _raw_edit_text(
        cq.message.chat.id,
        cq.message.id,
        text,
        _help_back_panel(),
    )

    if not ok:
        try:
            from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            rows = [[
                InlineKeyboardButton("« ʙᴀᴄᴋ",  callback_data="waifu_help"),
                InlineKeyboardButton("✖ ᴄʟᴏsᴇ", callback_data="help_close"),
            ]]
            await cq.edit_message_text(
                text=text,
                reply_markup=InlineKeyboardMarkup(rows),
                parse_mode=enums.ParseMode.HTML,
            )
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# ✅ CLOSE BUTTON → delete message
# ══════════════════════════════════════════════════════════════════════════════
@app.on_callback_query(filters.regex("^help_close$"))
async def help_close_cb(client: Client, cq: CallbackQuery):
    try:
        await cq.answer(show_alert=False)
        await cq.message.delete()
    except Exception:
        pass
