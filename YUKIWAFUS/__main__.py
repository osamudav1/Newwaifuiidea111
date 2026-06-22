import asyncio
import importlib
import traceback

from pyrogram import idle

import config
from YUKIWAFUS import LOGGER, app
from YUKIWAFUS.modules import ALL_MODULES

_log = LOGGER(__name__)


async def init():
    await app.start()

    failed  = []
    loaded  = []

    for module in ALL_MODULES:
        try:
            importlib.import_module("YUKIWAFUS.modules." + module)
            loaded.append(module)
            _log.info(f"  ✓ {module}")
        except Exception as e:
            failed.append(module)
            _log.error(
                f"  ✗ Failed to load [{module}]: {e}\n"
                f"{traceback.format_exc()}"
            )

    _log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    _log.info(f"  ✦ Loaded  : {len(loaded)} modules")
    if failed:
        _log.warning(f"  ✗ Failed  : {len(failed)} → {failed}")
    _log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    _log.info(
        "╔═════ஜ۩۞۩ஜ════╗\n"
        "  ✦ YUKIWAFUS Started ✦\n"
        "╚═════ஜ۩۞۩ஜ════╝"
    )

    # Log failed modules to LOG_CHANNEL if any
    if failed and getattr(config, "LOG_CHANNEL", 0):
        try:
            await app.send_message(
                config.LOG_CHANNEL,
                f"<blockquote>⚠️ <b>Failed to load modules:</b></blockquote>\n\n"
                + "\n".join(f"• <code>{m}</code>" for m in failed),
                parse_mode="html",
            )
        except Exception:
            pass

    await idle()
    await app.stop()
    _log.info("YUKIWAFUS Stopped.")


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(init())
    
