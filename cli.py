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
import os
import plistlib
import sys
import subprocess
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

app     = typer.Typer(help="WealthOS — Real-time AI wealth optimization")
console = Console()


def _write_env_values(values: dict[str, str]) -> None:
    env_path = Path(__file__).resolve().parent / ".env"
    lines = env_path.read_text().splitlines() if env_path.exists() else []
    keys = set(values)
    lines = [line for line in lines if not any(line.startswith(f"{key}=") for key in keys)]
    lines.extend(f"{key}={value}" for key, value in values.items())
    env_path.write_text("\n".join(lines) + "\n")
    os.chmod(env_path, 0o600)
    os.environ.update(values)


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


@app.command()
def setup():
    """Personalize WealthOS, configure optional account connectors, KPIs and goals."""
    from state.manager import state_manager, FinancialState
    console.print(Panel("Set up your profile, financial baseline, goals and optional integrations.", title="WealthOS First Run"))
    display_name = typer.prompt("Name for reports", default="User")
    timezone_name = typer.prompt("Report timezone", default="Africa/Lagos")
    try:
        ZoneInfo(timezone_name)
    except Exception as exc:
        raise typer.BadParameter("Enter a valid IANA timezone such as Africa/Lagos") from exc
    income = typer.prompt("Monthly income baseline (NGN)", type=float, default=0.0)
    expenses = typer.prompt("Monthly expense baseline (NGN)", type=float, default=0.0)
    hysa = typer.prompt("Bank cash balance (NGN)", type=float, default=0.0)
    equities = typer.prompt("Equities value (NGN)", type=float, default=0.0)
    bonds = typer.prompt("Bonds value (NGN)", type=float, default=0.0)
    mkt = typer.prompt("Money market/T-bills value (NGN)", type=float, default=0.0)
    other = typer.prompt("Other assets (NGN)", type=float, default=0.0)
    wealth_goal = typer.prompt("Net-worth goal (NGN)", type=float, default=50_000_000.0)
    target_monthly_income = typer.prompt("Target monthly income KPI (NGN)", type=float, default=income)
    skills = typer.prompt("Skills you can sell", default="")
    offers = typer.prompt("Products/services you can offer", default="")
    customers = typer.prompt("Target customers", default="")
    pricing = typer.prompt("Pricing/cost constraints", default="")
    resources = typer.prompt("Useful resources and available time", default="")
    channels = typer.prompt("Preferred customer channels", default="")
    mono_key = typer.prompt("Mono secret key (blank to configure later)", default="", hide_input=True)
    mono_id = typer.prompt("Mono account ID (blank to configure later)", default="")
    paystack_key = typer.prompt("Paystack secret key (blank to configure later)", default="", hide_input=True)
    email_to = typer.prompt("Email for daily reports (blank disables email)", default="")
    smtp_host = smtp_user = smtp_password = ""
    smtp_port = "587"
    if email_to:
        smtp_host = typer.prompt("SMTP host")
        smtp_port = str(typer.prompt("SMTP port", type=int, default=587))
        smtp_user = typer.prompt("SMTP username", default="")
        smtp_password = typer.prompt("SMTP password/app password", default="", hide_input=True)
    env_values = {"WEALTHOS_TIMEZONE": timezone_name,
        "WEALTH_GOAL": str(wealth_goal), "MONTHLY_INCOME_TARGET": str(target_monthly_income)}
    env_values.update({k: v for k, v in {"MONO_SECRET_KEY": mono_key, "MONO_ACCOUNT_ID": mono_id,
        "PAYSTACK_SECRET_KEY": paystack_key, "REPORT_EMAIL_TO": email_to,
        "SMTP_HOST": smtp_host, "SMTP_PORT": smtp_port, "SMTP_USERNAME": smtp_user,
        "SMTP_PASSWORD": smtp_password}.items() if v})
    _write_env_values(env_values)
    state_manager.save(FinancialState(hysa_balance=hysa, equities_value=equities,
        bonds_value=bonds, money_market_value=mkt, other_assets_value=other,
        monthly_income_avg=income, monthly_expense_avg=expenses,
        data_source="manual", last_synced=datetime.now().astimezone().isoformat()))
    state_manager.save_profile(display_name=display_name, skills=skills, offers=offers,
        target_customers=customers, pricing_notes=pricing, resources=resources,
        available_hours=0, preferred_channels=channels)
    state_manager.add_goal("Net worth target", wealth_goal, "")
    console.print("[green]Setup saved. Configure the 8 AM report with `python cli.py daily-schedule`.\n"
                  "Credentials are stored in the local .env file with owner-only permissions.[/green]")


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
        Panel(f"[bold {color}]{sc}/100[/bold {color}]\n[dim]verified outcome rating[/dim]",
              title="Wealth Rating", border_style=color),
        Panel(f"[bold {sh_color}]{result.sharpe_ratio:.2f}[/bold {sh_color}]\n"
              f"[dim]{'✓ Target met' if result.sharpe_ratio >= 1.5 else '⚠ Below 1.5'}[/dim]",
              title="Sharpe Ratio", border_style=sh_color),
        Panel(f"[bold cyan]{pct(result.expected_annual_return)}[/bold cyan]\n"
              f"[dim]modelled; vol: {pct(result.annual_volatility)}[/dim]",
              title="Projected Portfolio Return", border_style="cyan"),
        Panel(f"[bold green]~{naira(result.wealth_velocity_daily)}/day[/bold green]\n"
              f"[dim]modelled real return: {pct(result.real_annual_return)}[/dim]",
              title="Projected Investment Growth", border_style="green"),
    ]
    console.print(Columns(summary_panels))
    console.print()

    # ── Health score breakdown ─────────────────────────────────
    bd = result.health_breakdown
    hb = Table(title="Wealth Rating Components", box=box.SIMPLE, border_style="dim")
    hb.add_column("Dimension",  style="white", width=18)
    hb.add_column("Score",      justify="right", width=8)
    hb.add_column("Max",        justify="right", width=6)
    for name, pts in bd.items():
        max_pts = {"verified_net_earnings":50,"completed_sales":20,
                   "closed_sale_conversion":15,"profitability":15}.get(name,0)
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

    _print_earning_actions(s)


