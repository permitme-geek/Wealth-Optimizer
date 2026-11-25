#!/usr/bin/env python3
"""
cli.py — WealthOS Command-Line Interface
Your daily wealth optimization terminal.

Usage:
  python cli.py seed          # First run: load your numbers into the database
  python cli.py sync          # Pull live data from Mono + Paystack
  python cli.py status        # Show current portfolio snapshot
  python cli.py optimize      # Run full optimization + recommendations
  python cli.py project       # Run 10,000-path Monte Carlo projection
  python cli.py next-naira    # Answer: where does the next ₦1 go?
  python cli.py report        # Full report (status + optimize + project)
"""
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich import box
from rich.progress import Progress, SpinnerColumn, TextColumn
import time

app     = typer.Typer(help="WealthOS — Real-time AI wealth optimization")
console = Console()


# ── Formatting helpers ────────────────────────────────────────
def naira(n: float) -> str:
    if n is None: return "₦0"
    if abs(n) >= 1e9: return f"₦{n/1e9:.2f}B"
    if abs(n) >= 1e6: return f"₦{n/1e6:.2f}M"
    if abs(n) >= 1e3: return f"₦{n/1e3:.0f}K"
    return f"₦{n:,.0f}"

def pct(n: float, decimals: int = 1) -> str:
    return f"{n*100:.{decimals}f}%"

def score_color(s: int) -> str:
    if s >= 75: return "bright_green"
    if s >= 55: return "yellow"
    return "red"

def sharpe_color(s: float) -> str:
    if s >= 1.5: return "bright_green"
    if s >= 1.0: return "yellow"
    return "red"


# ── seed command ──────────────────────────────────────────────
@app.command()
def seed(
    hysa:        float = typer.Option(None, prompt="Wema HYSA balance (₦)"),
    yield_rate:  float = typer.Option(None, prompt="HYSA annual yield rate (e.g. 0.105 for 10.5%)"),
    equities:    float = typer.Option(None, prompt="NSE Equities value (₦)"),
    bonds:       float = typer.Option(None, prompt="FGN Bonds value (₦)"),
    mkt:         float = typer.Option(None, prompt="Money market / T-bills value (₦)"),
    other:       float = typer.Option(None, prompt="Other assets (₦)"),
    income:      float = typer.Option(None, prompt="Average monthly income (₦)"),
    expenses:    float = typer.Option(None, prompt="Average monthly expenses (₦)"),
):
    """Manually seed your financial data (first-run setup or manual override)."""
    from state.manager import state_manager, FinancialState
    from datetime import datetime, timezone

    state = FinancialState(
        hysa_balance          = hysa,
        hysa_yield_rate       = yield_rate,
        equities_value        = equities,
        bonds_value           = bonds,
        money_market_value    = mkt,
        other_assets_value    = other,
        monthly_income_avg    = income,
        monthly_expense_avg   = expenses,
        data_source           = "manual",
        last_synced           = datetime.now(timezone.utc).isoformat(),
    )
    state_manager.save(state)

    console.print(Panel(
        f"[bright_green]✓ Seeded successfully[/bright_green]\n"
        f"Net worth: [bold]{naira(state.total_net_worth)}[/bold]\n"
        f"Monthly surplus: [bold]{naira(state.monthly_surplus)}[/bold]",
        title="[bold]WealthOS — Data Seeded[/bold]",
        border_style="bright_green",
    ))


# ── sync command ──────────────────────────────────────────────
@app.command()
def sync():
    """Pull live data from Mono (Wema Bank) and Paystack. Requires API keys in .env"""
    from connectors.mono     import sync_mono
    from connectors.paystack import sync_paystack
    from config import settings

    console.print("\n[bold cyan]WealthOS Sync[/bold cyan]\n")

    # Mono
    if settings.mono_configured:
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                      console=console, transient=True) as p:
            p.add_task("Connecting to Wema Bank via Mono…", total=None)
            result = sync_mono()

        if result["success"]:
            console.print(
                f"[green]✓ Mono[/green] — {result['institution']} "
                f"| Balance: [bold]{naira(result['balance'])}[/bold] "
                f"| +{result['new_txns']} new transactions"
            )
        else:
            console.print(f"[red]✗ Mono[/red] — {result['error']}")
    else:
        console.print("[yellow]⚠ Mono not configured — add MONO_SECRET_KEY + MONO_ACCOUNT_ID to .env[/yellow]")

    # Paystack
    if settings.paystack_configured:
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                      console=console, transient=True) as p:
            p.add_task("Fetching Paystack income data…", total=None)
            result = sync_paystack()

        if result["success"]:
            console.print(
                f"[green]✓ Paystack[/green] — {result['receipts']} receipts "
                f"| Total: [bold]{naira(result['total_income'])}[/bold] "
                f"| +{result['new_txns']} new transactions"
            )
        else:
            console.print(f"[red]✗ Paystack[/red] — {result['error']}")
    else:
        console.print("[yellow]⚠ Paystack not configured — add PAYSTACK_SECRET_KEY to .env[/yellow]")

    console.print()


