import ast
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.answer as answer
import src.db as db


ROOT = Path(__file__).resolve().parents[1]
AI_NOT_CONFIGURED_ERROR = (
    "Alexander is not configured. Add ANTHROPIC_API_KEY and restart StudyLib."
)
AI_PROVIDER_ERROR = "Alexander could not reach the AI service. Try again shortly."


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _env_default(relative_path: str, constant_name: str) -> str:
    tree = ast.parse(_read(relative_path))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == constant_name for target in node.targets):
            continue
        call = node.value
        if not isinstance(call, ast.Call) or len(call.args) != 2:
            break
        default = call.args[1]
        if isinstance(default, ast.Constant) and isinstance(default.value, str):
            return default.value
    raise AssertionError(f"{constant_name} must use os.getenv with a string default")


def test_app_loads_dotenv_immediately_before_src_imports():
    source = _read("app.py")
    lines = source.splitlines()
    tree = ast.parse(source)

    dotenv_import = next(
        node
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        and node.module == "dotenv"
        and any(alias.name == "load_dotenv" for alias in node.names)
    )
    load_call = next(
        node
        for node in tree.body
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "load_dotenv"
    )
    src_import_lines = [
        node.lineno
        for node in tree.body
        if (
            isinstance(node, ast.Import)
            and any(alias.name.startswith("src.") for alias in node.names)
        )
        or (
            isinstance(node, ast.ImportFrom)
            and node.module is not None
            and node.module.startswith("src.")
        )
    ]

    assert lines[dotenv_import.end_lineno].strip() == "load_dotenv()"
    assert load_call.lineno < min(src_import_lines)