def _print_earning_actions(s):
    from state.manager import state_manager
    m = state_manager.wealth_metrics(s)
    active = [o for o in m["opportunities"] if o["status"] not in {"won", "lost", "refunded"}]
    console.print("[bold]Highest-value earning actions[/bold]")
    if active:
        active.sort(key=lambda o: (o["next_follow_up"] or "9999-99-99", -o["quoted_amount"]))
        for o in active[:3]:
            console.print(f"  #{o['id']} {o['customer']}: follow up through {o['channel'] or 'last contact channel'} "
                          f"on {o['offer']} ({naira(o['quoted_amount'])}); resolve the main objection and agree a dated next step.\n"
                          f"     Script: ‘Hi {o['customer']}, checking in on {o['offer']}. Is [specific outcome] still a priority? "
                          "I can answer questions or adjust the scope; would [date/time] work to decide?’")
    else:
        p = state_manager.get_profile()
        if p["offers"] or p["skills"]:
            buyer = p["target_customers"] or "a narrow buyer segment that already pays to solve this problem"
            console.print(f"  Package {p['offers'] or p['skills']} as a paid outcome for {buyer}; "
                          f"contact 10 likely buyers via {p['preferred_channels'] or 'your warm network'}, "
                          f"using {p['available_hours']:g} hours/week and resources ({p['resources'] or 'listed skills'}). "
                          f"Price a defined pilot from delivery time and cost{(': ' + p['pricing_notes']) if p['pricing_notes'] else ''}, then ask for a paid engagement.")
        else:
            console.print("  Run `python cli.py wealth-profile` to add your skills, offers, resources, time and channels; then set one paid offer.")
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


@app.command("wealth-profile")
def wealth_profile():
    """Set skills, offers, resources and time used to tailor earning actions."""
    from state.manager import state_manager
    current = state_manager.get_profile()
    skills = typer.prompt("Skills you can sell", default=current["skills"])
    offers = typer.prompt("Products/services or offers you can deliver", default=current["offers"])
    target_customers = typer.prompt("Target customers / buyer segment", default=current["target_customers"])
    pricing_notes = typer.prompt("Price range, costs or pricing constraints", default=current["pricing_notes"])
    resources = typer.prompt("Useful resources (equipment, audience, capital, network)", default=current["resources"])
    hours = typer.prompt("Hours available per week", default=float(current["available_hours"]), type=float)
    channels = typer.prompt("Preferred customer channels", default=current["preferred_channels"])
    state_manager.save_profile(skills=skills, offers=offers,
                               target_customers=target_customers, pricing_notes=pricing_notes,
                               resources=resources,
                               available_hours=hours, preferred_channels=channels)
    console.print("[green]Wealth profile saved. Run `python cli.py wealth` for tailored next steps.[/green]")


