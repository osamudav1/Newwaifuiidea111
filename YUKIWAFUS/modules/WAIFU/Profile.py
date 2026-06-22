import io
from html import escape

from PIL import Image, ImageDraw, ImageFont
from pyrogram import Client, enums, filters
from pyrogram.types import Message

import config
from YUKIWAFUS import app
from YUKIWAFUS.database.Mangodb import (
    balancedb, collectiondb, game_statsdb, onoffdb,
)
from YUKIWAFUS.utils.helpers import sc

# ══════════════════════════════════════════════════════════════════════════════
# ✅ CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════
CARD_W, CARD_H = 820, 390

# Colors
BG_TOP    = (12, 10, 22)
BG_BOT    = (22, 14, 40)
ACCENT    = (190, 100, 255)
ACCENT2   = (120, 60, 200)
TEXT_W    = (235, 230, 255)
TEXT_D    = (150, 140, 175)
DIVIDER   = (40, 32, 65)

RARITY_COLORS = {
    "Common":    (180, 180, 180),
    "Uncommon":  (80,  200, 120),
    "Rare":      (80,  140, 255),
    "Epic":      (180, 80,  255),
    "Legendary": (255, 200, 0),
    "Mythic":    (255, 60,  60),
}

RARITY_EMOJI = {
    "Common":    "⚪",
    "Uncommon":  "🟢",
    "Rare":      "🔵",
    "Epic":      "🟣",
    "Legendary": "🟡",
    "Mythic":    "🔴",
}

RARITY_ORDER = ["Common", "Uncommon", "Rare", "Epic", "Legendary", "Mythic"]


# ══════════════════════════════════════════════════════════════════════════════
# ✅ FONT LOADER
# ══════════════════════════════════════════════════════════════════════════════
def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates_bold = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
    ]
    candidates_reg = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
    ]
    for path in (candidates_bold if bold else candidates_reg):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


# ══════════════════════════════════════════════════════════════════════════════
# ✅ DB HELPERS
# ══════════════════════════════════════════════════════════════════════════════
async def is_userpic_enabled() -> bool:
    doc = await onoffdb.find_one({"key": "userpic"})
    return doc.get("value", True) if doc else True


async def set_userpic(enabled: bool):
    await onoffdb.update_one(
        {"key": "userpic"},
        {"$set": {"value": enabled}},
        upsert=True,
    )


async def get_coins(user_id: int) -> int:
    doc = await balancedb.find_one({"user_id": user_id})
    return doc.get("coins", 0) if doc else 0


async def get_waifus(user_id: int) -> list:
    doc = await collectiondb.find_one({"user_id": user_id})
    return doc.get("waifus", []) if doc else []


async def get_fav_waifu(user_id: int, waifus: list) -> dict | None:
    doc = await collectiondb.find_one({"user_id": user_id})
    if not doc:
        return None
    favs = doc.get("favourites", [])
    if favs:
        fav = next((w for w in waifus if w.get("waifu_id") == favs[0]), None)
        if fav:
            return fav
    return waifus[0] if waifus else None


async def get_total_guesses(user_id: int) -> int:
    doc = await game_statsdb.find_one({"user_id": user_id})
    return doc.get("total_guesses", 0) if doc else 0


async def get_rank(user_id: int, waifu_count: int) -> int:
    """Count how many users have more waifus — rank = that count + 1."""
    pipeline = [
        {"$project": {"waifu_count": {"$size": {"$ifNull": ["$waifus", []]}}}},
        {"$match": {"waifu_count": {"$gt": waifu_count}}},
        {"$count": "above"},
    ]
    result = await collectiondb.aggregate(pipeline).to_list(1)
    return (result[0]["above"] + 1) if result else 1


