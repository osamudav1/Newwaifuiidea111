"""
safe_reply_photo — robust multi-stage fallback:
  1. Send photo with original caption + markup
  2. Strip custom emoji → retry photo
  3. Strip inline switch buttons → retry photo
  4. Fall back to reply_text (no photo)
  5. reply_text without markup
"""

import re
from pyrogram import enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message


def _strip_custom_emoji(text: str) -> str:
    """<emoji id='...'>🌸</emoji>  →  🌸"""
    return re.sub(r"<emoji[^>]*>(.*?)</emoji>", r"\1", text, flags=re.DOTALL)


def _strip_switch_inline(markup: InlineKeyboardMarkup | None) -> InlineKeyboardMarkup | None:
    """Remove switch_inline_query_current_chat buttons (need inline mode enabled)."""
    if markup is None:
        return None
    new_rows = []
    for row in markup.inline_keyboard:
        new_row = [
            btn for btn in row
            if btn.switch_inline_query_current_chat is None
            and btn.switch_inline_query is None
        ]
        if new_row:
            new_rows.append(new_row)
    return InlineKeyboardMarkup(new_rows) if new_rows else None


async def safe_reply_photo(
    message: Message,
    photo: str,
    caption: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    has_spoiler: bool = True,
    parse_mode=enums.ParseMode.HTML,
) -> None:
    clean_caption = _strip_custom_emoji(caption)
    clean_markup  = _strip_switch_inline(reply_markup)

    # Stage 1: original
    try:
        await message.reply_photo(
            photo=photo, caption=caption,
            parse_mode=parse_mode, reply_markup=reply_markup,
            has_spoiler=has_spoiler,
        )
        return
    except Exception:
        pass

    # Stage 2: stripped emoji + stripped inline buttons
    try:
        await message.reply_photo(
            photo=photo, caption=clean_caption,
            parse_mode=parse_mode, reply_markup=clean_markup,
            has_spoiler=has_spoiler,
        )
        return
    except Exception:
        pass

    # Stage 3: text with cleaned caption + cleaned markup
    try:
        await message.reply_text(
            clean_caption,
            parse_mode=parse_mode,
            reply_markup=clean_markup,
        )
        return
    except Exception:
        pass

    # Stage 4: plain text, no markup at all
    try:
        await message.reply_text(
            re.sub(r"<[^>]+>", "", clean_caption),  # strip all HTML too
        )
    except Exception:
        pass


async def safe_reply_text(
    message: Message,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode=enums.ParseMode.HTML,
) -> None:
    """reply_text with custom emoji stripping fallback."""
    clean_text   = _strip_custom_emoji(text)
    clean_markup = _strip_switch_inline(reply_markup)

    # Stage 1: original
    try:
        await message.reply_text(
            text, parse_mode=parse_mode, reply_markup=reply_markup,
        )
        return
    except Exception:
        pass

    # Stage 2: stripped
    try:
        await message.reply_text(
            clean_text, parse_mode=parse_mode, reply_markup=clean_markup,
        )
        return
    except Exception:
        pass

    # Stage 3: no HTML at all
    try:
        await message.reply_text(re.sub(r"<[^>]+>", "", clean_text))
    except Exception:
        pass