@app.command("sales-add")
def sales_add(customer: str = typer.Option(..., prompt=True),
              offer: str = typer.Option(..., prompt=True),
              quoted_amount: float = typer.Option(..., prompt="Quoted price (NGN)", min=0),
              channel: str = typer.Option("", prompt="Channel", show_default=False),
              contact: str = typer.Option("", prompt="Contact details", show_default=False),
              source: str = typer.Option("manual", prompt="Lead source"),
              marketing_activity: str = typer.Option("", prompt="Marketing activity", show_default=False),
              follow_up: str = typer.Option("", prompt="Next follow-up date (YYYY-MM-DD)", show_default=False)):
    """Create a prospect/lead and start its auditable sales trail."""
    from state.manager import state_manager
    oid = state_manager.add_opportunity(customer=customer, offer=offer,
        quoted_amount=quoted_amount, channel=channel, contact=contact, source=source,
        marketing_activity=marketing_activity, next_follow_up=follow_up)
    console.print(f"[green]Created opportunity #{oid}.[/green] Quotes and pipeline are not counted as income.")


@app.command("sales-log")
def sales_log(opportunity_id: int = typer.Argument(...),
              activity: str = typer.Option(..., prompt="Activity (call, follow-up, objection, negotiation, etc.)"),
              notes: str = typer.Option("", prompt="Notes / outcome", show_default=False),
              stage: str = typer.Option(None, help="prospect, lead, opportunity, proposed, accepted, invoiced, won, lost"),
              payment_status: str = typer.Option(None, help="unpaid, pending, partial, refunded"),
              accepted_amount: float = typer.Option(None, help="Accepted deal amount (NGN)"),
              follow_up: str = typer.Option(None, help="Next follow-up date (YYYY-MM-DD)")):
    """Record outreach, responses, objections, negotiation or a stage change."""
    from state.manager import state_manager
    try:
        state_manager.update_opportunity(opportunity_id, activity_type=activity,
            notes=notes, status=stage, amount=accepted_amount,
            payment_status=payment_status, next_follow_up=follow_up)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    console.print(f"[green]Logged activity for opportunity #{opportunity_id}.[/green]")


@app.command("sales-receipt")
def sales_receipt(opportunity_id: int = typer.Argument(...),
                  amount: float = typer.Option(..., prompt="Amount received (NGN)", min=0),
                  reference: str = typer.Option(..., prompt="Bank/payment transaction reference"),
                  payment_date: str = typer.Option("", prompt="Payment date (YYYY-MM-DD; blank=today)", show_default=False),
                  costs: float = typer.Option(0, prompt="Additional costs recorded now (NGN)", min=0)):
    """Record a synced and matched money credit; requires its transaction ID."""
    from state.manager import state_manager
    try:
        state_manager.record_receipt(opportunity_id, amount, reference,
                                     payment_date=payment_date, costs=costs)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    console.print(f"[green]Recorded {naira(amount)} received for opportunity #{opportunity_id}.[/green]")


@app.command("receipt-candidates")
def receipt_candidates():
    """List synced business income credits that can verify sales receipts."""
    from state.manager import state_manager
    rows = state_manager.get_unlinked_business_credits()
    table = Table(title="Unlinked Synced Business Receipts", box=box.ROUNDED)
    for name in ("Transaction ID", "Date", "Source", "Description", "Amount"):
        table.add_column(name, justify="right" if name == "Amount" else "left")
    for row in rows:
        table.add_row(str(row["id"]), row["date"], row["source"], row["narration"], naira(row["amount"]))
    console.print(table)
    if not rows:
        console.print("No unlinked designated-account business credits. Sync Mono and check the account transaction category.")


@app.command("sales-adjust")
def sales_adjust(opportunity_id: int = typer.Argument(...),
                 adjustment: str = typer.Option(..., prompt="Adjustment type (cost or refund)"),
                 amount: float = typer.Option(..., prompt="Amount (NGN)", min=0),
                 notes: str = typer.Option(..., prompt="Reason", show_default=False),
                 reference: str = typer.Option("", prompt="Receipt/reference", show_default=False)):
    """Append a sales cost or refund to the auditable earnings trail."""
    from state.manager import state_manager
    try:
        state_manager.record_adjustment(opportunity_id, adjustment, amount, notes, reference)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    console.print(f"[green]Recorded {adjustment} of {naira(amount)} for opportunity #{opportunity_id}.[/green]")


