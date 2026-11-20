"""Formato de números, fechas y mensajes (es-ES, EUR)."""
from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from .models import Record
from .parser import MONTH_NAMES


def fmt_money(value: Decimal | int | float, sign: bool = False) -> str:
    """-1234.5 -> '-1.234,50 €'."""
    d = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    s = f"{abs(d):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    prefix = "-" if d < 0 else ("+" if sign and d > 0 else "")
    return f"{prefix}{s} €"


def fmt_date(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def fmt_record_line(r: Record) -> str:
    return f"#{r.id} · {fmt_date(r.date)} · {r.concept} · {fmt_money(r.amount)}"


def fmt_echo(r: Record) -> str:
    return f"✅ #{r.id} · {r.concept} · {fmt_money(r.amount)} · {fmt_date(r.date)} · {r.category}"


def fmt_summary(year: int, month: int, income: Decimal, expenses: Decimal) -> str:
    balance = income + expenses
    return (
        f"📊 {MONTH_NAMES[month].capitalize()} {year}\n"
        f"Ingresos: {fmt_money(income)}\n"
        f"Gastos: {fmt_money(expenses)}\n"
        f"Balance: {fmt_money(balance)}"
    )
