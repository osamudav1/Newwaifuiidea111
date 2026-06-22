import glob
import os
from os.path import basename, dirname, isfile, relpath

from YUKIWAFUS.logging import LOGGER


def _list_all_modules():
    base      = dirname(__file__)
    mod_paths = glob.glob(base + "/**/*.py", recursive=True)
    modules   = []

    for f in mod_paths:
        if not isfile(f):
            continue
        if "__init__" in f:
            continue
        rel = relpath(f, base)
        mod = rel.replace(os.sep, ".")[:-3]
        modules.append(mod)

    return modules


ALL_MODULES = _list_all_modules()
LOGGER.info(f"Modules found: {ALL_MODULES}")

__all__ = ALL_MODULES + ["ALL_MODULES"]
