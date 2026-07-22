from unittest.mock import Mock

import pytest

import src.db as db
import src.summarise as summarise


HOSTED_KEY = "hosted-test-key"
HOSTED_MODEL = "configured-summarise-model"
AI_NOT_CONFIGURED_ERROR = (
    "Alexander is not configured. Add ANTHROPIC_API_KEY and restart StudyLib."
)
AI_PROVIDER_ERROR = "Alexander could not reach the AI service. Try again shortly."
LONG_CONTENT = "Academic source content with enough detail for a useful summary. " * 4


@pytest.fixture(autouse=True)
def hosted_config(monkeypatch):
    monkeypatch.setattr(summarise, "ANTHROPIC_API_KEY", HOSTED_KEY)
    monkeypatch.setattr(summarise, "ANTHROPIC_SUMMARISE_MODEL", HOSTED_MODEL)


def _response(text):
    response = Mock()
    response.status_code = 200
    response.json.return_value = {"content": [{"text": text}]}
    return response


def _unexpected_work(*_args, **_kwargs):
    raise AssertionError("provider work happened before AI configuration check")


def test_summarise_url_success(monkeypatch):
    post = Mock(
        return_value=_response(
            '{"summary": "Test summary", "bullets": ["Bullet 1"], "relevance": "Relevant"}'
        )
    )
    monkeypatch.setattr(summarise.requests, "post", post)
    monkeypatch.setattr(summarise.whitelist, "is_allowed", lambda _url: True)
    monkeypatch.setattr(
        summarise.proxy,
        "fetch_source",
        lambda _url: {"status": True, "text": LONG_CONTENT, "title": "Fetched title"},
    )

    result = summarise.summarise_url("https://example.com", "Title")

    assert result["status"] is True
    assert result["summary"] == "Test summary"
    request = post.call_args
    assert request.args == ("https://api.anthropic.com/v1/messages",)
    assert request.kwargs["headers"] == {
        "x-api-key": HOSTED_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    assert request.kwargs["json"]["model"] == HOSTED_MODEL


def test_summarise_file_success(monkeypatch):
    monkeypatch.setattr(
        db,
        "get_uploaded_files",
        lambda _user_id: [
            {"id": 4, "filename": "research.txt", "extracted_text": LONG_CONTENT}
        ],
    )
    monkeypatch.setattr(
        summarise.requests,
        "post",
        Mock(
            return_value=_response(
                '{"summary": "File summary", "bullets": ["Point"], "relevance": "Useful"}'
            )
        ),
    )

    result = summarise.summarise_file(4, user_id=7)

    assert result == {
        "summary": "File summary",
        "bullets": ["Point"],
        "relevance": "Useful",
        "status": True,
    }


def test_summarise_search_results_success(monkeypatch):
    monkeypatch.setattr(
        summarise.requests,
        "post",
        Mock(return_value=_response("Concise hosted search summary.")),
    )

    result = summarise.summarise_search_results(
        "history", [{"title": "Archive", "description": LONG_CONTENT}]
    )

    assert result == {"status": True, "summary": "Concise hosted search summary."}


def test_missing_key_url_fails_before_provider(monkeypatch):
    monkeypatch.setattr(summarise, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(summarise.whitelist, "is_allowed", _unexpected_work)
    monkeypatch.setattr(summarise.proxy, "fetch_source", _unexpected_work)
    monkeypatch.setattr(summarise.requests, "post", _unexpected_work)

    result = summarise.summarise_url("https://example.com")

    assert result == {"status": False, "error": AI_NOT_CONFIGURED_ERROR}


def test_missing_key_file_fails_before_database(monkeypatch):
    monkeypatch.setattr(summarise, "ANTHROPIC_API_KEY", None)
    monkeypatch.setattr(db, "get_uploaded_files", _unexpected_work)
    monkeypatch.setattr(summarise.requests, "post", _unexpected_work)

    result = summarise.summarise_file(4, user_id=7)

    assert result == {"status": False, "error": AI_NOT_CONFIGURED_ERROR}


def test_summarise_provider_detail_not_leaked(monkeypatch):
    provider_detail = "provider-secret-DO-NOT-RETURN-a193"
    monkeypatch.setattr(summarise.whitelist, "is_allowed", lambda _url: True)
    monkeypatch.setattr(
        summarise.proxy,
        "fetch_source",
        lambda _url: {"status": True, "text": LONG_CONTENT},
    )
    monkeypatch.setattr(
        summarise.requests,
        "post",
        Mock(side_effect=RuntimeError(provider_detail)),
    )
    log_exception = Mock()
    monkeypatch.setattr(summarise.logging, "exception", log_exception)

    result = summarise.summarise_url("https://example.com", "Title")

    assert result == {"status": False, "error": AI_PROVIDER_ERROR}
    assert provider_detail not in str(result)
    log_exception.assert_called_once()
