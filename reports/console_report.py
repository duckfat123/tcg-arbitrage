from rich import box
from rich.console import Console
from rich.table import Table

from core.models import Opportunity

console = Console()


def print_opportunities(opportunities: list[Opportunity], total_scanned: int = 0) -> None:
    if not opportunities:
        console.print("[yellow]No opportunities found above threshold.[/yellow]")
        if total_scanned:
            console.print(f"[dim]Scanned {total_scanned} cards.[/dim]")
        return

    table = Table(
        title="TCG Arbitrage Opportunities",
        box=box.HEAVY_EDGE,
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Card", style="bold white", min_width=24)
    table.add_column("Set", style="dim", min_width=14)
    table.add_column("Game", style="dim", width=10)
    table.add_column("TCG Mkt", justify="right", style="cyan", width=9)
    table.add_column("eBay Med", justify="right", style="yellow", width=9)
    table.add_column("Cost", justify="right", style="white", width=8)
    table.add_column("Profit", justify="right", width=9)
    table.add_column("ROI %", justify="right", width=10)
    table.add_column("Comps", justify="right", style="dim", width=6)

    for opp in opportunities:
        if opp.roi_pct >= 30:
            color = "bold green"
            roi_badge = " ✅"
        elif opp.roi_pct >= 20:
            color = "green"
            roi_badge = " ✅"
        else:
            color = "white"
            roi_badge = ""

        table.add_row(
            opp.card_name,
            opp.set_name or "—",
            opp.game,
            f"${opp.tcg_market:.2f}",
            f"${opp.ebay_median:.2f}",
            f"${opp.total_cost:.2f}",
            f"[{color}]${opp.gross_profit:.2f}[/{color}]",
            f"[{color}]{opp.roi_pct:.1f}%{roi_badge}[/{color}]",
            str(opp.ebay_comps_count),
        )

    console.print(table)
    console.print(
        f"[bold]Scanned {total_scanned} cards | {len(opportunities)} opportunities found[/bold]"
    )
