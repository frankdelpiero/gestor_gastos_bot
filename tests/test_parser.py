from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from gastos_bot.parser import ParseError, parse_amount, parse_date, parse_message, parse_month_year

# 18/11/2026 12:00 UTC (miércoles)
NOW = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize("text,concept,amount,d", [
    ("Cena -32,5", "Cena", "-32.5", date(2026, 11, 18)),
    ("Cena -32.5", "Cena", "-32.5", date(2026, 11, 18)),
    ("Nómina 1500 ayer", "Nómina", "1500", date(2026, 11, 17)),
    ("Gasolina -60 15/11", "Gasolina", "-60", date(2026, 11, 15)),
    ("Alquiler -800 01/11/2026", "Alquiler", "-800", date(2026, 11, 1)),
    ("Café con leche -1,80 hoy", "Café con leche", "-1.80", date(2026, 11, 18)),
    ("Cena 2 personas -30", "Cena 2 personas", "-30", date(2026, 11, 18)),
    ("Bonus +200", "Bonus", "200", date(2026, 11, 18)),
    ("  Cena   -5  ", "Cena", "-5", date(2026, 11, 18)),
    ("Reforma -1.500", "Reforma", "-1500", date(2026, 11, 18)),
    ("Coche -12.345,67", "Coche", "-12345.67", date(2026, 11, 18)),
    ("Cena -32,5 €", "Cena", "-32.5", date(2026, 11, 18)),
])
def test_valid(text, concept, amount, d):
    m = parse_message(text, NOW)
    assert (m.concept, m.amount, m.date) == (concept, Decimal(amount), d)


@pytest.mark.parametrize("text", [
    "", "hola", "-32", "Cena", "Cena abc", "Cena 0", "Cena -32,555", "Cena -32 31/02",
    "Cena -32 32/01", "Cena -32 ayer hoy", "Cena 1,2,3", "Cena 0.500",
])
def test_invalid(text):
    with pytest.raises(ParseError):
        parse_message(text, NOW)


@pytest.mark.parametrize("token,expected", [
    ("12.5", "12.5"), ("1.500", "1500"), ("1.500,25", "1500.25"), ("-0,5", "-0.5"), ("+3", "3"),
])
def test_amount(token, expected):
    assert parse_amount(token) == Decimal(expected)


def test_default_date_uses_madrid_not_utc():
    # 23:30 UTC del 18/11 ya es 19/11 00:30 en Madrid (UTC+1 en invierno)
    late = datetime(2026, 11, 18, 23, 30, tzinfo=timezone.utc)
    assert parse_message("Cena -5", late).date == date(2026, 11, 19)
    assert parse_message("Cena -5 hoy", late).date == date(2026, 11, 19)
    assert parse_message("Cena -5 ayer", late).date == date(2026, 11, 18)


def test_summer_time_offset():
    # 22:30 UTC en julio = 00:30 del día siguiente en Madrid (UTC+2)
    dt = datetime(2026, 7, 10, 22, 30, tzinfo=timezone.utc)
    assert parse_message("Cena -5", dt).date == date(2026, 7, 11)


def test_dd_mm_year_rollover():
    today = date(2027, 1, 2)
    assert parse_date("28/12", today) == date(2026, 12, 28)  # no en el futuro lejano
    assert parse_date("05/01", today) == date(2027, 1, 5)  # ≤ 30 días: año actual


def test_naive_datetime_is_treated_as_utc():
    assert parse_message("Cena -5", datetime(2026, 11, 18, 23, 30)).date == date(2026, 11, 19)


def test_month_year():
    today = date(2026, 11, 18)
    assert parse_month_year([], today) == (2026, 11)
    assert parse_month_year(["marzo"], today) == (2026, 3)
    assert parse_month_year(["9", "2025"], today) == (2025, 9)
    assert parse_month_year(["Septiembre"], today) == (2026, 9)
    assert parse_month_year(["2025"], today) == (2025, 11)
    with pytest.raises(ParseError):
        parse_month_year(["13"], today)
    with pytest.raises(ParseError):
        parse_month_year(["foo"], today)
