"""Error handling of the Gemini translation runner, with a fake client."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from tenacity import wait_none

import gemini


class APIError(Exception):
    """Shape of google.genai.errors.APIError: an HTTP ``code`` on the exception."""

    def __init__(self, code: int, message: str):
        super().__init__(f"{code} {message}")
        self.code = code


class FakeClient:
    def __init__(self, behaviour):
        self.calls = 0
        self.models = SimpleNamespace(generate_content=self._generate)
        self._behaviour = behaviour

    def _generate(self, **_kwargs):
        self.calls += 1
        return self._behaviour(self.calls)


def _records(n: int) -> list[dict]:
    return [
        {"id": f"h{i}", "en": f"text {i}", "uk_human": "текст", "metadata": {"type": "dialogue"}}
        for i in range(n)
    ]


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    monkeypatch.setattr(gemini, "SLEEP_BETWEEN", 0)
    monkeypatch.setattr(gemini._call_api.retry, "wait", wait_none())


def _run(tmp_path, monkeypatch, client, n=5):
    sample = tmp_path / "sample.jsonl"
    sample.write_text("\n".join(json.dumps(r) for r in _records(n)), encoding="utf-8")
    results = tmp_path / "results.jsonl"
    monkeypatch.setattr(gemini, "init_client", lambda: client)
    monkeypatch.setattr(gemini, "load_prompt_template", lambda: "{type}: {en_text}")
    gemini.run(sample, results)
    return results


# ---------------- classification ----------------


@pytest.mark.parametrize("code", [400, 401, 403, 404])
def test_client_error_codes_are_fatal(code):
    assert isinstance(gemini._classify_api_error(APIError(code, "bad")), gemini.FatalError)


@pytest.mark.parametrize("code", [429, 500, 503])
def test_rate_limit_and_server_codes_are_retryable(code):
    assert isinstance(gemini._classify_api_error(APIError(code, "x")), gemini.RetryableError)


def test_code_wins_over_digits_in_the_message():
    # The old substring check read "500" in this message as a server error.
    exc = APIError(400, "Request of 1500 tokens is invalid")
    assert isinstance(gemini._classify_api_error(exc), gemini.FatalError)


def test_exception_without_code_falls_back_to_message():
    assert isinstance(
        gemini._classify_api_error(RuntimeError("503 UNAVAILABLE")), gemini.RetryableError
    )


# ---------------- run ----------------


def test_fatal_error_stops_the_whole_run(tmp_path, monkeypatch):
    def always_403(_call):
        raise APIError(403, "PERMISSION_DENIED: API key not valid")

    client = FakeClient(always_403)
    results = _run(tmp_path, monkeypatch, client)
    # One request, then stop: a bad key is not going to work on record two.
    assert client.calls == 1
    assert not results.exists() or results.read_text(encoding="utf-8") == ""


def test_empty_response_fails_the_record_without_retries(tmp_path, monkeypatch):
    def blocked_then_ok(call):
        return SimpleNamespace(text=None if call == 1 else " переклад ")

    client = FakeClient(blocked_then_ok)
    results = _run(tmp_path, monkeypatch, client, n=3)
    assert client.calls == 3  # one call per record, no retries on the blocked one
    rows = [json.loads(line) for line in results.read_text(encoding="utf-8").splitlines()]
    assert [r["uk_gemini"] for r in rows] == [None, "переклад", "переклад"]


def test_retryable_error_is_retried_then_succeeds(tmp_path, monkeypatch):
    def flaky(call):
        if call < 3:
            raise APIError(503, "UNAVAILABLE")
        return SimpleNamespace(text="переклад")

    client = FakeClient(flaky)
    results = _run(tmp_path, monkeypatch, client, n=1)
    assert client.calls == 3
    row = json.loads(results.read_text(encoding="utf-8"))
    assert row["uk_gemini"] == "переклад"
