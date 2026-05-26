import csv
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Generator, Optional

from .models import Card, EbayComp, Opportunity, TcgPrice

DB_PATH = os.getenv(
    "DB_PATH",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "arbitrage.db"),
)


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Open a connection, commit on success, rollback on error, always close."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_name TEXT NOT NULL,
                set_name TEXT,
                game TEXT NOT NULL DEFAULT 'pokemon',
                ebay_query_override TEXT,
                active INTEGER DEFAULT 1,
                added_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS tcg_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_name TEXT NOT NULL,
                set_name TEXT,
                game TEXT,
                market_price REAL,
                low_price REAL,
                fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS ebay_comps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                search_query TEXT NOT NULL,
                avg_price REAL,
                median_price REAL,
                min_price REAL,
                max_price REAL,
                num_results INTEGER,
                fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS opportunities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_name TEXT NOT NULL,
                set_name TEXT,
                game TEXT,
                tcg_market REAL,
                ebay_median REAL,
                tcg_net_payout REAL,
                total_cost REAL,
                gross_profit REAL,
                roi_pct REAL,
                ebay_comps_count INTEGER,
                scanned_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS scan_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cards_scanned INTEGER NOT NULL,
                opps_found INTEGER NOT NULL,
                scanned_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)


def seed_watchlist_from_csv(csv_path: str) -> int:
    with get_db() as conn:
        existing = conn.execute("SELECT COUNT(*) FROM watchlist").fetchone()[0]
        if existing > 0:
            return 0

    count = 0
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        with get_db() as conn:
            for row in reader:
                override = row.get("ebay_search_query_override", "").strip() or None
                conn.execute(
                    "INSERT INTO watchlist (card_name, set_name, game, ebay_query_override) VALUES (?, ?, ?, ?)",
                    (
                        row["card_name"].strip(),
                        row.get("set_name", "").strip() or None,
                        row.get("game", "pokemon").strip(),
                        override,
                    ),
                )
                count += 1
    return count


def get_watchlist(game: Optional[str] = None) -> list[Card]:
    with get_db() as conn:
        if game:
            rows = conn.execute(
                "SELECT * FROM watchlist WHERE active=1 AND game=?", (game,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM watchlist WHERE active=1").fetchall()
    return [
        Card(
            card_name=r["card_name"],
            game=r["game"],
            set_name=r["set_name"],
            ebay_query_override=r["ebay_query_override"],
        )
        for r in rows
    ]


def add_to_watchlist(card: Card) -> None:
    with get_db() as conn:
        conn.execute(
            "INSERT INTO watchlist (card_name, set_name, game, ebay_query_override) VALUES (?, ?, ?, ?)",
            (card.card_name, card.set_name, card.game, card.ebay_query_override),
        )


def get_cached_tcg_price(
    card_name: str,
    game: str,
    set_name: Optional[str] = None,
    max_age_hours: int = 24,
) -> Optional[TcgPrice]:
    cutoff = (datetime.now() - timedelta(hours=max_age_hours)).isoformat()
    with get_db() as conn:
        if set_name:
            row = conn.execute(
                "SELECT * FROM tcg_prices WHERE card_name=? AND game=? AND set_name=? AND fetched_at > ?"
                " ORDER BY fetched_at DESC LIMIT 1",
                (card_name, game, set_name, cutoff),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM tcg_prices WHERE card_name=? AND game=? AND fetched_at > ?"
                " ORDER BY fetched_at DESC LIMIT 1",
                (card_name, game, cutoff),
            ).fetchone()
    if not row:
        return None
    return TcgPrice(
        card_name=row["card_name"],
        game=row["game"],
        set_name=row["set_name"],
        market_price=row["market_price"],
        low_price=row["low_price"],
        fetched_at=datetime.fromisoformat(row["fetched_at"]),
    )


def save_tcg_price(price: TcgPrice) -> None:
    with get_db() as conn:
        conn.execute(
            "INSERT INTO tcg_prices (card_name, set_name, game, market_price, low_price, fetched_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                price.card_name,
                price.set_name,
                price.game,
                price.market_price,
                price.low_price,
                price.fetched_at.isoformat(),
            ),
        )


def get_cached_ebay_comp(query: str, max_age_hours: int = 6) -> Optional[EbayComp]:
    cutoff = (datetime.now() - timedelta(hours=max_age_hours)).isoformat()
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM ebay_comps WHERE search_query=? AND fetched_at > ?"
            " ORDER BY fetched_at DESC LIMIT 1",
            (query, cutoff),
        ).fetchone()
    if not row:
        return None
    return EbayComp(
        search_query=row["search_query"],
        avg_price=row["avg_price"],
        median_price=row["median_price"],
        min_price=row["min_price"],
        max_price=row["max_price"],
        num_results=row["num_results"],
        fetched_at=datetime.fromisoformat(row["fetched_at"]),
    )


def save_ebay_comp(comp: EbayComp) -> None:
    with get_db() as conn:
        conn.execute(
            "INSERT INTO ebay_comps (search_query, avg_price, median_price, min_price, max_price, num_results, fetched_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                comp.search_query,
                comp.avg_price,
                comp.median_price,
                comp.min_price,
                comp.max_price,
                comp.num_results,
                comp.fetched_at.isoformat(),
            ),
        )


def save_opportunity(opp: Opportunity) -> None:
    with get_db() as conn:
        conn.execute(
            """INSERT INTO opportunities
               (card_name, set_name, game, tcg_market, ebay_median, tcg_net_payout,
                total_cost, gross_profit, roi_pct, ebay_comps_count, scanned_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                opp.card_name,
                opp.set_name,
                opp.game,
                opp.tcg_market,
                opp.ebay_median,
                opp.tcg_net_payout,
                opp.total_cost,
                opp.gross_profit,
                opp.roi_pct,
                opp.ebay_comps_count,
                opp.scanned_at.isoformat(),
            ),
        )


def log_scan(cards_scanned: int, opps_found: int) -> None:
    with get_db() as conn:
        conn.execute(
            "INSERT INTO scan_log (cards_scanned, opps_found) VALUES (?, ?)",
            (cards_scanned, opps_found),
        )


def get_last_scans(limit: int = 10) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM scan_log ORDER BY scanned_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_recent_opportunities(limit: int = 50) -> list[Opportunity]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM opportunities ORDER BY scanned_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [
        Opportunity(
            card_name=r["card_name"],
            game=r["game"],
            set_name=r["set_name"],
            tcg_market=r["tcg_market"],
            ebay_median=r["ebay_median"],
            tcg_net_payout=r["tcg_net_payout"],
            total_cost=r["total_cost"],
            gross_profit=r["gross_profit"],
            roi_pct=r["roi_pct"],
            ebay_comps_count=r["ebay_comps_count"],
            scanned_at=datetime.fromisoformat(r["scanned_at"]),
        )
        for r in rows
    ]