def test_local_model_files_symbols_and_dependencies_are_absent():
    assert not (ROOT / "src" / ("local" + "_ai.py")).exists()
    assert not (ROOT / ("testAi" + "Local.py")).exists()

    forbidden = (
        "distil" + "gpt2",
        "src." + "local_ai",
        "USE_" + "LOCAL_AI",
        "LOCAL_" + "AI_MODEL",
        "import " + "torch",
        "from " + "transformers",
    )
    executable_paths = [ROOT / "app.py", ROOT / "requirements.txt"]
    executable_paths.extend((ROOT / "src").rglob("*.py"))
    executable_paths.extend((ROOT / "static").rglob("*.js"))
    executable_paths.extend((ROOT / "tests").rglob("*.py"))
    executable_paths.extend(ROOT.glob("test*.py"))

    for path in executable_paths:
        contents = path.read_text(encoding="utf-8").lower()
        for symbol in forbidden:
            assert symbol.lower() not in contents, f"{symbol} remains in {path.relative_to(ROOT)}"

    dependencies = {
        line.strip().lower().split("=", 1)[0].split(">", 1)[0]
        for line in _read("requirements.txt").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert "torch" not in dependencies
    assert ("transform" + "ers") not in dependencies


def test_env_example_and_model_defaults_match_hosted_contract():
    expected = (
        "ANTHROPIC_API_KEY=\n"
        "ANTHROPIC_MODEL=claude-sonnet-4-6\n"
        "ANTHROPIC_SUMMARISE_MODEL=claude-haiku-4-5-20251001\n"
        "SERP_API_KEY=\n"
        "GOOGLE_BOOKS_API_KEY=\n"
        "PUBMED_API_KEY=\n"
    )
    assert _read(".env.example") == expected
    assert _env_default("src/answer.py", "ANTHROPIC_MODEL") == "claude-sonnet-4-6"
    assert (
        _env_default("src/summarise.py", "ANTHROPIC_SUMMARISE_MODEL")
        == "claude-haiku-4-5-20251001"
    )


def test_google_custom_search_backend_symbols_are_absent():
    source = _read("src/search.py")
    forbidden = (
        "GOOGLE_" + "SEARCH_API_KEY",
        "GOOGLE_" + "SEARCH_ENGINE_ID",
        "_google_" + "custom_search_items",
        "google_" + "scholar",
        "googleapis.com/" + "customsearch",
    )

    for symbol in forbidden:
        assert symbol not in source


def test_manual_claude_script_is_non_secret_and_not_collected():
    script = _read("test_claude_integration.py")
    assert "__test__ = False" in script
    assert 'os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")' in script
    assert "ANTHROPIC_API_KEY is configured" in script
    assert "api_key[:" not in script


def _unexpected_lookup(*_args, **_kwargs):
    raise AssertionError("context lookup happened before hosted AI configuration check")


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
def test_answer_entry_points_fail_before_context_lookup_without_client(
    monkeypatch, invoke, expected
):
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


def test_answer_prompt_uses_configured_model_and_first_text_block(monkeypatch):
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


def test_chat_preserves_message_roles_content_and_first_text_block(monkeypatch):
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


def test_answer_provider_error_is_logged_and_sanitised(monkeypatch):
    provider_detail = "provider-secret-DO-NOT-RETURN-7f21"
    fake_client = FakeAnthropicClient(error=RuntimeError(provider_detail))
    _hosted_answer_setup(monkeypatch, fake_client)
    log_exception = Mock()
    monkeypatch.setattr(answer.logging, "exception", log_exception)

    result = answer.answer_prompt("Explain the topic", user_id=7)

    assert result == {"status": False, "error": AI_PROVIDER_ERROR}
    assert provider_detail not in str(result)
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


def test_workspace_chat_db_inserts_turns_oldest_first_and_isolates_owners(
    isolated_workspace_db,
):
    ids = isolated_workspace_db

    assert db.append_workspace_chat_turn(
        ids["first_user"], ids["first_workspace"], "First question", "First answer"
    ) is True
    assert db.append_workspace_chat_turn(
        ids["first_user"], ids["first_workspace"], "Second question", "Second answer"
    ) is True

    messages = db.get_workspace_chat_messages(
        ids["first_workspace"], ids["first_user"]
    )
    assert [(message["role"], message["content"]) for message in messages] == [
        ("user", "First question"),
        ("assistant", "First answer"),
        ("user", "Second question"),
        ("assistant", "Second answer"),
    ]
    assert [message["id"] for message in messages] == sorted(
        message["id"] for message in messages
    )
    assert db.get_workspace_chat_messages(
        ids["first_workspace"], ids["second_user"]
    ) == []
    assert db.append_workspace_chat_turn(
        ids["second_user"], ids["first_workspace"], "Attack", "Blocked"
    ) is False
    assert len(db.get_workspace_chat_messages(
        ids["first_workspace"], ids["first_user"]
    )) == 4


def test_workspace_deletion_cleans_up_chat_messages(isolated_workspace_db):
    ids = isolated_workspace_db
    assert db.append_workspace_chat_turn(
        ids["first_user"], ids["first_workspace"], "Question", "Answer"
    ) is True

    assert db.delete_workspace(ids["first_workspace"], ids["first_user"]) is True

    with ids["session"]() as session:
        assert session.query(db.WorkspaceChatMessage).count() == 0


def test_url_item_upsert_reuses_legacy_source_name_row(isolated_workspace_db):
    ids = isolated_workspace_db
    source_url = "https://en.wikipedia.org/wiki/Archive"
    with ids["session"]() as session:
        legacy = db.Item(
            title="Legacy title",
            description="Legacy description",
            thumb_url="",
            thumb_mime="image/jpeg",
            thumb_height=0,
            source_url=source_url,
            source_name="Wikipedia",
            source_id=source_url,
        )
        session.add(legacy)
        session.commit()
        legacy_id = legacy.id

    result = db.get_or_create_item_by_source_id(
        {
            "title": "Fresh title",
            "description": "Fresh description",
            "thumb_url": "",
            "thumb_mime": "image/jpeg",
            "thumb_height": 0,
            "source_url": source_url,
            "source_name": "wikipedia",
            "source_id": source_url,
        },
        ids["first_user"],
        False,
    )

    assert result["id"] == legacy_id
    assert result["source_name"] == "Wikipedia"
    with ids["session"]() as session:
        assert session.query(db.Item).filter_by(source_id=source_url).count() == 1


def test_workspace_chat_get_requires_login_and_owned_workspace(monkeypatch):
    import app as flask_app

    with flask_app.app.test_request_context("/api/workspaces/4/chat"):
        response, status = flask_app.get_workspace_chat(4)
    assert status == 401
    assert response.get_json() == {"status": False, "error": "Not logged in"}

    monkeypatch.setattr(flask_app.db, "get_workspace", lambda *_args: None)
    with flask_app.app.test_request_context("/api/workspaces/4/chat"):
        flask_app.session["user_id"] = 9
        response, status = flask_app.get_workspace_chat(4)
    assert status == 404
    assert response.get_json() == {"status": False, "error": "Workspace not found"}


@pytest.mark.parametrize("configured", (False, True))
def test_workspace_chat_get_returns_saved_messages_and_ai_state(monkeypatch, configured):
    import app as flask_app

    saved = [
        {"id": 1, "role": "user", "content": "Question", "time_created": 10},
        {"id": 2, "role": "assistant", "content": "Answer", "time_created": 10},
    ]
    monkeypatch.setattr(flask_app.db, "get_workspace", lambda *_args: {"id": 4})
    monkeypatch.setattr(
        flask_app.db,
        "get_workspace_chat_messages",
        lambda workspace_id, user_id: saved,
        raising=False,
    )
    monkeypatch.setattr(flask_app.answer, "client", object() if configured else None)

    with flask_app.app.test_request_context("/api/workspaces/4/chat"):
        flask_app.session["user_id"] = 9
        response = flask_app.get_workspace_chat(4)

    assert response.get_json() == {
        "status": True,
        "messages": saved,
        "ai_configured": configured,
    }


def test_answer_chat_persists_successful_owned_workspace_turn(monkeypatch):
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
        lambda received, user_id, atn=None: {
            "status": True,
            "response": "Hosted answer",
            "sources": [],
        },
    )

    with flask_app.app.test_request_context(
        "/api/answer/chat",
        method="POST",
        json={"messages": messages, "workspace_id": 4},
    ):
        flask_app.session["user_id"] = 9
        response = flask_app.answer_chat()

    assert response.get_json()["response"] == "Hosted answer"
    assert append_calls == [(9, 4, "Latest question", "Hosted answer")]