# ── status command ────────────────────────────────────────────
@app.command()
def status():
    """Show current portfolio snapshot."""
    from state.manager import state_manager

    s = state_manager.get()
    _print_status(s)


def _print_status(s):
    """Shared status display used by status and report commands."""
    from datetime import datetime

    synced = s.last_synced[:10] if s.last_synced else "not synced"

    # ── Top metrics panels ─────────────────────────────────────
    metrics = [
        Panel(f"[bold white]{naira(s.total_net_worth)}[/bold white]\n[dim]last synced: {synced}[/dim]",
              title="Net Worth", border_style="cyan"),
        Panel(f"[bold]{naira(s.hysa_balance)}[/bold]\n[dim]{pct(s.hysa_yield_rate)} p.a.[/dim]",
              title="Wema HYSA", border_style="blue"),
        Panel(f"[bold]{naira(s.monthly_surplus)}/mo[/bold]\n[dim]savings rate: {pct(s.savings_rate)}[/dim]",
              title="Monthly Surplus", border_style="green" if s.monthly_surplus >= 0 else "red"),
        Panel(f"[bold]{s.liquid_months:.1f} months[/bold]\n[dim]{'✓ Safe' if s.liquid_months >= 3 else '⚠ Low'}[/dim]",
              title="Liquidity Buffer", border_style="green" if s.liquid_months >= 3 else "yellow"),
    ]
    console.print(Columns(metrics))
    console.print()

    # ── Allocation table ───────────────────────────────────────
    alloc = s.allocation
    table = Table(title="Current Allocation", box=box.ROUNDED, border_style="dim")
    table.add_column("Asset",   style="bold white", width=14)
    table.add_column("Value",   justify="right", style="cyan")
    table.add_column("Weight",  justify="right")
    table.add_column("Real Return", justify="right")

    asset_vals = {
        "HYSA":        s.hysa_balance,
        "Equities":    s.equities_value,
        "Bonds":       s.bonds_value,
        "MoneyMarket": s.money_market_value,
        "Other":       s.other_assets_value,
    }
    real_returns = {
        "HYSA":        s.real_hysa_return(),
        "Equities":    (1.16) / (1 + 0.30) - 1,
        "Bonds":       (1.145) / (1 + 0.30) - 1,
        "MoneyMarket": (1.15) / (1 + 0.30) - 1,
        "Other":       0.0,
    }
    for asset, val in asset_vals.items():
        w      = alloc.get(asset, 0)
        rr     = real_returns.get(asset, 0)
        rr_str = f"[red]{pct(rr)}[/red]" if rr < 0 else f"[green]{pct(rr)}[/green]"
        table.add_row(asset, naira(val), pct(w), rr_str)

    console.print(table)
    console.print()


# ── optimize command ──────────────────────────────────────────
@app.command()
def optimize():
    """Run Markowitz MVO + Kelly + next-₦1 optimization. Shows recommendations."""
    from state.manager      import state_manager
    from optimization.engine import OptimizationEngine

    s = state_manager.get()

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  console=console, transient=True) as p:
        p.add_task("Running Markowitz MVO + Kelly Criterion…", total=None)
        engine = OptimizationEngine()
        result = engine.run(s)

    _print_optimization(s, result)


