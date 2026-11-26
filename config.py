"""
config.py — WealthOS centralised configuration
Loads all settings from the .env file automatically.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Paystack ──────────────────────────────────────────────
    paystack_secret_key: str = Field(default="", description="Paystack secret key")

    # ── Personal financial parameters ─────────────────────────
    hysa_yield_rate: float           = 0.105
    monthly_income_estimate: float   = 850_000.0
    monthly_expense_estimate: float  = 350_000.0
    risk_tolerance: float            = 2.5       # CRRA gamma
    inflation_rate: float            = 0.30
    risk_free_rate: float            = 0.14      # Nigerian T-bill

    # ── Manual investment positions ────────────────────────────
    equities_value: float            = 2_000_000.0
    bonds_value: float               = 1_000_000.0
    money_market_value: float        = 1_500_000.0
    other_assets_value: float        = 500_000.0

    # ── Wealth goal ────────────────────────────────────────────
    wealth_goal: float               = 50_000_000.0
    goal_horizon_months: int         = 60

    # ── System ────────────────────────────────────────────────
    database_url: str = "sqlite:///wealthos.db"

    @property
    def paystack_configured(self) -> bool:
        return bool(self.paystack_secret_key)


# Singleton — import this everywhere
settings = Settings()
