from __future__ import annotations

from time import time
from typing import Any, Iterable, Optional, Tuple, Dict, List
import logging

import pandas as pd
from sqlalchemy.exc import ProgrammingError, OperationalError
from common.config import (
    HOLDINGS_HEADER,
    CASH_HEADER,
    BALANCES_HEADER,
    CASHFLOW_HEADER,
    SBS_DIOI_HEADER,
)

# Simple in-process DataFrame cache with TTL.
# Treat returned DataFrames as read-only; we return a shallow copy to avoid
# accidental mutation of the cached object.

_df_cache: Dict[Tuple[str, str, str, Tuple[Any, ...]], Tuple[float, pd.DataFrame]] = {}

# Map known table names to their header definitions from config
_TABLE_HEADERS: Dict[str, List[str]] = {
    "holdings_view": HOLDINGS_HEADER,
    "cash": CASH_HEADER,
    "balances": BALANCES_HEADER,
    "cashflow": CASHFLOW_HEADER,
    "sbs_dioi": SBS_DIOI_HEADER,
}


def get_df(
    table: str,
    *,
    engine,
    ttl: float = 30.0,
    cols: str = "*",
    where: Optional[str] = None,
    params: Optional[Iterable[Any]] = None,
    parse_dates: Optional[list[str]] = None,
):
    """Return a pandas DataFrame for a SELECT, cached for `ttl` seconds.

    Keyed by (table, cols, where, params). Returns a shallow copy so callers
    can add columns without mutating the cached frame.
    """
    now = time()
    key = (table, cols, where or "", tuple(params or ()))
    hit = _df_cache.get(key)
    if hit and hit[0] > now:
        return hit[1].copy(deep=False)

    sql = f"SELECT {cols} FROM {table}" + (f" WHERE {where}" if where else "")
    try:
        df = pd.read_sql_query(sql, engine, params=list(params or ()), parse_dates=parse_dates)
    except (ProgrammingError, OperationalError) as e:
        # If table missing, return empty DataFrame with headers from config
        msg = str(getattr(e, "orig", e))
        if (
            "doesn't exist" in msg.lower()
            or "no such table" in msg.lower()
            or "undefined table" in msg.lower()
        ):
            if cols.strip() != "*":
                headers = [c.strip().strip("`\"") for c in cols.split(",") if c.strip()]
            else:
                headers = _TABLE_HEADERS.get(table, [])

            if parse_dates:
                for col in parse_dates:
                    if col not in headers:
                        headers.append(col)

            logging.warning(
                "Table '%s' missing. Returning empty DataFrame with headers from config: %s",
                table,
                headers,
            )
            df = pd.DataFrame(columns=headers)
        else:
            raise
    _df_cache[key] = (now + ttl, df)
    return df.copy(deep=False)


def clear_cache(table: Optional[str] = None) -> None:
    """Clear entire cache or entries for a specific table."""
    if table is None:
        _df_cache.clear()
        return
    to_delete = [k for k in _df_cache.keys() if k[0] == table]
    for k in to_delete:
        _df_cache.pop(k, None)