# ══════════════════════════════════════════════════════════════════════════════
# ✅ AVATAR DOWNLOADER
# ══════════════════════════════════════════════════════════════════════════════
async def _get_avatar(client: Client, user_id: int) -> bytes | None:
    try:
        photos = await client.get_profile_photos(user_id, limit=1)
        if not photos:
            return None
        result = await client.download_media(photos[0], in_memory=True)
        if isinstance(result, io.BytesIO):
            return result.getvalue()
        return None
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# ✅ CARD GENERATOR
# ══════════════════════════════════════════════════════════════════════════════
def _draw_avatar(draw: ImageDraw.Draw, img: Image.Image, avatar_bytes: bytes | None, first_name: str):
    AX, AY, AS = 48, 62, 132

    # Ring
    draw.ellipse([AX - 4, AY - 4, AX + AS + 4, AY + AS + 4], outline=ACCENT, width=3)

    if avatar_bytes:
        try:
            av = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((AS, AS), Image.LANCZOS)
            mask = Image.new("L", (AS, AS), 0)
            ImageDraw.Draw(mask).ellipse([0, 0, AS, AS], fill=255)
            canvas = Image.new("RGBA", (AS, AS), (0, 0, 0, 0))
            canvas.paste(av, mask=mask)
            img.paste(canvas, (AX, AY), canvas)
            return
        except Exception:
            pass

    # Fallback: initial circle
    draw.ellipse([AX, AY, AX + AS, AY + AS], fill=(35, 24, 60))
    initial = (first_name or "?")[0].upper()
    f = _font(58, bold=True)
    bbox = draw.textbbox((0, 0), initial, font=f)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        (AX + (AS - tw) // 2, AY + (AS - th) // 2 - 2),
        initial, font=f, fill=ACCENT,
    )


def _draw_rarity_bar(draw: ImageDraw.Draw, rarity_counts: dict, total: int):
    BX, BY = 48, CARD_H - 70
    BW, BH = CARD_W - 96, 13

    draw.line([(BX, BY - 24), (BX + BW, BY - 24)], fill=DIVIDER, width=1)
    draw.text((BX, BY - 20), "Collection Breakdown", font=_font(13), fill=TEXT_D)

    # Bar background
    draw.rounded_rectangle([BX, BY, BX + BW, BY + BH], radius=7, fill=(28, 20, 48))

    # Segments
    cx = BX
    for rarity in RARITY_ORDER:
        count = rarity_counts.get(rarity, 0)
        if count == 0:
            continue
        seg = max(4, int((count / max(total, 1)) * BW))
        draw.rectangle([cx, BY, cx + seg, BY + BH], fill=RARITY_COLORS[rarity])
        cx += seg

    # Legend
    lx, ly = BX, BY + BH + 8
    f_leg = _font(13)
    for rarity in RARITY_ORDER:
        count = rarity_counts.get(rarity, 0)
        if count == 0:
            continue
        label = f"{rarity[:3]} {count}"
        draw.rectangle([lx, ly + 3, lx + 8, ly + 11], fill=RARITY_COLORS[rarity])
        draw.text((lx + 12, ly), label, font=f_leg, fill=TEXT_D)
        bbox = draw.textbbox((0, 0), label, font=f_leg)
        lx += bbox[2] - bbox[0] + 22
        if lx > BX + BW - 60:
            break


