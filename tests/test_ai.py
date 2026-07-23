from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.answer as answer
import src.db as db


AI_NOT_CONFIGURED_ERROR = (
    "Alexander is not configured. Add ANTHROPIC_API_KEY and restart StudyLib."
)
AI_PROVIDER_ERROR = "Alexander could not reach the AI service. Try again shortly."


def _unexpected_lookup(*_args, **_kwargs):
    raise AssertionError("context lookup happened before AI configuration check")


@pytest.mark.parametrize(
    ("invoke", "expected"),
    [
        (
            lambda: answer.answer_prompt("What is photosynthesis?", user_id=7),
            {"status": False, "error": AI_NOT_CONFIGURED_ERROR},
        ),
        (
            lambda: answer.chat_with_sources(
                [{"role": "user", "content": "What is photosynthesis?"}], user_id=7
            ),
            {"status": False, "error": AI_NOT_CONFIGURED_ERROR},
        ),
    ],
)
def test_answer_entry_points_fail_without_client(monkeypatch, invoke, expected):
    monkeypatch.setattr(answer, "client", None, raising=False)
    monkeypatch.setattr(answer, "search_files_for_context", _unexpected_lookup)
    monkeypatch.setattr(answer, "gather_whitelisted_context", _unexpected_lookup)
    monkeypatch.setattr(answer.db, "get_uploaded_files", _unexpected_lookup)
    monkeypatch.setattr(answer.search, "gbooks", _unexpected_lookup)
    monkeypatch.setattr(answer.pubmed, "search", _unexpected_lookup)

    result = invoke()
    assert result == expected


class FakeMessages:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


class FakeAnthropicClient:
    def __init__(self, response=None, error=None):
        self.messages = FakeMessages(response=response, error=error)


def _hosted_answer_setup(monkeypatch, fake_client, model="configured-answer-model"):
    monkeypatch.setattr(answer, "client", fake_client)
    monkeypatch.setattr(answer, "ANTHROPIC_API_KEY", "hosted-test-key")
    monkeypatch.setattr(answer, "ANTHROPIC_MODEL", model)
    monkeypatch.setattr(
        answer,
        "search_files_for_context",
        lambda *_args, **_kwargs: {
            "status": True,
            "context": "File context",
            "sources": [{"type": "file", "filename": "notes.txt", "file_id": 3}],
        },
    )
    monkeypatch.setattr(
        answer,
        "gather_whitelisted_context",
        lambda *_args, **_kwargs: {
            "status": True,
            "context": "Web context",
            "sources": [{"type": "wikipedia", "title": "Topic", "url": "https://example.com"}],
        },
    )


def test_answer_prompt_uses_configured_model(monkeypatch):
    response = SimpleNamespace(
        content=[SimpleNamespace(text="First hosted answer"), SimpleNamespace(text="Ignored block")]
    )
    fake_client = FakeAnthropicClient(response=response)
    _hosted_answer_setup(monkeypatch, fake_client)

    result = answer.answer_prompt("Explain the topic", user_id=7)

    assert result["status"] is True
    assert result["answer"] == "First hosted answer"
    assert result["sources"] == [
        {"type": "file", "filename": "notes.txt", "file_id": 3},
        {"type": "wikipedia", "title": "Topic", "url": "https://example.com"},
    ]
    request = fake_client.messages.calls[0]
    assert request["model"] == "configured-answer-model"


def test_chat_preserves_message_roles_and_content(monkeypatch):
    response = SimpleNamespace(
        content=[SimpleNamespace(text="First hosted response"), SimpleNamespace(text="Ignored block")]
    )
    fake_client = FakeAnthropicClient(response=response)
    _hosted_answer_setup(monkeypatch, fake_client, model="configured-chat-model")
    messages = [
        {"role": "user", "content": "First question"},
        {"role": "assistant", "content": "Earlier answer"},
        {"role": "user", "content": "Follow-up question"},
    ]

    result = answer.chat_with_sources(messages, user_id=7, atn="Essay")

    assert result["status"] is True
    assert result["response"] == "First hosted response"
    request = fake_client.messages.calls[0]
    assert request["model"] == "configured-chat-model"
    assert request["messages"] == messages


def test_answer_provider_error_is_handled(monkeypatch):
    fake_client = FakeAnthropicClient(error=RuntimeError("provider secret detail"))
    _hosted_answer_setup(monkeypatch, fake_client)
    log_exception = Mock()
    monkeypatch.setattr(answer.logging, "exception", log_exception)

    result = answer.answer_prompt("Explain the topic", user_id=7)

    assert result == {"status": False, "error": AI_PROVIDER_ERROR}
    log_exception.assert_called_once()


@pytest.fixture
def isolated_workspace_db(monkeypatch, tmp_path):
    test_engine = create_engine(f"sqlite:///{(tmp_path / 'workspace-chat.db').as_posix()}")
    test_session = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    db.Base.metadata.create_all(bind=test_engine)
    monkeypatch.setattr(db, "engine", test_engine)
    monkeypatch.setattr(db, "SessionLocal", test_session)

    with test_session() as session:
        first_user = db.User(
            email="first@example.test",
            login_platform="local",
            platform_id={},
        )
        second_user = db.User(
            email="second@example.test",
            login_platform="local",
            platform_id={},
        )
        session.add_all([first_user, second_user])
        session.flush()
        first_workspace = db.Workspace(
            user_id=first_user.id,
            name="First workspace",
            time_created=1,
        )
        second_workspace = db.Workspace(
            user_id=second_user.id,
            name="Second workspace",
            time_created=2,
        )
        session.add_all([first_workspace, second_workspace])
        session.commit()
        return {
            "session": test_session,
            "first_user": first_user.id,
            "second_user": second_user.id,
            "first_workspace": first_workspace.id,
            "second_workspace": second_workspace.id,
        }