@app.command("sales-list")
def sales_list():
    """Show sales pipeline stages, accepted amounts and verified receipts."""
    from state.manager import state_manager
    rows = state_manager.list_opportunities()
    table = Table(title="Sales Trail", box=box.ROUNDED)
    for name in ("ID", "Customer", "Offer", "Stage", "Quoted", "Received", "Payment", "Next follow-up"):
        table.add_column(name, justify="right" if name in {"ID", "Quoted", "Received"} else "left")
    for o in rows:
        table.add_row(str(o["id"]), o["customer"], o["offer"], o["status"],
                      naira(o["quoted_amount"]), naira(o["received_amount"]),
                      o["payment_status"], o["next_follow_up"] or "—")
    console.print(table)
    if not rows: console.print("No opportunities yet. Use `python cli.py sales-add` to start a sales trail.")


@app.command("sales-history")
def sales_history(opportunity_id: int = typer.Argument(...)):
    """Show the dated contact, negotiation, follow-up, receipt and adjustment trail."""
    from state.manager import state_manager
    history = state_manager.opportunity_history(opportunity_id)
    if not history:
        console.print(f"No activity found for opportunity #{opportunity_id}.")
        return
    table = Table(title=f"Opportunity #{opportunity_id} Activity Trail", box=box.ROUNDED)
    table.add_column("Date", width=22)
    table.add_column("Activity")
    table.add_column("Amount", justify="right")
    table.add_column("Notes")
    for entry in history:
        table.add_row(entry["occurred_at"][:19].replace("T", " "), entry["activity_type"],
                      naira(entry["amount"]), entry["notes"])
    console.print(table)


@app.command("goal-add")
def goal_add(goal: str = typer.Option(..., prompt=True),
             target_amount: float = typer.Option(0, prompt="Target amount (NGN)", min=0),
             target_date: str = typer.Option("", prompt="Target date (YYYY-MM-DD)", show_default=False)):
    """Add a measurable wealth goal."""
    from state.manager import state_manager
    gid = state_manager.add_goal(goal, target_amount, target_date)
    console.print(f"[green]Saved goal #{gid}: {goal}[/green]")


@app.command("daily-report")
def daily_report():
    """Sync available accounts, compare today's balance with the prior report and issue next actions."""
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env", override=True)
    from state.manager import state_manager
    from config import settings
    timezone_name = os.getenv("WEALTHOS_TIMEZONE", "Africa/Lagos")
    now = datetime.now(ZoneInfo(timezone_name))
    # Sync first so the opening balance reflects the latest available account data.
    sync_messages = []
    try:
        from connectors.mono import sync_mono
        if settings.mono_configured:
            result = sync_mono(verbose=False)
            sync_messages.append(f"Mono sync: {'ok' if result['success'] else result.get('error', 'failed')}")
    except Exception as exc:
        sync_messages.append(f"Mono sync failed: {exc}")
    try:
        from connectors.paystack import sync_paystack
        if settings.paystack_configured:
            result = sync_paystack(verbose=False)
            sync_messages.append(f"Paystack sync: {'ok' if result['success'] else result.get('error', 'failed')}")
    except Exception as exc:
        sync_messages.append(f"Paystack sync failed: {exc}")
    state = state_manager.get()
    balances = state_manager.record_daily_balance(state, now.date().isoformat())
    prev = balances["previous"]
    delta = state.total_net_worth - prev[1] if prev else 0
    metrics = state_manager.wealth_metrics(state)
    profile = state_manager.get_profile()
    lines = [f"WealthOS Daily Brief — {now:%A, %d %B %Y} ({timezone_name})",
             f"Hello {profile.get('display_name') or 'there'}.",
             f"Current balance/net worth: {naira(state.total_net_worth)}",
             f"Previous reported close: {naira(prev[2]) if prev else 'No prior daily close'}",
             f"Change since previous report: {naira(delta)}",
             f"Verified account income this month: {naira(metrics['received_month'])}",
             f"Net realised sales earnings: {naira(metrics['net_realised'])}",
             f"Outstanding receivables (separate): {naira(metrics['outstanding'])}",
             f"Wealth rating: {metrics['rating']}/100", "Sync: " + ("; ".join(sync_messages) or "No connectors configured")]
    goals = state_manager.get_goals()
    if goals:
        lines.append("Goals:")
        for goal in goals:
            gap = max(goal["target_amount"] - state.total_net_worth, 0) if goal["target_amount"] else 0
            lines.append(f"- {goal['goal']}: target {naira(goal['target_amount'])}; remaining {naira(gap)}; due {goal['target_date'] or 'no date'}")
    active = [o for o in metrics["opportunities"] if o["status"] not in {"won", "lost", "refunded"}]
    lines.append("Today's optimized actions:")
    if active:
        active.sort(key=lambda o: (o["next_follow_up"] or "9999-99-99", -o["quoted_amount"]))
        lines.extend(f"- Follow up #{o['id']} with {o['customer']} about {o['offer']} ({naira(o['quoted_amount'])}); resolve their main objection and set a decision date." for o in active[:3])
    elif profile.get("offers") or profile.get("skills"):
        lines.append(f"- Offer {profile['offers'] or profile['skills']} to {profile.get('target_customers') or 'a focused buyer segment'} through {profile.get('preferred_channels') or 'your strongest channel'}; make one specific paid offer and log the result.")
    else:
        lines.append("- Complete `python cli.py wealth-profile` and add one concrete offer and buyer segment.")
    brief = "\n".join(lines)
    console.print(Panel(brief, title="Daily Wealth Brief", border_style="cyan"))
    outdir = Path(__file__).resolve().parent / "reports"
    outdir.mkdir(exist_ok=True)
    with (outdir / "daily.log").open("a") as f:
        f.write(brief + "\n\n")
    try:
        _email_daily_brief(brief)
    except Exception as exc:
        console.print(f"[yellow]Email delivery failed: {exc}. The brief remains in reports/daily.log.[/yellow]")