def _print_optimization(s, result):
    """Shared optimization display used by optimize and report commands."""
    # ── Health score + key metrics ─────────────────────────────
    sc    = result.health_score
    color = score_color(sc)
    sh_color = sharpe_color(result.sharpe_ratio)

    summary_panels = [
        Panel(f"[bold {color}]{sc}/100[/bold {color}]",
              title="Health Score", border_style=color),
        Panel(f"[bold {sh_color}]{result.sharpe_ratio:.2f}[/bold {sh_color}]\n"
              f"[dim]{'✓ Target met' if result.sharpe_ratio >= 1.5 else '⚠ Below 1.5'}[/dim]",
              title="Sharpe Ratio", border_style=sh_color),
        Panel(f"[bold cyan]{pct(result.expected_annual_return)}[/bold cyan]\n"
              f"[dim]vol: {pct(result.annual_volatility)}[/dim]",
              title="Annual Return", border_style="cyan"),
        Panel(f"[bold green]+{naira(result.wealth_velocity_daily)}/day[/bold green]\n"
              f"[dim]real: {pct(result.real_annual_return)}[/dim]",
              title="Wealth Velocity", border_style="green"),
    ]
    console.print(Columns(summary_panels))
    console.print()

    # ── Health score breakdown ─────────────────────────────────
    bd = result.health_breakdown
    hb = Table(title="Health Score Breakdown", box=box.SIMPLE, border_style="dim")
    hb.add_column("Dimension",  style="white", width=18)
    hb.add_column("Score",      justify="right", width=8)
    hb.add_column("Max",        justify="right", width=6)
    for name, pts in bd.items():
        max_pts = {"sharpe":25,"liquidity":20,"savings_rate":20,"diversification":15,"real_return":20}.get(name,0)
        bar = "█" * int(pts / max_pts * 10) if max_pts > 0 else ""
        color = "green" if pts >= max_pts * 0.7 else "yellow" if pts >= max_pts * 0.4 else "red"
        hb.add_row(name.replace("_"," ").title(), f"[{color}]{pts:.1f}[/{color}]", str(max_pts))
    console.print(hb)
    console.print()

    # ── Optimal vs current allocation ─────────────────────────
    alloc_table = Table(title="Allocation — Current vs Optimal (MVO)", box=box.ROUNDED)
    alloc_table.add_column("Asset",        style="bold", width=14)
    alloc_table.add_column("Current",      justify="right")
    alloc_table.add_column("Optimal",      justify="right")
    alloc_table.add_column("Action",       justify="right")
    for asset in ["HYSA","Equities","Bonds","MoneyMarket"]:
        cur = result.current_weights.get(asset, 0)
        opt = result.weights.get(asset, 0)
        diff = opt - cur
        if abs(diff) < 0.005:
            action = "[dim]hold[/dim]"
        elif diff > 0:
            action = f"[green]+{pct(diff)}[/green]"
        else:
            action = f"[red]{pct(diff)}[/red]"
        alloc_table.add_row(asset, pct(cur), pct(opt), action)
    console.print(alloc_table)
    console.print()

    # ── Rebalancing moves ──────────────────────────────────────
    if result.rebalancing_moves:
        console.print("[bold]Rebalancing Signals[/bold]")
        for move in result.rebalancing_moves:
            arrow  = "[green]↑[/green]" if move["direction"] == "increase" else "[red]↓[/red]"
            drift  = move["drift_pct"]
            color  = "green" if drift > 0 else "red"
            console.print(
                f"  {arrow} [bold]{move['asset']:12}[/bold] "
                f"[{color}]{move['from_pct']:.1f}% → {move['to_pct']:.1f}%[/{color}]  "
                f"({naira(move['amount'])})"
            )
        console.print()

    # ── Next ₦1 ───────────────────────────────────────────────
    console.print(Panel(
        f"[bold bright_green]{result.next_naira_asset}[/bold bright_green]\n"
        f"[dim]Maximises CRRA marginal utility at γ = {s.__class__.__module__ and 2.5}[/dim]\n"
        f"Deployable surplus: [bold]{naira(result.surplus_to_deploy)}[/bold]",
        title="[bold]▶ Next ₦1 Goes To[/bold]",
        border_style="bright_green",
    ))
    console.print()

    # ── Kelly fractions ────────────────────────────────────────
    kelly_table = Table(title="Kelly Criterion — Surplus Sizing (Quarter-Kelly)", box=box.SIMPLE)
    kelly_table.add_column("Asset",    style="bold", width=14)
    kelly_table.add_column("Fraction", justify="right")
    kelly_table.add_column("₦ Amount", justify="right")
    surplus = result.surplus_to_deploy
    for asset, frac in result.kelly_fractions.items():
        amount = frac * surplus
        kelly_table.add_row(asset, pct(frac), naira(amount))
    console.print(kelly_table)
    console.print()


# ── project command ───────────────────────────────────────────
@app.command()
def project(
    months: int = typer.Option(60, help="Projection horizon in months"),
):
    """Run Monte Carlo wealth projection (10,000 paths)."""
    from state.manager         import state_manager
    from optimization.engine   import OptimizationEngine
    from simulation.monte_carlo import MonteCarloEngine
    from config import settings

    s = state_manager.get()

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  console=console, transient=True) as p:
        p.add_task(f"Running 10,000 Monte Carlo paths × {months} months…", total=None)

        engine = OptimizationEngine()
        opt    = engine.run(s)
        mc     = MonteCarloEngine(n_paths=10_000)
        proj   = mc.run(
            initial_wealth       = s.total_net_worth,
            weights              = opt.weights,
            monthly_contribution = max(s.monthly_surplus, 0),
            n_months             = months,
            wealth_goal          = settings.wealth_goal,
        )

    _print_projection(s, proj)