def test_workspace_chat_inserts_and_isolates_owners(isolated_workspace_db):
    ids = isolated_workspace_db

    assert db.append_workspace_chat_turn(
        ids["first_user"], ids["first_workspace"], "First question", "First answer"
    ) is True
    assert db.append_workspace_chat_turn(
        ids["first_user"], ids["first_workspace"], "Second question", "Second answer"
    ) is True

    messages = db.get_workspace_chat_messages(ids["first_workspace"], ids["first_user"])
    assert [(m["role"], m["content"]) for m in messages] == [
        ("user", "First question"),
        ("assistant", "First answer"),
        ("user", "Second question"),
        ("assistant", "Second answer"),
    ]

    assert db.get_workspace_chat_messages(ids["first_workspace"], ids["second_user"]) == []
    assert db.append_workspace_chat_turn(ids["second_user"], ids["first_workspace"], "Attack", "Blocked") is False
    assert len(db.get_workspace_chat_messages(ids["first_workspace"], ids["first_user"])) == 4


def test_workspace_deletion_cleans_chat_messages(isolated_workspace_db):
    ids = isolated_workspace_db
    assert db.append_workspace_chat_turn(ids["first_user"], ids["first_workspace"], "Question", "Answer") is True
    assert db.delete_workspace(ids["first_workspace"], ids["first_user"]) is True

    with ids["session"]() as session:
        assert session.query(db.WorkspaceChatMessage).count() == 0


def test_answer_chat_persists_successful_turn(monkeypatch):
    import app as flask_app

    messages = [
        {"role": "user", "content": "Earlier"},
        {"role": "assistant", "content": "Earlier answer"},
        {"role": "user", "content": "Latest question"},
    ]
    append_calls = []
    monkeypatch.setattr(flask_app.db, "get_workspace", lambda user_id, workspace_id: {"id": workspace_id})
    monkeypatch.setattr(
        flask_app.db,
        "append_workspace_chat_turn",
        lambda *args: append_calls.append(args) or True,
        raising=False,
    )
    monkeypatch.setattr(
        flask_app.answer,
        "chat_with_sources",
        lambda received, user_id, atn=None, workspace_id=None: {
            "status": True,
            "response": "Hosted answer",
            "sources": [],
        },
    )

    with flask_app.app.test_request_context(
        "/api/answer/chat", method="POST",
        json={"messages": messages, "workspace_id": 4},
    ):
        flask_app.session["user_id"] = 9
        response = flask_app.answer_chat()

    assert response.get_json()["response"] == "Hosted answer"
    assert append_calls == [(9, 4, "Latest question", "Hosted answer")]


def test_answer_chat_rejects_wrong_workspace_owner(monkeypatch):
    import app as flask_app

    monkeypatch.setattr(flask_app.db, "get_workspace", lambda *_args: None)
    monkeypatch.setattr(
        flask_app.answer,
        "chat_with_sources",
        lambda *_args, **_kwargs: pytest.fail("provider called for wrong workspace owner"),
    )

    with flask_app.app.test_request_context(
        "/api/answer/chat", method="POST",
        json={"messages": [{"role": "user", "content": "Question"}], "workspace_id": 4},
    ):
        flask_app.session["user_id"] = 9
        response, status = flask_app.answer_chat()

    assert status == 404
    assert response.get_json() == {"status": False, "error": "Workspace not found"}


def test_answer_chat_does_not_persist_on_provider_failure(monkeypatch):
    import app as flask_app

    monkeypatch.setattr(flask_app.db, "get_workspace", lambda *_args: {"id": 4})
    monkeypatch.setattr(
        flask_app.db,
        "append_workspace_chat_turn",
        lambda *_args: pytest.fail("failed provider response was persisted"),
        raising=False,
    )
    monkeypatch.setattr(
        flask_app.answer,
        "chat_with_sources",
        lambda *_args, **_kwargs: {"status": False, "error": AI_PROVIDER_ERROR},
    )

    with flask_app.app.test_request_context(
        "/api/answer/chat", method="POST",
        json={"messages": [{"role": "user", "content": "Question"}], "workspace_id": 4},
    ):
        flask_app.session["user_id"] = 9
        response = flask_app.answer_chat()

    assert response.get_json() == {"status": False, "error": AI_PROVIDER_ERROR}


def test_browse_summary_returns_summariser_dict(monkeypatch):
    import app as flask_app

    expected = {"status": False, "error": AI_NOT_CONFIGURED_ERROR}
    monkeypatch.setattr(
        flask_app.summarise,
        "summarise_search_results",
        lambda *_args, **_kwargs: expected,
    )

    with flask_app.app.test_request_context(
        "/api/browse/summary", method="POST",
        json={"query": "history", "results": []},
    ):
        flask_app.session["user_id"] = 7
        response = flask_app.browse_summary()

    assert response.get_json() == expected