def test_answer_chat_rejects_wrong_workspace_owner_before_provider(monkeypatch):
    import app as flask_app

    monkeypatch.setattr(flask_app.db, "get_workspace", lambda *_args: None)
    monkeypatch.setattr(
        flask_app.answer,
        "chat_with_sources",
        lambda *_args, **_kwargs: pytest.fail("provider called for wrong workspace owner"),
    )

    with flask_app.app.test_request_context(
        "/api/answer/chat",
        method="POST",
        json={
            "messages": [{"role": "user", "content": "Question"}],
            "workspace_id": 4,
        },
    ):
        flask_app.session["user_id"] = 9
        response, status = flask_app.answer_chat()

    assert status == 404
    assert response.get_json() == {"status": False, "error": "Workspace not found"}


def test_answer_chat_does_not_persist_provider_failure(monkeypatch):
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
        "/api/answer/chat",
        method="POST",
        json={
            "messages": [{"role": "user", "content": "Question"}],
            "workspace_id": 4,
        },
    ):
        flask_app.session["user_id"] = 9
        response = flask_app.answer_chat()

    assert response.get_json() == {"status": False, "error": AI_PROVIDER_ERROR}


def test_answer_chat_without_workspace_keeps_legacy_non_persistent_contract(monkeypatch):
    import app as flask_app

    monkeypatch.setattr(
        flask_app.db,
        "get_workspace",
        lambda *_args: pytest.fail("legacy chat attempted workspace lookup"),
    )
    monkeypatch.setattr(
        flask_app.db,
        "append_workspace_chat_turn",
        lambda *_args: pytest.fail("legacy chat attempted persistence"),
        raising=False,
    )
    monkeypatch.setattr(
        flask_app.answer,
        "chat_with_sources",
        lambda *_args, **_kwargs: {"status": True, "response": "Legacy answer"},
    )

    with flask_app.app.test_request_context(
        "/api/answer/chat",
        method="POST",
        json={"messages": [{"role": "user", "content": "Question"}]},
    ):
        flask_app.session["user_id"] = 9
        response = flask_app.answer_chat()

    assert response.get_json() == {"status": True, "response": "Legacy answer"}


def test_browse_summary_returns_summariser_dict_directly(monkeypatch):
    import app as flask_app

    expected = {"status": False, "error": AI_NOT_CONFIGURED_ERROR}
    monkeypatch.setattr(
        flask_app.summarise,
        "summarise_search_results",
        lambda *_args, **_kwargs: expected,
    )

    with flask_app.app.test_request_context(
        "/api/browse/summary",
        method="POST",
        json={"query": "history", "results": []},
    ):
        flask_app.session["user_id"] = 7
        response = flask_app.browse_summary()

    assert response.get_json() == expected


