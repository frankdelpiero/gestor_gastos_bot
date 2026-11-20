from datetime import date
from decimal import Decimal

from gastos_bot.models import Record
from gastos_bot.services import deletion
from gastos_bot.sheets.repository import InMemoryRepository

SECRET = "s3cret"
T0 = 1_800_000_000


def make_repo():
    repo = InMemoryRepository()
    for i in (1, 2, 3):
        rid = repo.reserve_id()
        repo.add_record(Record(rid, date(2026, 11, i), f"c{i}", Decimal(-i), "Otros", "u"))
    return repo


def test_prepare_existing_id():
    p = deletion.prepare(make_repo(), "2")
    assert p.record.id == 2 and p.error is None


def test_prepare_unknown_id_does_not_touch_sheet():
    repo = make_repo()
    p = deletion.prepare(repo, "99")
    assert p.record is None and "No existe" in p.error
    assert len(repo.records) == 3


def test_prepare_last_and_empty():
    assert deletion.prepare(make_repo(), "ultimo").record.id == 3
    assert deletion.prepare(InMemoryRepository(), "ultimo").record is None


def test_prepare_bad_args():
    assert deletion.prepare(make_repo(), None).error
    assert deletion.prepare(make_repo(), "abc").error


def test_confirm_deletes_by_id_even_if_rows_shifted():
    repo = make_repo()
    tok_ok = deletion.make_token(SECRET, "ok", 3, T0)
    repo.delete_by_id(1)  # las filas cambian entre medias
    out = deletion.resolve(repo, SECRET, tok_ok, T0 + 10)
    assert out.status == "deleted"
    assert [r.id for r in repo.records] == [2]


def test_cancel_keeps_data():
    repo = make_repo()
    out = deletion.resolve(repo, SECRET, deletion.make_token(SECRET, "no", 2, T0), T0 + 5)
    assert out.status == "cancelled" and len(repo.records) == 3


def test_expired_does_not_delete():
    repo = make_repo()
    out = deletion.resolve(repo, SECRET, deletion.make_token(SECRET, "ok", 2, T0), T0 + 121)
    assert out.status == "expired" and len(repo.records) == 3


def test_double_click_second_is_not_found():
    repo = make_repo()
    tok = deletion.make_token(SECRET, "ok", 2, T0)
    assert deletion.resolve(repo, SECRET, tok, T0 + 1).status == "deleted"
    assert deletion.resolve(repo, SECRET, tok, T0 + 2).status == "not_found"
    assert len(repo.records) == 2


def test_tampered_or_wrong_secret_is_invalid():
    repo = make_repo()
    tok = deletion.make_token(SECRET, "ok", 2, T0)
    forged = tok.replace(":2:", ":3:")
    assert deletion.resolve(repo, SECRET, forged, T0 + 1).status == "invalid"
    assert deletion.resolve(repo, "otra", tok, T0 + 1).status == "invalid"
    assert deletion.resolve(repo, SECRET, "basura", T0 + 1).status == "invalid"
    assert len(repo.records) == 3


def test_ids_never_reused_after_delete():
    repo = make_repo()
    repo.delete_by_id(3)
    assert repo.reserve_id() == 4


def test_token_fits_callback_data_limit():
    assert len(deletion.make_token(SECRET, "ok", 123456, T0).encode()) <= 64