def _email_daily_brief(brief: str) -> None:
    from email.message import EmailMessage
    import smtplib
    recipient = os.getenv("REPORT_EMAIL_TO", "").strip()
    host = os.getenv("SMTP_HOST", "").strip()
    if not recipient or not host:
        return
    msg = EmailMessage()
    msg["Subject"] = f"WealthOS Daily Brief — {datetime.now():%Y-%m-%d}"
    msg["From"] = os.getenv("SMTP_USERNAME", recipient)
    msg["To"] = recipient
    msg.set_content(brief)
    with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587")), timeout=20) as server:
        server.starttls()
        user = os.getenv("SMTP_USERNAME", "")
        password = os.getenv("SMTP_PASSWORD", "")
        if user:
            server.login(user, password)
        server.send_message(msg)


@app.command("daily-schedule")
def daily_schedule():
    """Install a macOS LaunchAgent for a daily 8 AM brief in the configured timezone."""
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env", override=True)
    project = Path(__file__).resolve().parent
    home = Path.home()
    launch_agents = home / "Library" / "LaunchAgents"
    launch_agents.mkdir(parents=True, exist_ok=True)
    (project / "reports").mkdir(exist_ok=True)
    timezone_name = os.getenv("WEALTHOS_TIMEZONE", "Africa/Lagos")
    plist = {"Label": "com.wealthos.daily-brief",
             "ProgramArguments": [str(project / ".venv" / "bin" / "python"), str(project / "cli.py"), "daily-report"],
             "WorkingDirectory": str(project), "StartCalendarInterval": {"Hour": 8, "Minute": 0},
             "StandardOutPath": str(project / "reports" / "scheduler.log"),
             "StandardErrorPath": str(project / "reports" / "scheduler-error.log"),
             "EnvironmentVariables": {"TZ": timezone_name}}
    target = launch_agents / "com.wealthos.daily-brief.plist"
    with target.open("wb") as f:
        plistlib.dump(plist, f)
    console.print(f"[green]LaunchAgent installed at {target}. It runs daily-report at 8:00 AM ({timezone_name}).[/green]")
    loaded = subprocess.run(["launchctl", "load", str(target)], capture_output=True, text=True)
    if loaded.returncode:
        console.print(f"[yellow]LaunchAgent saved but not loaded: {loaded.stderr.strip()}[/yellow]")
    else:
        console.print("[green]LaunchAgent loaded; the daily job is active.[/green]")


