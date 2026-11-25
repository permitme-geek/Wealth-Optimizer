"""
optimization/engine.py — WealthOS Mathematical Optimization Engine

Implements:
  - Markowitz MVO (efficient frontier, max Sharpe)
  - Linear Programming (constrained allocation)
  - Kelly Criterion (surplus position sizing)
  - Next-₦1 marginal utility allocation
  - Risk-adjusted metrics (Sharpe, Sortino, real return)
  - Portfolio health score
"""
from __future__ import annotations
import numpy as np
from scipy.optimize import minimize
from dataclasses import dataclass
from typing import Optional
from config import settings


# ── Nigerian market parameters (calibrated to historical data) ─
ASSET_PARAMS = {
    # asset: (annual_return_nominal, annual_volatility)
    "HYSA":        (settings.hysa_yield_rate, 0.005),
    "Equities":    (0.16,  0.22),
    "Bonds":       (0.145, 0.06),
    "MoneyMarket": (0.15,  0.02),
}

ASSETS = list(ASSET_PARAMS.keys())

# Correlation matrix: [HYSA, Equities, Bonds, MoneyMarket]
CORR = np.array([
    [1.00, 0.05, 0.08, 0.12],
    [0.05, 1.00, 0.20, 0.10],
    [0.08, 0.20, 1.00, 0.35],
    [0.12, 0.10, 0.35, 1.00],
])


@dataclass
class OptimizationResult:
    # Optimal weights
    weights: dict[str, float]

    # Risk-return metrics
    expected_annual_return: float
    annual_volatility:       float
    sharpe_ratio:            float
    real_annual_return:      float   # after Nigerian CPI
    wealth_velocity_daily:   float   # ₦/day

    # Position sizing
    kelly_fractions:         dict[str, float]
    next_naira_asset:        str
    surplus_to_deploy:       float

    # Rebalancing
    current_weights:         dict[str, float]
    rebalancing_moves:       list[dict]

    # Health score
    health_score:            int     # 0–100
    health_breakdown:        dict[str, float]