async def generate_profile_card(
    user_id:      int,
    first_name:   str,
    username:     str | None,
    waifus:       list,
    coins:        int,
    rank:         int,
    fav_waifu:    dict | None,
    total_guesses: int,
    avatar_bytes: bytes | None,
    title:        str | None,
) -> io.BytesIO:

    # ── Background gradient ──────────────────────────────────────────────────
    img  = Image.new("RGB", (CARD_W, CARD_H), BG_TOP)
    draw = ImageDraw.Draw(img)

    for y in range(CARD_H):
        t = y / CARD_H
        r = int(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * t)
        draw.line([(0, y), (CARD_W, y)], fill=(r, g, b))

    # ── Decorative blobs ─────────────────────────────────────────────────────
    draw.ellipse([-90, -90, 200, 200], fill=(22, 14, 42))
    draw.ellipse([660, 240, 920, 480], fill=(18, 12, 38))

    # ── Top accent bar ───────────────────────────────────────────────────────
    draw.rectangle([0, 0, CARD_W, 4], fill=ACCENT)

    # ── Avatar ───────────────────────────────────────────────────────────────
    _draw_avatar(draw, img, avatar_bytes, first_name)

    # ── Name & handle ────────────────────────────────────────────────────────
    IX = 48 + 132 + 28          # info x-start
    IY = 62

    name_text = (first_name or "User")[:22] + ("…" if len(first_name or "") > 22 else "")
    draw.text((IX, IY), name_text, font=_font(30, bold=True), fill=TEXT_W)

    handle = f"@{username}" if username else f"ɪᴅ: {user_id}"
    draw.text((IX, IY + 38), handle, font=_font(18), fill=TEXT_D)

    # ── Title badge ──────────────────────────────────────────────────────────
    title_y = IY + 66
    if title:
        t_text = f" ✦ {title} ✦ "
        f_t    = _font(16)
        bbox   = draw.textbbox((0, 0), t_text, font=f_t)
        tw     = bbox[2] - bbox[0]
        draw.rounded_rectangle(
            [IX - 2, title_y - 2, IX + tw + 2, title_y + 20],
            radius=6, fill=(55, 28, 95),
        )
        draw.text((IX, title_y), t_text, font=f_t, fill=ACCENT)

    # ── Vertical divider ─────────────────────────────────────────────────────
    DX = 460
    draw.line([(DX, 46), (DX, CARD_H - 80)], fill=DIVIDER, width=1)

    # ── Stats panel (right side) ─────────────────────────────────────────────
    SX = DX + 24
    f_label = _font(16)
    f_val   = _font(22, bold=True)

    stats = [
        ("🌸", sc("Waifus"),   str(len(waifus))),
        ("🪙", sc("Coins"),    f"{coins:,}"),
        ("🏆", sc("Rank"),     f"#{rank}"),
        ("🎯", sc("Guesses"),  str(total_guesses)),
    ]

    if fav_waifu:
        fav_name  = (fav_waifu.get("name") or "")[:14]
        fav_rar   = fav_waifu.get("rarity", "")
        fav_emoji = RARITY_EMOJI.get(fav_rar, "◈")
        stats.append(("❤️", sc("Fav"), f"{fav_emoji} {fav_name}"))

    for i, (emoji, label, value) in enumerate(stats):
        sy = 52 + i * 50
        draw.rounded_rectangle([SX, sy, SX + 310, sy + 40], radius=8, fill=(22, 16, 42))
        draw.text((SX + 10, sy + 10), emoji,  font=f_label, fill=TEXT_W)
        draw.text((SX + 36, sy + 12), label,  font=f_label, fill=TEXT_D)
        # Value right-aligned
        bbox = draw.textbbox((0, 0), value, font=f_val)
        vw   = bbox[2] - bbox[0]
        draw.text((SX + 300 - vw, sy + 9), value, font=f_val, fill=TEXT_W)

    # ── Rarity breakdown bar ─────────────────────────────────────────────────
    rarity_counts = {}
    for w in waifus:
        r = w.get("rarity", "Common")
        rarity_counts[r] = rarity_counts.get(r, 0) + 1

    _draw_rarity_bar(draw, rarity_counts, len(waifus))

    # ── Watermark ────────────────────────────────────────────────────────────
    wm = "✦ YUKIWAFUS"
    f_wm = _font(13)
    bbox = draw.textbbox((0, 0), wm, font=f_wm)
    draw.text((CARD_W - (bbox[2] - bbox[0]) - 14, CARD_H - 18), wm, font=f_wm, fill=(50, 40, 75))

    # ── Save ─────────────────────────────────────────────────────────────────
    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True)
    out.seek(0)
    return out


