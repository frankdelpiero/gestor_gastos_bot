from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from starlette.testclient import TestClient
from telegram.ext import Application

from gastos_bot.application import build_application
from gastos_bot.bot.handlers import Deps
from gastos_bot.config import Settings
from gastos_bot.sheets.repository import InMemoryRepository
from gastos_bot.webhook import create_web_app

SETTINGS = Settings("123:ABC", 42, "sid", "{}", "hook-secret")


@pytest.fixture
def client(monkeypatch):
    # Application usa __slots__: se parchea la clase para evitar llamadas de red (getMe)
    monkeypatch.setattr(Application, "initialize", AsyncMock())
    monkeypatch.setattr(Application, "shutdown", AsyncMock())
    deps = Deps(SETTINGS, InMemoryRepository(), now=lambda: datetime(2026, 11, 18, tzinfo=timezone.utc))
    with TestClient(create_web_app(build_application(deps), SETTINGS.webhook_secret)) as c:
        yield c


def test_healthz(client):
    assert client.get("/healthz").text == "ok"


def test_wrong_or_missing_secret_is_403(client):
    assert client.post("/telegram", json={"update_id": 1}).status_code == 403
    r = client.post("/telegram", json={"update_id": 1}, headers={"X-Telegram-Bot-Api-Secret-Token": "nope"})
    assert r.status_code == 403
