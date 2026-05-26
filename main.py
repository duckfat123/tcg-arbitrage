import argparse
import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
)

from core.database import (
    add_to_watchlist,
    get_recent_opportunities,
    get_watchlist,
    init_db,
    seed_watchlist_from_csv,
)
from core.models import Card
from reports.console_report import console, print_opportunities
from reports.csv_report import export_csv
from scanner import run_scan

WATCHLIST_CSV = os.path.join(os.path.dirname(__file__), "watchlist.csv")


def cmd_scan(args: argparse.Namespace) -> None:
    init_db()
    seeded = seed_watchlist_from_csv(WATCHLIST_CSV)
    if seeded:
        console.print(f"[green]Seeded {seeded} cards from watchlist.csv[/green]")

    console.print("[cyan]Starting scan...[/cyan]")
    opportunities = run_scan(
        game=args.game,
        min_profit_override=args.min_profit,
    )
    watchlist = get_watchlist(game=args.game)
    print_opportunities(opportunities, total_scanned=len(watchlist))

    if opportunities or args.export:
        path = export_csv(opportunities)
        console.print(f"[dim]CSV exported: {path}[/dim]")


def cmd_report(args: argparse.Namespace) -> None:
    init_db()
    opportunities = get_recent_opportunities(limit=50)
    watchlist = get_watchlist()
    print_opportunities(opportunities, total_scanned=len(watchlist))
    if args.export:
        path = export_csv(opportunities)
        console.print(f"[dim]CSV exported: {path}[/dim]")


def cmd_add(args: argparse.Namespace) -> None:
    init_db()
    card = Card(card_name=args.name, game=args.game, set_name=args.set)
    add_to_watchlist(card)
    console.print(f"[green]Added '{args.name}' ({args.game}) to watchlist.[/green]")


def cmd_watchlist(_args: argparse.Namespace) -> None:
    init_db()
    cards = get_watchlist()
    if not cards:
        console.print("[yellow]Watchlist is empty.[/yellow]")
        return
    for card in cards:
        set_str = f" — {card.set_name}" if card.set_name else ""
        console.print(f"  [cyan]{card.card_name}[/cyan]{set_str} [{card.game}]")
    console.print(f"\n[dim]{len(cards)} cards total[/dim]")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tcg-arb",
        description="TCG Arbitrage Scanner — eBay sold comps → TCGPlayer",
    )
    sub = parser.add_subparsers(dest="command")

    p_scan = sub.add_parser("scan", help="Run full scan of watchlist")
    p_scan.add_argument("--game", choices=["pokemon", "one-piece"], help="Filter by game")
    p_scan.add_argument("--min-profit", type=float, dest="min_profit", metavar="DOLLARS",
                        help="Override MIN_PROFIT_DOLLARS for this run")
    p_scan.add_argument("--export", action="store_true", help="Export CSV even with no results")

    p_report = sub.add_parser("report", help="Show last scan results from DB")
    p_report.add_argument("--export", action="store_true", help="Export results to CSV")

    p_add = sub.add_parser("add", help="Add a card to the watchlist")
    p_add.add_argument("name", help="Card name")
    p_add.add_argument("--set", default=None, metavar="SET_NAME")
    p_add.add_argument("--game", choices=["pokemon", "one-piece"], default="pokemon")

    sub.add_parser("watchlist", help="Print current watchlist")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    dispatch = {
        "scan": cmd_scan,
        "report": cmd_report,
        "add": cmd_add,
        "watchlist": cmd_watchlist,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