# ══════════════════════════════════════════════════════════════════════════════
# ✅ /profile COMMAND
# ══════════════════════════════════════════════════════════════════════════════
@app.on_message(filters.command(["profile", "me", "card"]))
async def profile_cmd(client: Client, message: Message):
    # Target: reply → someone else, else self
    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
    else:
        target = message.from_user

    if target.is_bot:
        return await message.reply_text(
            f"<blockquote>❌ <b>{sc('Bots have no profile')}!</b></blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    processing = await message.reply_text(
        f"<blockquote>🎴 <b>{sc('Generating profile card')}...</b></blockquote>",
        parse_mode=enums.ParseMode.HTML,
    )

    try:
        # ── Fetch all data concurrently ───────────────────────────────────────
        waifus        = await get_waifus(target.id)
        coins         = await get_coins(target.id)
        total_guesses = await get_total_guesses(target.id)
        rank          = await get_rank(target.id, len(waifus))
        fav_waifu     = await get_fav_waifu(target.id, waifus)

        # Title (if title system exists later)
        title = None

        # Avatar (only if userpic is enabled globally)
        avatar_bytes = None
        if await is_userpic_enabled():
            avatar_bytes = await _get_avatar(client, target.id)

        # ── Generate card ─────────────────────────────────────────────────────
        card = await generate_profile_card(
            user_id       = target.id,
            first_name    = target.first_name or "",
            username      = target.username,
            waifus        = waifus,
            coins         = coins,
            rank          = rank,
            fav_waifu     = fav_waifu,
            total_guesses = total_guesses,
            avatar_bytes  = avatar_bytes,
            title         = title,
        )

        await processing.delete()

        mention = f"<a href='tg://user?id={target.id}'>{escape(target.first_name or 'User')}</a>"

        await message.reply_photo(
            photo=card,
            caption=(
                f"<blockquote>"
                f"<emoji id='6291837599254322363'>🌸</emoji> "
                f"<b>{sc('Profile')} — {mention}</b>"
                f"</blockquote>\n\n"
                f"<b>🌸 {sc('Waifus')} :</b>  <code>{len(waifus)}</code>\n"
                f"<b>🪙 {sc('Coins')} :</b>   <code>{coins:,}</code>\n"
                f"<b>🏆 {sc('Rank')} :</b>    <code>#{rank}</code>\n"
                f"<b>🎯 {sc('Guesses')} :</b> <code>{total_guesses}</code>"
            ),
            parse_mode=enums.ParseMode.HTML,
        )

    except Exception as e:
        await processing.delete()
        await message.reply_text(
            f"<blockquote>❌ <b>{sc('Failed to generate profile')}.</b></blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )


# ══════════════════════════════════════════════════════════════════════════════
# ✅ /userpic — Admin Toggle (sudo/owner only)
# ══════════════════════════════════════════════════════════════════════════════
@app.on_message(
    filters.command("userpic")
    & filters.user(config.SUDO_USERS + [config.OWNER_ID])
)
async def userpic_cmd(client: Client, message: Message):
    # No args → show current state
    if len(message.command) < 2:
        state = await is_userpic_enabled()
        label = "ᴇɴᴀʙʟᴇᴅ ✅" if state else "ᴅɪsᴀʙʟᴇᴅ ❌"
        return await message.reply_text(
            f"<blockquote>"
            f"<emoji id='6080176744709495278'>🐾</emoji> "
            f"<b>ᴜsᴇʀᴘɪᴄ :</b> {label}"
            f"</blockquote>\n\n"
            f"<b>ᴜsᴀɢᴇ :</b> "
            f"<code>/userpic on</code> | <code>/userpic off</code>",
            parse_mode=enums.ParseMode.HTML,
        )

    arg = message.command[1].lower()

    if arg == "on":
        await set_userpic(True)
        await message.reply_text(
            f"<blockquote>"
            f"<emoji id='6001483331709966655'>✅</emoji> "
            f"<b>ᴜsᴇʀ ᴘʜᴏᴛᴏs ᴇɴᴀʙʟᴇᴅ!</b>"
            f"</blockquote>\n\n"
            f"<i>{sc('Profile cards will now show user photos')}.</i>",
            parse_mode=enums.ParseMode.HTML,
        )

    elif arg == "off":
        await set_userpic(False)
        await message.reply_text(
            f"<blockquote>"
            f"<emoji id='5998834801472182366'>❌</emoji> "
            f"<b>ᴜsᴇʀ ᴘʜᴏᴛᴏs ᴅɪsᴀʙʟᴇᴅ!</b>"
            f"</blockquote>\n\n"
            f"<i>{sc('Profile cards will show initials instead')}.</i>",
            parse_mode=enums.ParseMode.HTML,
        )

    else:
        await message.reply_text(
            f"<blockquote>"
            f"<emoji id='6001602353843672777'>⚠️</emoji> "
            f"<b>ɪɴᴠᴀʟɪᴅ.</b> Use <code>on</code> or <code>off</code>."
            f"</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )
