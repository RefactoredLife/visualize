import logging
import os
import tempfile

import yfinance as yf


_CONFIGURED = False
_CACHE_DIR = os.path.join(tempfile.gettempdir(), "py-yfinance-cache")


def configure_yfinance() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    try:
        os.makedirs(_CACHE_DIR, exist_ok=True)
        yf.set_tz_cache_location(_CACHE_DIR)
    except Exception as exc:
        logging.warning("Failed to configure yfinance timezone cache at %s: %s", _CACHE_DIR, exc)

    _CONFIGURED = True
