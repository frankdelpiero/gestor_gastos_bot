from datetime import date
from decimal import Decimal

import pytest

from gastos_bot.categories import Categorizer
from gastos_bot.config import ConfigError, Settings
from gastos_bot.formatting import fmt_money
from gastos_bot.models import Record
from gastos_bot.services import idempotency
from gastos_bot.sheets.repository import InMemoryRepository, expenses_by_category, month_totals


def test_fmt_money():
    assert fmt_money(Decimal("-1234.5")) == "-1.234,50 €"
    assert fmt_money(Decimal("0.005")) == "0,01 €"
    assert fmt_money(Decimal("1500")) == "1.500,00 €"


def test_categories():
    c = Categorizer()
    assert c.categorize("Cena con amigos", Decimal(-30)) == "Restauración"
    assert c.categorize("NÓMINA noviembre", Decimal(1500)) == "Salario"
    assert c.categorize("Regalo", Decimal(-10)) == "Otros"
    assert c.categorize("Regalo", Decimal(10)) == "Ingresos varios"
    custom = Categorizer([("", "X"), ("pan", ""), ("pan", "Comida"), ("pan", "Dup")])
    assert custom.categorize("pan", Decimal(-1)) == "Comida"


def test_idempotency():
    repo = InMemoryRepository()
    assert not idempotency.already_processed(repo, 5)
    idempotency.mark_processed(repo, 5)
    assert idempotency.already_processed(repo, 5)


def test_totals():
    rs = [Record(1, date(2026, 1, 1), "a", Decimal(100), "Salario", "u"),
          Record(2, date(2026, 1, 2), "b", Decimal(-30), "Otros", "u"),
          Record(3, date(2026, 1, 3), "c", Decimal(-20), "Vivienda", "u")]
    assert month_totals(rs) == (Decimal(100), Decimal(-50))
    assert list(expenses_by_category(rs)) == ["Otros", "Vivienda"]


def test_config():
    env = {"TELEGRAM_TOKEN": "t", "ALLOWED_USER_ID": "5", "SPREADSHEET_ID": "s",
           "GOOGLE_SERVICE_ACCOUNT_JSON": "{}", "WEBHOOK_SECRET": "w"}
    assert Settings.from_env(env).allowed_user_id == 5
    with pytest.raises(ConfigError, match="WEBHOOK_SECRET"):
        Settings.from_env({k: v for k, v in env.items() if k != "WEBHOOK_SECRET"})
    with pytest.raises(ConfigError):
        Settings.from_env({**env, "ALLOWED_USER_ID": "abc"})
