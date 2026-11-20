"""Acceso a datos: Protocol + implementación Google Sheets + implementación en memoria (tests)."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Protocol

from ..models import Record
from .client import with_retries

REGISTRO = "Registro"
CATEGORIAS = "Categorías"
META = "_Meta"
HEADERS = ["ID", "Fecha", "Concepto", "Importe", "Categoría", "Usuario", "Creado"]
UPDATE_RING = 200


class Repository(Protocol):
    def reserve_id(self) -> int: ...
    def add_record(self, record: Record) -> None: ...
    def find_by_id(self, record_id: int) -> Record | None: ...
    def last_record(self) -> Record | None: ...
    def list_last(self, n: int) -> list[Record]: ...
    def delete_by_id(self, record_id: int) -> bool: ...
    def month_records(self, year: int, month: int) -> list[Record]: ...
    def category_rules(self) -> list[tuple[str, str]]: ...
    def update_seen(self, update_id: int) -> bool: ...
    def mark_update(self, update_id: int) -> None: ...


def month_totals(records: list[Record]) -> tuple[Decimal, Decimal]:
    income = sum((r.amount for r in records if r.amount > 0), Decimal(0))
    expenses = sum((r.amount for r in records if r.amount < 0), Decimal(0))
    return income, expenses


def expenses_by_category(records: list[Record]) -> dict[str, Decimal]:
    out: dict[str, Decimal] = defaultdict(Decimal)
    for r in records:
        if r.amount < 0:
            out[r.category] += -r.amount
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


# ------------------------------------------------------------------ memoria
class InMemoryRepository:
    """Implementación para tests y desarrollo sin red."""

    def __init__(self, rules: list[tuple[str, str]] | None = None):
        self.records: list[Record] = []
        self._next_id = 1
        self._updates: list[int] = []
        self._rules = rules or []
        self.fail_next: Exception | None = None  # para simular fallos

    def _maybe_fail(self):
        if self.fail_next is not None:
            exc, self.fail_next = self.fail_next, None
            raise exc

    def reserve_id(self) -> int:
        self._maybe_fail()
        current = max([self._next_id] + [r.id + 1 for r in self.records])
        self._next_id = current + 1
        return current

    def add_record(self, record: Record) -> None:
        self._maybe_fail()
        if not any(r.id == record.id for r in self.records):
            self.records.append(record)

    def find_by_id(self, record_id: int) -> Record | None:
        self._maybe_fail()
        return next((r for r in self.records if r.id == record_id), None)

    def last_record(self) -> Record | None:
        return max(self.records, key=lambda r: r.id, default=None)

    def list_last(self, n: int) -> list[Record]:
        return sorted(self.records, key=lambda r: r.id, reverse=True)[:n]

    def delete_by_id(self, record_id: int) -> bool:
        self._maybe_fail()
        before = len(self.records)
        self.records = [r for r in self.records if r.id != record_id]
        return len(self.records) < before

    def month_records(self, year: int, month: int) -> list[Record]:
        return [r for r in self.records if r.date.year == year and r.date.month == month]

    def category_rules(self) -> list[tuple[str, str]]:
        return self._rules

    def update_seen(self, update_id: int) -> bool:
        return update_id in self._updates

    def mark_update(self, update_id: int) -> None:
        self._updates.append(update_id)
        self._updates = self._updates[-UPDATE_RING:]


# ------------------------------------------------------------------- Google
_EPOCH = date(1899, 12, 30)


def _to_date(value) -> date:
    if isinstance(value, (int, float)):
        return _EPOCH + timedelta(days=int(value))
    return date.fromisoformat(str(value)[:10])


def _to_decimal(value) -> Decimal:
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    return Decimal(str(value).replace(".", "").replace(",", "."))


class GoogleSheetsRepository:
    """Columnas Registro: A ID | B Fecha | C Concepto | D Importe | E Categoría | F Usuario | G Creado."""

    def __init__(self, spreadsheet):
        self._ss = spreadsheet
        self._reg = spreadsheet.worksheet(REGISTRO)
        self._meta = spreadsheet.worksheet(META)
        self._rules_cache: tuple[float, list[tuple[str, str]]] | None = None

    # -- helpers
    def _rows(self) -> list[list]:
        rows = self._reg.get_all_values(value_render_option="UNFORMATTED_VALUE")
        return rows[1:]  # sin cabecera

    @staticmethod
    def _to_record(row: list) -> Record | None:
        try:
            row = list(row) + [""] * (7 - len(row))
            return Record(
                id=int(row[0]), date=_to_date(row[1]), concept=str(row[2]),
                amount=_to_decimal(row[3]), category=str(row[4]), user=str(row[5]),
            )
        except (ValueError, TypeError):
            return None

    def _records(self) -> list[Record]:
        return [r for r in (self._to_record(row) for row in self._rows()) if r]

    def _row_number(self, record_id: int) -> int | None:
        ids = self._reg.col_values(1, value_render_option="UNFORMATTED_VALUE")
        for idx, value in enumerate(ids[1:], start=2):
            if str(value) == str(record_id):
                return idx
        return None

    # -- API
    @with_retries()
    def reserve_id(self) -> int:
        counter = int(self._meta.acell("B1", value_render_option="UNFORMATTED_VALUE").value or 1)
        ids = [int(v) for v in self._reg.col_values(1, value_render_option="UNFORMATTED_VALUE")[1:]
               if str(v).isdigit()]
        new_id = max(counter, (max(ids) + 1) if ids else 1)
        self._meta.update_acell("B1", new_id + 1)
        return new_id

    @with_retries()
    def add_record(self, record: Record) -> None:
        if self._row_number(record.id) is not None:  # reintento tras timeout: ya está
            return
        created = (record.created or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
        self._reg.append_row(
            [record.id, record.date.isoformat(), record.concept, float(record.amount),
             record.category, record.user, created],
            value_input_option="USER_ENTERED",
            table_range="A1",
        )

    @with_retries()
    def find_by_id(self, record_id: int) -> Record | None:
        return next((r for r in self._records() if r.id == record_id), None)

    @with_retries()
    def last_record(self) -> Record | None:
        return max(self._records(), key=lambda r: r.id, default=None)

    @with_retries()
    def list_last(self, n: int) -> list[Record]:
        return sorted(self._records(), key=lambda r: r.id, reverse=True)[:n]

    @with_retries()
    def delete_by_id(self, record_id: int) -> bool:
        row = self._row_number(record_id)  # siempre por ID, nunca por nº de fila guardado
        if row is None:
            return False
        self._reg.delete_rows(row)
        return True

    @with_retries()
    def month_records(self, year: int, month: int) -> list[Record]:
        return [r for r in self._records() if r.date.year == year and r.date.month == month]

    @with_retries()
    def category_rules(self) -> list[tuple[str, str]]:
        import time

        now = time.monotonic()
        if self._rules_cache and now - self._rules_cache[0] < 300:
            return self._rules_cache[1]
        rows = self._ss.worksheet(CATEGORIAS).get_all_values()[1:]
        rules = [(r[0], r[1]) for r in rows if len(r) >= 2]
        self._rules_cache = (now, rules)
        return rules

    def _ring(self) -> list[int]:
        raw = str(self._meta.acell("B2").value or "")
        return [int(x) for x in raw.split(";") if x.strip().isdigit()]

    @with_retries()
    def update_seen(self, update_id: int) -> bool:
        return update_id in self._ring()

    @with_retries()
    def mark_update(self, update_id: int) -> None:
        ring = (self._ring() + [update_id])[-UPDATE_RING:]
        self._meta.update_acell("B2", ";".join(map(str, ring)))
