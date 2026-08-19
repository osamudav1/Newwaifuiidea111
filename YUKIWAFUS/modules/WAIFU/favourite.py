from html import escape

from pyrogram import Client, enums, filters
from pyrogram.types import Message

from YUKIWAFUS import app
from YUKIWAFUS.database.Mangodb import collectiondb
from YUKIWAFUS.utils.helpers import sc


async def _find_owned_waifu(user_id: int, value: str):
    user = await collectiondb.find_one({"user_id": user_id})
    waifus = (user or {}).get("waifus", [])
    needle = value.strip().lower()
    for waifu in waifus:
        waifu_id = str(waifu.get("waifu_id", ""))
        name = str(waifu.get("name", ""))
        if needle in {waifu_id.lower(), name.lower()}:
            return waifu
    return None


@app.on_message(filters.command(["fav", "favorite", "favourite"]))
async def favourite_handler(client: Client, message: Message):
    user_id = message.from_user.id
    user = await collectiondb.find_one({"user_id": user_id}) or {}
    favourites = list(user.get("favourites", []))

    if len(message.command) < 2:
        if not favourites:
            return await message.reply_text(
                f"💖 {sc('No favourite waifu set.')}\n"
                f"{sc('Usage')}: <code>/fav &lt;waifu_id or name&gt;</code>",
                parse_mode=enums.ParseMode.HTML,
            )
        return await message.reply_text(
            f"💖 {sc('Favourite waifu')}: <code>{escape(str(favourites[0]))}</code>"
        )

    value = " ".join(message.command[1:])
    waifu = await _find_owned_waifu(user_id, value)
    if not waifu:
        return await message.reply_text(
            f"❌ {sc('That waifu is not in your harem.')}",
        )

    waifu_id = str(waifu.get("waifu_id", waifu.get("name", "")))
    if waifu_id in favourites:
        favourites.remove(waifu_id)
        action = sc("removed from favourites")
    else:
        favourites.insert(0, waifu_id)
        favourites = favourites[:5]
        action = sc("added to favourites")

    await collectiondb.update_one(
        {"user_id": user_id},
        {"$set": {"favourites": favourites}},
        upsert=True,
    )
    await message.reply_text(
        f"💖 <b>{escape(str(waifu.get('name', waifu_id)))}</b> {action}.",
        parse_mode=enums.ParseMode.HTML,
    )
