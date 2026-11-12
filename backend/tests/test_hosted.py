import pytest

from app.platform.hosted import validate_environment


@pytest.fixture
def hosted_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://demo:password@localhost/paypool")
    monkeypatch.setenv("PAYPOOL_FRONTEND_URL", "https://paypool.example.com")
    monkeypatch.setenv("PAYPOOL_COOKIE_SECURE", "true")
    monkeypatch.setenv("PORT", "10000")


def test_hosted_uses_provider_port(hosted_env, monkeypatch):
    monkeypatch.setenv("PORT", "12345")
    assert validate_environment() == 12345


@pytest.mark.parametrize(
    "key,value",
    [
        ("DATABASE_URL", "sqlite:///lost-on-restart.db"),
        ("PAYPOOL_FRONTEND_URL", "http://localhost:3000"),
        ("PAYPOOL_COOKIE_SECURE", "false"),
        ("PORT", "0"),
    ],
)
def test_hosted_refuses_data_loss_or_insecure_settings(
    hosted_env, monkeypatch, key, value
):
    monkeypatch.setenv(key, value)
    with pytest.raises(ValueError):
        validate_environment()