class OptimizationEngine:

    def __init__(self, inflation: float = None, risk_free: float = None,
                 gamma: float = None):
        self.inflation   = inflation  or settings.inflation_rate
        self.risk_free   = risk_free  or settings.risk_free_rate
        self.gamma       = gamma      or settings.risk_tolerance  # CRRA coefficient

        # Build parameter vectors
        self.mu    = np.array([ASSET_PARAMS[a][0] for a in ASSETS])
        self.sigma = np.array([ASSET_PARAMS[a][1] for a in ASSETS])

        # Covariance matrix: Σ = D * ρ * D  where D = diag(σ)
        D = np.diag(self.sigma)
        self.cov = D @ CORR @ D

    # ── 1. Markowitz MVO — Max Sharpe ─────────────────────────
    def max_sharpe_portfolio(
        self, hysa_floor: float = 0.0
    ) -> tuple[np.ndarray, float, float, float]:
        """
        Returns (weights, μ_p, σ_p, sharpe) for the max-Sharpe portfolio.
        hysa_floor: minimum HYSA weight (liquidity constraint).
        """
        n = len(ASSETS)

        def neg_sharpe(w):
            mu_p  = float(self.mu @ w)
            var_p = float(w @ self.cov @ w)
            sig_p = np.sqrt(var_p) + 1e-10
            return -(mu_p - self.risk_free) / sig_p

        constraints = [
            {"type": "eq",   "fun": lambda w: w.sum() - 1},
        ]
        bounds = [(hysa_floor if i == 0 else 0.0, 0.65) for i in range(n)]

        best_result = None
        best_val    = np.inf

        # Multiple random starts to avoid local minima
        for _ in range(30):
            w0 = np.random.dirichlet(np.ones(n))
            res = minimize(neg_sharpe, w0, method="SLSQP",
                           bounds=bounds, constraints=constraints,
                           options={"maxiter": 1000, "ftol": 1e-9})
            if res.success and res.fun < best_val:
                best_val    = res.fun
                best_result = res

        if best_result is None:
            w = np.array([0.20, 0.40, 0.20, 0.20])
        else:
            w = best_result.x

        w = np.clip(w, 0, 1)
        w /= w.sum()

        mu_p  = float(self.mu @ w)
        sig_p = float(np.sqrt(w @ self.cov @ w))
        sharpe = (mu_p - self.risk_free) / (sig_p + 1e-10)

        return w, mu_p, sig_p, sharpe

    # ── 2. Kelly Criterion (surplus only) ─────────────────────
    def kelly_fractions(self) -> dict[str, float]:
        """
        Fractional Kelly (25%) for surplus capital deployment.
        Applied only to monthly surplus — NOT core wealth.
        """
        excess = self.mu - self.risk_free
        full_kelly = excess / (self.sigma ** 2 + 1e-10)
        frac_kelly = 0.25 * np.clip(full_kelly, 0, 1)   # quarter-Kelly
        return {ASSETS[i]: round(float(frac_kelly[i]), 4) for i in range(len(ASSETS))}

    # ── 3. Next-₦1 Marginal Utility ───────────────────────────
    def next_naira_asset(
        self, current_weights: dict[str, float], total_wealth: float
    ) -> str:
        """
        Returns the asset class where adding ₦1 maximises CRRA marginal utility.
        This is the "where should the next naira go?" answer.
        """
        best_asset, best_mu = None, -np.inf

        for i, asset in enumerate(ASSETS):
            w_i   = current_weights.get(asset, 0.0)
            W_i   = total_wealth * w_i
            r_i   = self.mu[i]
            delta = 1.0

            # CRRA marginal utility: dU/dW = W^(-γ)
            W_after  = W_i + delta * (1 + r_i)
            W_before = W_i + 1e-6

            if self.gamma == 1:
                mu_val = np.log(W_after) - np.log(W_before)
            else:
                mu_val = ((W_after**(1 - self.gamma) -
                           W_before**(1 - self.gamma)) / (1 - self.gamma))

            if mu_val > best_mu:
                best_mu    = mu_val
                best_asset = asset

        return best_asset or "MoneyMarket"

    # ── 4. Rebalancing Signals ────────────────────────────────
    def rebalancing_moves(
        self,
        current_weights: dict[str, float],
        optimal_weights: dict[str, float],
        total_wealth: float,
        threshold: float = 0.05,
    ) -> list[dict]:
        """
        Returns actionable rebalancing moves where drift > threshold (5%).
        """
        moves = []
        for asset in ASSETS:
            current = current_weights.get(asset, 0.0)
            optimal = optimal_weights.get(asset, 0.0)
            drift   = optimal - current

            if abs(drift) > threshold:
                amount = abs(drift) * total_wealth
                direction = "increase" if drift > 0 else "reduce"
                moves.append({
                    "asset":     asset,
                    "direction": direction,
                    "drift_pct": round(drift * 100, 1),
                    "amount":    round(amount, 0),
                    "from_pct":  round(current * 100, 1),
                    "to_pct":    round(optimal * 100, 1),
                })
        # sort by absolute drift descending
        return sorted(moves, key=lambda x: abs(x["drift_pct"]), reverse=True)

    # ── 5. Portfolio Health Score (0–100) ─────────────────────
    def health_score(
        self,
        sharpe: float,
        liquid_months: float,
        savings_rate: float,
        current_weights: dict[str, float],
        real_return: float,
    ) -> tuple[int, dict]:
        """
        Composite health score with five equally important dimensions.
        Returns (score: int, breakdown: dict).
        """
        def sigmoid(x): return 1 / (1 + np.exp(-x))

        # 1. Sharpe component (25 pts) — target ≥ 1.5
        sharpe_pts = min(sharpe / 1.5, 1.0) * 25

        # 2. Liquidity (20 pts) — target ≥ 4 months
        liquid_pts = min(liquid_months / 4.0, 1.0) * 20

        # 3. Savings rate (20 pts) — target ≥ 30%
        savings_pts = min(savings_rate / 0.30, 1.0) * 20

        # 4. Diversification (15 pts) — HHI penalises concentration
        hhi = sum(w**2 for w in current_weights.values())
        hhi_ideal = 1 / len(ASSETS)   # perfectly diversified
        diversif_pts = max(0, (1 - hhi) / (1 - hhi_ideal)) * 15

        # 5. Real return awareness (20 pts)
        # Penalise if real HYSA return is very negative (inflation eating wealth)
        real_return_pts = sigmoid(real_return / 0.05) * 20

        total = sharpe_pts + liquid_pts + savings_pts + diversif_pts + real_return_pts

        breakdown = {
            "sharpe":          round(sharpe_pts, 1),
            "liquidity":       round(liquid_pts, 1),
            "savings_rate":    round(savings_pts, 1),
            "diversification": round(diversif_pts, 1),
            "real_return":     round(real_return_pts, 1),
        }
        return int(min(total, 100)), breakdown

    # ── Master: run full optimization ─────────────────────────
    def run(self, state) -> OptimizationResult:
        """
        Main entry point. Takes a FinancialState, returns OptimizationResult.
        """
        W = state.total_net_worth
        if W <= 0:
            W = 1.0  # avoid division by zero

        # Liquidity floor: HYSA must cover 3 months of expenses
        liq_floor_weight = max(
            (3 * state.monthly_expense_avg) / W, 0.05
        ) if state.monthly_expense_avg > 0 else 0.05

        # Run max-Sharpe MVO
        opt_w, mu_p, sig_p, sharpe = self.max_sharpe_portfolio(
            hysa_floor=liq_floor_weight
        )
        opt_weights = {ASSETS[i]: round(float(opt_w[i]), 4) for i in range(len(ASSETS))}

        # Real return
        real_return = (1 + mu_p) / (1 + self.inflation) - 1

        # Wealth velocity (₦/day)
        velocity = W * (mu_p / 365)

        # Kelly fractions for surplus
        kelly = self.kelly_fractions()

        # Next ₦1
        current_alloc = state.allocation
        next_naira = self.next_naira_asset(current_alloc, W)

        # Surplus to deploy
        surplus = state.monthly_surplus
        deployable = max(surplus - 3 * state.monthly_expense_avg
                         + state.hysa_balance, 0) if state.monthly_expense_avg > 0 else surplus

        # Rebalancing moves
        moves = self.rebalancing_moves(current_alloc, opt_weights, W)

        # The primary rating follows verifiable outcomes; portfolio metrics remain
        # useful context but cannot turn activity or projected returns into wealth.
        from state.manager import state_manager
        wealth_metrics = state_manager.wealth_metrics(state)
        score = wealth_metrics["rating"]
        breakdown = wealth_metrics["rating_breakdown"]

        return OptimizationResult(
            weights                = opt_weights,
            expected_annual_return = round(mu_p, 4),
            annual_volatility      = round(sig_p, 4),
            sharpe_ratio           = round(sharpe, 3),
            real_annual_return     = round(real_return, 4),
            wealth_velocity_daily  = round(velocity, 0),
            kelly_fractions        = kelly,
            next_naira_asset       = next_naira,
            surplus_to_deploy      = round(max(surplus, 0), 0),
            current_weights        = {k: round(v, 4) for k, v in current_alloc.items()},
            rebalancing_moves      = moves,
            health_score           = score,
            health_breakdown       = breakdown,
        )
