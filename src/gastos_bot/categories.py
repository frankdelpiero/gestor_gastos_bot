"""Categorización por palabras clave (tabla editable en la hoja «Categorías»)."""
from __future__ import annotations

import re
import unicodedata
from decimal import Decimal

DEFAULT_RULES: list[tuple[str, str]] = [
    ("cena", "Restauración"), ("comida", "Restauración"), ("restaurante", "Restauración"),
    ("cafe", "Restauración"), ("bar", "Restauración"),
    ("supermercado", "Supermercado"), ("mercadona", "Supermercado"), ("compra", "Supermercado"),
    ("gasolina", "Transporte"), ("metro", "Transporte"), ("taxi", "Transporte"), ("bus", "Transporte"),
    ("alquiler", "Vivienda"), ("hipoteca", "Vivienda"), ("luz", "Vivienda"), ("agua", "Vivienda"),
    ("internet", "Vivienda"),
    ("cine", "Ocio"), ("netflix", "Ocio"), ("spotify", "Ocio"),
    ("farmacia", "Salud"), ("medico", "Salud"),
    ("nomina", "Salario"),
]

OTHER_EXPENSE = "Otros"
OTHER_INCOME = "Ingresos varios"


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn").strip()


class Categorizer:
    def __init__(self, rules: list[tuple[str, str]] | None = None):
        cleaned: dict[str, str] = {}
        for keyword, category in rules if rules is not None else DEFAULT_RULES:
            k, c = normalize(keyword or ""), (category or "").strip()
            if k and c and k not in cleaned:  # ignora vacías y duplicadas
                cleaned[k] = c
        # palabras clave más largas primero
        self._rules = sorted(cleaned.items(), key=lambda kv: -len(kv[0]))

    def categorize(self, concept: str, amount: Decimal) -> str:
        words = set(re.findall(r"\w+", normalize(concept)))
        text = normalize(concept)
        for keyword, category in self._rules:
            if " " in keyword:
                if keyword in text:
                    return category
            elif keyword in words:
                return category
        return OTHER_INCOME if amount > 0 else OTHER_EXPENSE
