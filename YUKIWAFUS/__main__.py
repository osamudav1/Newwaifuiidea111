import importlib
import os
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer



class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ("/", "/health"):
            self.send_response(404)
            self.end_headers()
            return

        body = b"OK\n"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_HEAD(self):
        if self.path not in ("/", "/health"):
            self.send_response(404)
            self.end_headers()
            return
        body = b"OK\n"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()

    def log_message(self, format, *args):
        return


def start_health_server():
    port = int(os.environ.get("PORT", "10000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), HealthHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


# Runtime objects are loaded only after the health server is bound.  This lets
# Render detect the web port even when an environment value or Telegram/MongoDB
# startup dependency is temporarily invalid.
app = None
config = None
ALL_MODULES = ()
_log = None


def load_runtime():
    global app, config, ALL_MODULES, _log
    import config as config_module
    from YUKIWAFUS import LOGGER, app as app_client
    from YUKIWAFUS.modules import ALL_MODULES as discovered_modules

    config = config_module
    app = app_client
    ALL_MODULES = discovered_modules
    _log = LOGGER


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
    handler_count = sum(len(group) for group in app.dispatcher.groups.values())
    _log.info(f"  ✦ Handlers: {handler_count}")
    _log.info(
        "  ✦ Admin config: owner_set=%s, sudo_count=%s",
        bool(config.OWNER_ID),
        len(config.SUDO_USERS),
    )
    if not config.OWNER_ID:
        _log.error("OWNER_ID is missing or invalid; protected commands will be ignored")
    if failed:
        _log.warning(f"  ✗ Failed  : {len(failed)} → {failed}")
    _log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    _log.info(
        "╔═════ஜ۩۞۩ஜ════╗\n"
        "  ✦ OSAMU Started ✦\n"
        "╚═════ஜ۩۞۩ஜ════╝"
    )

    # Log failed modules to LOG_CHANNEL if any
    if failed and getattr(config, "LOG_CHANNEL", 0):
        try:
            await app.send_message(
                config.LOG_CHANNEL,
                "<blockquote>⚠️ <b>Failed to load modules:</b></blockquote>\n"
                + "\n".join(f"• <code>{m}</code>" for m in failed),
                parse_mode="html",
            )
        except Exception:
            pass

    from pyrogram import idle

    await idle()
    await app.stop()
    _log.info("YUKIWAFUS Stopped.")


if __name__ == "__main__":
    start_health_server()
    load_runtime()
    # `Client` creates its dispatcher on the event loop available during
    # package import.  Reusing that same loop is required because Pyrogram's
    # decorator registration schedules handler-install tasks on it.  Using
    # asyncio.run() here creates a different loop and leaves every handler
    # unregistered, making the live bot silently ignore all commands.
    app.loop.run_until_complete(init())
    
