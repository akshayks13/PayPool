import pytest

from app.modules.negotiation import llm


class ProviderError(Exception):
    def __init__(self, code: int) -> None:
        self.code = code
        super().__init__(f"provider status {code}")


class FakeClient:
    def __init__(self, failures_before_success: int, error_code: int = 503) -> None:
        self.models = self
        self._failures_before_success = failures_before_success
        self._error_code = error_code
        self.calls = 0

    def generate_content(self, **kwargs: object) -> str:
        self.calls += 1
        if self.calls <= self._failures_before_success:
            raise ProviderError(self._error_code)
        return "success"


def test_retries_transient_provider_error_then_returns_result(monkeypatch) -> None:
    monkeypatch.setenv("PAYPOOL_LLM_MAX_RETRIES", "2")
    monkeypatch.setenv("PAYPOOL_LLM_RETRY_BACKOFF_MS", "0")
    client = FakeClient(failures_before_success=2)

    result = llm._generate_with_retry(client, model="test", contents="hello", config=object())

    assert result == "success"
    assert client.calls == 3


def test_does_not_retry_non_transient_provider_error(monkeypatch) -> None:
    monkeypatch.setenv("PAYPOOL_LLM_MAX_RETRIES", "2")
    client = FakeClient(failures_before_success=1, error_code=403)

    with pytest.raises(ProviderError):
        llm._generate_with_retry(client, model="test", contents="hello", config=object())

    assert client.calls == 1
