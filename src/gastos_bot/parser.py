"""Parser determinista (sin I/O, sin LLM) de mensajes y argumentos de comandos."""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from .models import Movement

MADRID = "Europe/Madrid"

FORMAT_HELP = (
    "Formato: concepto importe [fecha]\n"
    "Importe: positivo = ingreso, negativo = gasto (coma o punto decimal).\n"
    "Fecha opcional: hoy, ayer, dd/mm o dd/mm/aaaa.\n"
    "Ejemplos:\n"
    "  Cena -32,5\n"
    "  Nómina 1500 ayer\n"
    "  Gasolina -60 15/11\n"
    "  Alquiler -800 01/11/2026"
)


class ParseError(ValueError):
    """Error de formato; el mensaje es apto para mostrar al usuario."""


_MESSAGE_RE = re.compile(
    r"""^(?P<concept>.+?)\s+
        (?P<amount>[+\-−]?\d[\d.,]*)\s*€?
        (?:\s+(?P<date>hoy|ayer|\d{1,2}/\d{1,2}(?:/\d{4})?))?$""",
    re.IGNORECASE | re.VERBOSE,
)


def parse_amount(token: str) -> Decimal:
    """Convierte '-32,5', '1500', '1.500', '1.234,56', '12.5' en Decimal.

    Reglas: la coma siempre es decimal (máx. 2 decimales). El punto es
    separador de miles si va seguido de exactamente 3 cifras y la parte entera
    no empieza por 0 (`1.500` = 1500); en otro caso es decimal (`12.5`).
    """
    raw = token.strip().replace("−", "-")
    sign = Decimal(1)
    if raw.startswith("-"):
        sign, raw = Decimal(-1), raw[1:]
    elif raw.startswith("+"):
        raw = raw[1:]
    if not raw or not re.fullmatch(r"\d[\d.,]*", raw):
        raise ParseError(f"Importe no válido: «{token}».")

    if "," in raw:
        int_part, _, dec_part = raw.rpartition(",")
        if "," in int_part or not dec_part.isdigit() or len(dec_part) > 2:
            raise ParseError(f"Importe no válido: «{token}».")
        if not re.fullmatch(r"\d{1,3}(\.\d{3})*|\d+", int_part):
            raise ParseError(f"Importe no válido: «{token}».")
        number = int_part.replace(".", "") + "." + dec_part
    elif "." in raw:
        if re.fullmatch(r"[1-9]\d{0,2}(\.\d{3})+", raw):
            number = raw.replace(".", "")
        elif re.fullmatch(r"\d+\.\d{1,2}", raw):
            number = raw
        else:
            raise ParseError(f"Importe no válido: «{token}».")
    else:
        number = raw

    try:
        value = Decimal(number)
    except InvalidOperation as exc:
        raise ParseError(f"Importe no válido: «{token}».") from exc
    if value == 0:
        raise ParseError("El importe no puede ser 0.")
    return sign * value


def to_local(moment: datetime, tz: str = MADRID) -> datetime:
    """Convierte un datetime (UTC si es naive) a la zona horaria indicada."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=ZoneInfo("UTC"))
    return moment.astimezone(ZoneInfo(tz))


def parse_date(token: str | None, today: date) -> date:
    """Resuelve hoy/ayer/dd/mm/dd/mm/aaaa respecto a `today` (ya en Madrid)."""
    if token is None:
        return today
    t = token.strip().lower()
    if t == "hoy":
        return today
    if t == "ayer":
        return today - timedelta(days=1)
    parts = t.split("/")
    try:
        day, month = int(parts[0]), int(parts[1])
        if len(parts) == 3:
            return date(int(parts[2]), month, day)
        candidate = date(today.year, month, day)
        if candidate > today + timedelta(days=30):
            candidate = date(today.year - 1, month, day)
        return candidate
    except (ValueError, IndexError) as exc:
        raise ParseError(f"Fecha no válida: «{token}».") from exc


def parse_message(text: str, message_dt: datetime, tz: str = MADRID) -> Movement:
    """Parsea `concepto importe [fecha]`. `message_dt` es la fecha del mensaje de Telegram."""
    text = " ".join((text or "").split())
    match = _MESSAGE_RE.match(text)
    if not match:
        raise ParseError("No he entendido el mensaje.")
    concept = match.group("concept").strip()
    if not concept or re.fullmatch(r"[\d.,+\-−]+", concept):
        raise ParseError("Falta el concepto.")
    amount = parse_amount(match.group("amount"))
    today = to_local(message_dt, tz).date()
    return Movement(concept=concept, amount=amount, date=parse_date(match.group("date"), today))


# ---------------------------------------------------------------- mes / año
_MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}
_MONTH_ABBR = {k[:3]: v for k, v in _MONTHS.items()}
MONTH_NAMES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
               "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def parse_month_year(args: list[str], today: date) -> tuple[int, int]:
    """Devuelve (año, mes) a partir de [mes] [año]; por defecto el mes actual."""
    year, month = today.year, today.month
    if len(args) > 2:
        raise ParseError("Uso: /comando [mes] [año]")
    for arg in args:
        a = _strip_accents(arg.strip().lower())
        if a.isdigit() and len(a) == 4:
            year = int(a)
            if not 2000 <= year <= 2100:
                raise ParseError(f"Año no válido: «{arg}».")
        elif a.isdigit():
            month = int(a)
            if not 1 <= month <= 12:
                raise ParseError(f"Mes no válido: «{arg}».")
        elif a in _MONTHS:
            month = _MONTHS[a]
        elif a in _MONTH_ABBR:
            month = _MONTH_ABBR[a]
        else:
            raise ParseError(f"No entiendo «{arg}». Usa un mes (11 o noviembre) y/o un año (2026).")
    return year, month