@app.command()
def wealth():
    """Show verified wealth progress, sales evidence and practical earning actions."""
    from state.manager import state_manager
    s = state_manager.get()
    m = state_manager.wealth_metrics(s)
    p = state_manager.get_profile()
    console.rule("[bold cyan]Wealth Progress[/bold cyan]")
    base = m["baseline"]
    console.print(Columns([
        Panel(naira(base["net_worth"]), title="Starting baseline", border_style="blue"),
        Panel(naira(m["received_month"]), title="Verified income this month", border_style="green"),
        Panel(naira(m["received_total"]), title="Cumulative verified income", border_style="cyan"),
        Panel(naira(m["net_realised"]), title="Net realised sales earnings", border_style="bright_green"),
    ]))
    console.print(Columns([
        Panel(naira(m["costs"]), title="Recorded sales costs", border_style="yellow"),
        Panel(naira(m["refunds"]), title="Refunds", border_style="red"),
        Panel(naira(m["outstanding"]), title="Outstanding receivables", border_style="yellow"),
        Panel(naira(m["pipeline_value"]), title="Unclosed quoted pipeline", border_style="magenta"),
    ]))
    close_rate = m["conversion_rate"]
    rating = m["rating"]
    console.print(Panel(
        f"[bold]{rating}/100[/bold]  |  Evidence: net realised receipts {naira(m['net_realised'])}; "
        f"{m['won_count']} completed sales / {m['opportunity_count']} recorded opportunities; "
        f"closed-sale conversion {pct(close_rate)}.  Portfolio change from baseline: {naira(m['net_worth_change'])}.\n" +
        "Rating components: " + ", ".join(f"{k.replace('_',' ')} {v:.0f}" for k, v in m["rating_breakdown"].items()),
        title="Wealth outcome rating", border_style="green" if rating >= 60 else "yellow"))
    console.print("[dim]Verified income comes from synced Mono account salary, business-income, other-income and interest credits; transfers and Paystack-only confirmations are excluded until bank credited. Net realised sales earnings use linked account receipts less recorded refunds and costs. Quotes, promises and receivables are excluded.[/dim]\n")
    console.print(f"Sales activity: {m['activity_count']} logged actions; {m['followup_count']} follow-up events; "
                  f"{m['followups_due']} follow-ups due. View details with `sales-history <id>`.\n")

    stages = Table(title="Pipeline by stage", box=box.SIMPLE)
    stages.add_column("Stage"); stages.add_column("Count", justify="right"); stages.add_column("Quoted value", justify="right")
    for stage_name in ("prospect", "lead", "opportunity", "proposed", "accepted", "invoiced", "won", "lost"):
        items = [o for o in m["opportunities"] if o["status"] == stage_name]
        if items: stages.add_row(stage_name.title(), str(len(items)), naira(sum(o["quoted_amount"] for o in items)))
    console.print(stages)

    active = [o for o in m["opportunities"] if o["status"] not in {"won", "lost", "refunded"}]
    console.print("\n[bold]Highest-value immediate next actions[/bold]")
    if active:
        active.sort(key=lambda o: (o["next_follow_up"] or "9999-99-99", -o["quoted_amount"]))
        for o in active[:3]:
            console.print(f"  #{o['id']} {o['customer']}: follow up via {o['channel'] or 'their last contact channel'} "
                          f"about {o['offer']} ({naira(o['quoted_amount'])}); ask what blocks a decision, "
                          f"resolve one objection, and agree a dated next step.")
    elif p["skills"] or p["offers"]:
        buyer = p["target_customers"] or "a narrow buyer segment that already pays to solve this problem"
        console.print(f"  Package one paid outcome from {p['offers'] or p['skills']} for {buyer}. "
                      f"Contact 10 likely buyers through {p['preferred_channels'] or 'your warm network'}; "
                      f"use {p['available_hours']:g} hours/week and resources ({p['resources'] or 'listed skills'}). "
                      f"Price a defined scope from delivery time and costs{(': ' + p['pricing_notes']) if p['pricing_notes'] else ''}, and ask for a paid pilot.")
    else:
        console.print("  Run `python cli.py wealth-profile` to record skills, offers, resources, available hours and channels; "
                      "then choose one buyer segment and create a specific paid offer.")
    console.print("  Track each contact and follow-up with `sales-add` and `sales-log`; record money only after credit with `sales-receipt`.")


if __name__ == "__main__":
    app()
