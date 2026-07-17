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
    raise AssertionError("source or provider work happened before hosted AI configuration check")


def test_summarise_url_success_uses_configured_key_and_model(monkeypatch):
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
    assert request.kwargs["json"]["messages"][0]["role"] == "user"
    assert request.kwargs["timeout"] == 10


def test_summarise_file_success_keeps_structured_shape(monkeypatch):
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


def test_summarise_search_results_success_is_structured(monkeypatch):
    monkeypatch.setattr(
        summarise.requests,
        "post",
        Mock(return_value=_response("Concise hosted search summary.")),
    )

    result = summarise.summarise_search_results(
        "history", [{"title": "Archive", "description": LONG_CONTENT}]
    )

    assert result == {"status": True, "summary": "Concise hosted search summary."}


def test_summarise_url_short_content_does_not_call_provider(monkeypatch):
    post = Mock()
    monkeypatch.setattr(summarise.requests, "post", post)
    monkeypatch.setattr(summarise.whitelist, "is_allowed", lambda _url: True)
    monkeypatch.setattr(
        summarise.proxy,
        "fetch_source",
        lambda _url: {"status": True, "text": "Short"},
    )

    result = summarise.summarise_url("https://example.com", "Title")

    assert result["status"] is False
    assert "insufficient" in result["error"]
    post.assert_not_called()


def test_missing_key_url_fails_before_whitelist_or_source_work(monkeypatch):
    monkeypatch.setattr(summarise, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(summarise.whitelist, "is_allowed", _unexpected_work)
    monkeypatch.setattr(summarise.proxy, "fetch_source", _unexpected_work)
    monkeypatch.setattr(summarise.requests, "post", _unexpected_work)

    result = summarise.summarise_url("https://example.com")

    assert result == {"status": False, "error": AI_NOT_CONFIGURED_ERROR}


def test_missing_key_file_fails_before_database_work(monkeypatch):
    monkeypatch.setattr(summarise, "ANTHROPIC_API_KEY", None)
    monkeypatch.setattr(db, "get_uploaded_files", _unexpected_work)
    monkeypatch.setattr(summarise.requests, "post", _unexpected_work)

    result = summarise.summarise_file(4, user_id=7)

    assert result == {"status": False, "error": AI_NOT_CONFIGURED_ERROR}


def test_missing_key_search_fails_before_result_or_provider_work(monkeypatch):
    monkeypatch.setattr(summarise, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(summarise.requests, "post", _unexpected_work)

    class UnexpectedResults(list):
        def __iter__(self):
            _unexpected_work()

    result = summarise.summarise_search_results("history", UnexpectedResults())

    assert result == {"status": False, "error": AI_NOT_CONFIGURED_ERROR}


def test_summarise_provider_detail_is_logged_not_returned(monkeypatch):
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
