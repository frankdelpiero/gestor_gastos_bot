"""Gráfico mensual en PNG (matplotlib, import diferido para acortar el cold start)."""
from __future__ import annotations

import io
from decimal import Decimal

from .formatting import fmt_money
from .models import Record
from .parser import MONTH_NAMES
from .sheets.repository import expenses_by_category, month_totals


def render_month_chart(records: list[Record], year: int, month: int) -> bytes | None:
    """Devuelve PNG o None si no hay datos en el mes."""
    if not records:
        return None
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    income, expenses = month_totals(records)
    balance = income + expenses
    by_cat = expenses_by_category(records)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.5), gridspec_kw={"width_ratios": [1, 1.4]})
    labels = ["Ingresos", "Gastos", "Balance"]
    values = [float(income), float(-expenses), float(balance)]
    colors = ["#2e7d32", "#c62828", "#1565c0" if balance >= 0 else "#ef6c00"]
    bars = ax1.bar(labels, values, color=colors)
    for bar, val in zip(bars, [income, expenses, balance]):
        ax1.annotate(fmt_money(val), (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                     ha="center", va="bottom", fontsize=8)
    ax1.axhline(0, color="#444", linewidth=0.8)
    ax1.set_title("Resumen del mes")

    if by_cat:
        cats = list(by_cat)[::-1]
        ax2.barh(cats, [float(by_cat[c]) for c in cats], color="#c62828")
        total = sum(by_cat.values(), Decimal(0))
        for i, c in enumerate(cats):
            ax2.annotate(f" {fmt_money(by_cat[c])} ({by_cat[c] / total:.0%})",
                         (float(by_cat[c]), i), va="center", fontsize=8)
        ax2.set_xlim(0, float(max(by_cat.values())) * 1.35)
    else:
        ax2.text(0.5, 0.5, "Sin gastos", ha="center", va="center")
    ax2.set_title("Gastos por categoría")

    fig.suptitle(f"{MONTH_NAMES[month].capitalize()} {year}", fontweight="bold")
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130)
    plt.close(fig)
    return buf.getvalue()
