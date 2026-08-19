import logging
import sys

from colorlog import ColoredFormatter

LOG_FORMAT = "%(log_color)s[%(asctime)s] [%(levelname)s]%(reset)s ❯ %(name)s ❯ %(message)s"
DATE_FORMAT = "%d-%b-%Y %H:%M:%S"

LOG_COLORS = {
    "DEBUG": "cyan",
    "INFO": "green",
    "WARNING": "yellow",
    "ERROR": "red",
    "CRITICAL": "bold_red",
}

formatter = ColoredFormatter(
    LOG_FORMAT,
    datefmt=DATE_FORMAT,
    log_colors=LOG_COLORS,
)

stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(formatter)

file_handler = logging.FileHandler("yukiwafus.log", encoding="utf-8")
file_handler.setFormatter(
    logging.Formatter(
        "[%(asctime)s] [%(levelname)s] ❯ %(name)s ❯ %(message)s",
        datefmt=DATE_FORMAT,
    )
)

logging.basicConfig(
    level=logging.INFO,
    handlers=[stream_handler, file_handler],
)

logging.getLogger("pyrogram").setLevel(logging.ERROR)
logging.getLogger("motor").setLevel(logging.ERROR)
logging.getLogger("pymongo").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("apscheduler").setLevel(logging.ERROR)

# ✅ ဒီနေရာကို ပြောင်းပါ
LOGGER = logging.getLogger("YUKIWAFUS")  # object

# LOGGER function ကို ဖျက်ပစ်ပါ (ဒါမှမဟုတ် မသုံးပါနဲ့)
# def LOGGER(name: str) -> logging.Logger:
#     return logging.getLogger(name)