def test_send_alexander_message_runtime_lifecycle(tmp_path):
    source = _read("static/js/pages/workspace.js")
    source = source.replace(
        "import { showToast } from '../toast.js';",
        "const showToast = () => {};",
    ).replace(
        "import { studyHelperAI } from '../ai-prompt.js';",
        "const studyHelperAI = globalThis.studyHelperAI;",
    )
    harness = r'''
function element() {
    let html = '';
    return {
        value: '',
        disabled: false,
        children: [],
        scrollTop: 0,
        scrollHeight: 0,
        get innerHTML() { return html; },
        set innerHTML(value) { html = String(value); this.children = []; },
        set textContent(value) {
            html = String(value)
                .replaceAll('&', '&amp;')
                .replaceAll('<', '&lt;')
                .replaceAll('>', '&gt;');
        },
        appendChild(child) { this.children.push(child); this.scrollHeight += 1; },
    };
}

function check(condition, message) {
    if (!condition) throw new Error(message);
}

function deferred() {
    let resolve;
    let reject;
    const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
    return { promise, resolve, reject };
}

globalThis.document = {
    createElement: () => element(),
    querySelector: () => null,
};

const input = element();
const sendButton = element();
const refreshButton = element();
const container = element();
pageRoot = {
    querySelector(selector) {
        if (selector === '#alexanderChatInput') return input;
        if (selector === '#alexanderSendBtn') return sendButton;
        if (selector === '#refreshWorkspaceBtn') return refreshButton;
        if (selector === '#alexanderChatMessages') return container;
        return null;
    },
};
currentWorkspaceId = 42;

const oldLoading = { role: 'agent', text: 'Alexander is thinking...' };
alexanderMessages = [{ role: 'agent', text: 'Welcome' }, oldLoading];
const firstDeferred = deferred();
let networkCalls = 0;
globalThis.__chatImpl = () => {
    networkCalls += 1;
    return firstDeferred.promise;
};
input.value = 'First question';
const firstRequest = sendAlexanderMessage();
const activeLoading = alexanderMessages.at(-1);
check(alexanderConversationVersion === 1, 'chat did not invalidate an older Refresh response');
input.value = 'Duplicate question';
sendAlexanderMessage();
check(networkCalls === 1, 'duplicate pending submission made another network call');
check(globalThis.__chatCalls[0][0] === 'First question', 'chat message payload changed');
check(globalThis.__chatCalls[0][1]?.workspaceId === 42, 'chat omitted current workspace ID');
check(input.disabled === true, 'chat input stayed enabled while request pending');
check(sendButton.disabled === true, 'Send stayed enabled while request pending');
check(refreshButton.disabled === true, 'Refresh stayed enabled while chat request pending');
firstDeferred.resolve({ status: true, response: 'Hosted answer' });
await firstRequest;
check(alexanderMessages.includes(oldLoading), 'cleanup removed an older equal loading object');
check(!alexanderMessages.includes(activeLoading), 'success kept active loading object');
check(input.disabled === false, 'success did not restore chat input');
check(sendButton.disabled === false, 'success did not restore Send');
check(refreshButton.disabled === false, 'success did not restore Refresh');
check(alexanderMessages.at(-1).text === 'Hosted answer', 'success response was not rendered');

alexanderMessages = [];
const rejectionDeferred = deferred();
globalThis.__chatImpl = () => rejectionDeferred.promise;
input.value = 'Rejected question';
const rejectedRequest = sendAlexanderMessage();
const rejectedLoading = alexanderMessages.at(-1);
rejectionDeferred.reject(new Error('network unavailable'));
try { await rejectedRequest; } catch (_) { /* cleanup must still run */ }
check(!alexanderMessages.includes(rejectedLoading), 'rejection kept active loading object');
check(input.disabled === false, 'rejection did not restore chat input');
check(sendButton.disabled === false, 'rejection did not restore Send');

alexanderMessages = [];
const serverError = 'Alexander is not configured. Add ANTHROPIC_API_KEY and restart StudyLib.';
globalThis.__chatImpl = async () => ({ status: false, error: serverError });
input.value = 'Server error question';
await sendAlexanderMessage();
const errorBubble = alexanderMessages.at(-1);
check(errorBubble.role === 'agent', 'structured server error was not an Alexander bubble');
check(errorBubble.text.includes(serverError), 'structured server error text was not rendered');
check(input.disabled === false && sendButton.disabled === false, 'server error left controls disabled');
'''
    prelude = (
        "globalThis.__chatImpl = async () => ({ status: false, error: 'unset' });\n"
        "globalThis.__chatCalls = [];\n"
        "globalThis.studyHelperAI = { chat: (...args) => { globalThis.__chatCalls.push(args); return globalThis.__chatImpl(...args); } };\n"
    )
    harness_path = tmp_path / "workspace-ai-lifecycle.mjs"
    harness_path.write_text(prelude + source + "\n" + harness, encoding="utf-8")

    completed = subprocess.run(
        ["node", str(harness_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_study_helper_ai_restores_history_and_sends_optional_workspace_id(tmp_path):
    module_path = tmp_path / "ai-prompt-under-test.mjs"
    module_path.write_text(_read("static/js/ai-prompt.js"), encoding="utf-8")
    harness = r'''
function check(condition, message) {
    if (!condition) throw new Error(message);
}

globalThis.document = {
    querySelector: () => null,
    getElementById: () => null,
};
const requests = [];
globalThis.fetch = async (_url, options) => {
    requests.push(JSON.parse(options.body));
    return {
        ok: true,
        async json() { return { status: true, response: `Answer ${requests.length}` }; },
    };
};

const { studyHelperAI } = await import("./ai-prompt-under-test.mjs");
const saved = [
    { role: "user", content: "Saved question" },
    { role: "assistant", content: "Saved answer" },
];
studyHelperAI.setConversationHistory(saved);
saved[0].content = "mutated outside";
await studyHelperAI.chat("Latest question", { workspaceId: 42, atn: "Essay" });

check(requests[0].workspace_id === 42, "workspace ID missing from chat payload");
check(requests[0].atn === "Essay", "ATN changed");
check(requests[0].messages.length === 3, "saved history was not restored");
check(requests[0].messages[0].content === "Saved question", "history was not copied safely");
check(requests[0].messages[1].role === "assistant", "assistant history role changed");

studyHelperAI.clearConversation();
await studyHelperAI.chat("Legacy question");
check(!Object.hasOwn(requests[1], "workspace_id"), "legacy chat gained workspace ID");
'''
    harness_path = tmp_path / "ai-prompt-runtime.mjs"
    harness_path.write_text(harness, encoding="utf-8")

    completed = subprocess.run(
        ["node", str(harness_path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_workspace_restores_saved_chat_and_disables_unconfigured_controls(tmp_path):
    source = _read("static/js/pages/workspace.js")
    assert "`/api/workspaces/${currentWorkspaceId}/chat`" in source
    source = source.replace(
        "import { showToast } from '../toast.js';",
        "const showToast = () => {};",
    ).replace(
        "import { studyHelperAI } from '../ai-prompt.js';",
        "const studyHelperAI = globalThis.studyHelperAI;",
    )
    harness = rf'''
function check(condition, message) {{
    if (!condition) throw new Error(message);
}}

function element() {{
    let html = "";
    return {{
        disabled: false,
        children: [],
        scrollTop: 0,
        scrollHeight: 0,
        get innerHTML() {{ return html; }},
        set innerHTML(value) {{ html = String(value); this.children = []; }},
        get textContent() {{ return html; }},
        set textContent(value) {{
            html = String(value)
                .replaceAll("&", "&amp;")
                .replaceAll("<", "&lt;")
                .replaceAll(">", "&gt;");
        }},
        appendChild(child) {{ this.children.push(child); this.scrollHeight += 1; }},
    }};
}}

globalThis.document = {{ createElement: () => element() }};
const input = element();
const sendButton = element();
const status = element();
const container = element();
pageRoot = {{
    querySelector(selector) {{
        if (selector === "#alexanderChatInput") return input;
        if (selector === "#alexanderSendBtn") return sendButton;
        if (selector === "#alexanderChatStatus") return status;
        if (selector === "#alexanderChatMessages") return container;
        return null;
    }},
}};

const saved = [
    {{ id: 1, role: "user", content: "Saved question", time_created: 10 }},
    {{ id: 2, role: "assistant", content: "Saved answer", time_created: 10 }},
];
applyAlexanderChatData({{ status: true, messages: saved, ai_configured: false }});
renderAlexanderMessages();
syncAlexanderChatAvailability();

check(globalThis.__historyCalls.length === 1, "saved history was not given to AI client");
check(JSON.stringify(globalThis.__historyCalls[0]) === JSON.stringify(saved),
    "AI client received wrong workspace history");
check(alexanderMessages.length === 3, "saved chat bubbles were not restored after welcome");
check(alexanderMessages[1].role === "user" && alexanderMessages[1].text === "Saved question",
    "saved user bubble changed");
check(alexanderMessages[2].role === "agent" && alexanderMessages[2].text === "Saved answer",
    "saved assistant bubble changed");
check(container.children.length === 3, "saved messages are not readable");
check(input.disabled === true && sendButton.disabled === true,
    "missing AI configuration left chat controls enabled");
check(status.textContent.includes({AI_NOT_CONFIGURED_ERROR!r}),
    "missing AI configuration message was not shown");
'''
    prelude = (
        "globalThis.__historyCalls = [];\n"
        "globalThis.studyHelperAI = {\n"
        "  setConversationHistory(messages) { globalThis.__historyCalls.push(messages); },\n"
        "  chat: async () => ({ status: false, error: 'unused' }),\n"
        "};\n"
    )
    harness_path = tmp_path / "workspace-chat-restore.mjs"
    harness_path.write_text(prelude + source + "\n" + harness, encoding="utf-8")

    completed = subprocess.run(
        ["node", str(harness_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