def _print_projection(s, proj):
    """Shared projection display."""
    years = proj.n_months // 12
    console.print(f"\n[bold]Monte Carlo Wealth Projection — {proj.n_months} months ({years} years)[/bold]")
    console.print(f"[dim]{proj.n_paths:,} simulated paths | "
                  f"₦{proj.monthly_contribution:,.0f}/mo contribution[/dim]\n")

    # ── Milestone table ────────────────────────────────────────
    table = Table(box=box.ROUNDED, border_style="cyan")
    table.add_column("Scenario",    style="bold",    width=16)
    table.add_column("1 Year",      justify="right", width=14)
    table.add_column("3 Years",     justify="right", width=14)
    table.add_column("5 Years",     justify="right", width=14)

    milestones = {12: proj.p10, 36: proj.p10, 60: proj.p10}   # placeholder

    rows = [
        ("Bear  (P10)",  proj.p10,  "red"),
        ("Base  (P50)",  proj.p50,  "cyan"),
        ("Bull  (P90)",  proj.p90,  "green"),
    ]
    for label, curve, color in rows:
        m12 = int(min(12, len(curve)-1))
        m36 = int(min(36, len(curve)-1))
        m60 = int(min(60, len(curve)-1))
        table.add_row(
            f"[{color}]{label}[/{color}]",
            f"[{color}]{naira(curve[m12])}[/{color}]",
            f"[{color}]{naira(curve[m36])}[/{color}]",
            f"[{color}]{naira(curve[m60])}[/{color}]",
        )
    console.print(table)
    console.print()

    # ── Goal progress ──────────────────────────────────────────
    goal_color = "green" if proj.prob_reaching_goal >= 0.5 else "yellow" if proj.prob_reaching_goal >= 0.25 else "red"
    exp_months = proj.expected_months_to_goal
    exp_str    = f"{exp_months:.0f} months ({exp_months/12:.1f} yrs)" if exp_months < 600 else "beyond horizon"

    console.print(Panel(
        f"Goal: [bold]{naira(proj.wealth_goal)}[/bold]\n"
        f"Probability of reaching goal: [{goal_color}][bold]{proj.prob_reaching_goal*100:.0f}%[/bold][/{goal_color}]\n"
        f"Expected time to goal (median path): [bold]{exp_str}[/bold]\n"
        f"Median CAGR: [bold]{pct(proj.cagr())}[/bold] nominal  |  "
        f"[bold]{pct(proj.real_cagr())}[/bold] real",
        title="[bold]Goal Analysis[/bold]",
        border_style=goal_color,
    ))
    console.print()


# ── next-naira command ────────────────────────────────────────
@app.command(name="next-naira")
def next_naira():
    """Answer: where should the next ₦1 go right now?"""
    from state.manager       import state_manager
    from optimization.engine  import OptimizationEngine

    s      = state_manager.get()
    engine = OptimizationEngine()
    result = engine.run(s)

    console.print(Panel(
        f"[bold bright_green]→ {result.next_naira_asset}[/bold bright_green]\n\n"
        f"Monthly surplus available: [bold]{naira(result.surplus_to_deploy)}[/bold]\n\n"
        f"[bold]Kelly Criterion deployment:[/bold]\n" +
        "\n".join(
            f"  {a}: {pct(f)} → {naira(f * result.surplus_to_deploy)}"
            for a, f in result.kelly_fractions.items()
        ),
        title="[bold]Where does the next ₦1 go?[/bold]",
        border_style="bright_green",
        expand=False,
    ))


# ── report command ────────────────────────────────────────────
@app.command()
def report(save: bool = typer.Option(False, "--save", help="Save report to file")):
    """Full WealthOS report: status + optimization + Monte Carlo projection."""
    from state.manager         import state_manager
    from optimization.engine   import OptimizationEngine
    from simulation.monte_carlo import MonteCarloEngine
    from config import settings

    s = state_manager.get()

    console.rule("[bold cyan]WealthOS — Full Optimization Report[/bold cyan]")
    console.print()

    # Status
    console.print("[bold]── Portfolio Status ──[/bold]")
    _print_status(s)

    # Optimize
    console.print("[bold]── Mathematical Optimization ──[/bold]")
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console, transient=True) as p:
        p.add_task("Running MVO + Kelly…", total=None)
        engine = OptimizationEngine()
        result = engine.run(s)
    _print_optimization(s, result)

    # Project
    console.print("[bold]── Monte Carlo Projection ──[/bold]")
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console, transient=True) as p:
        p.add_task("Simulating 10,000 paths…", total=None)
        mc   = MonteCarloEngine(n_paths=10_000)
        proj = mc.run(
            initial_wealth       = s.total_net_worth,
            weights              = result.weights,
            monthly_contribution = max(s.monthly_surplus, 0),
            n_months             = 60,
            wealth_goal          = settings.wealth_goal,
        )
    _print_projection(s, proj)

    console.rule("[dim]End of Report[/dim]")


if __name__ == "__main__":
    app()
