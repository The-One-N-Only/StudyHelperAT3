import ast
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import src.answer as answer


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
    )
    assert _read(".env.example") == expected
    assert _env_default("src/answer.py", "ANTHROPIC_MODEL") == "claude-sonnet-4-6"
    assert (
        _env_default("src/summarise.py", "ANTHROPIC_SUMMARISE_MODEL")
        == "claude-haiku-4-5-20251001"
    )


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
const container = element();
pageRoot = {
    querySelector(selector) {
        if (selector === '#alexanderChatInput') return input;
        if (selector === '#alexanderSendBtn') return sendButton;
        if (selector === '#alexanderChatMessages') return container;
        return null;
    },
};

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
input.value = 'Duplicate question';
sendAlexanderMessage();
check(networkCalls === 1, 'duplicate pending submission made another network call');
check(input.disabled === true, 'chat input stayed enabled while request pending');
check(sendButton.disabled === true, 'Send stayed enabled while request pending');
firstDeferred.resolve({ status: true, response: 'Hosted answer' });
await firstRequest;
check(alexanderMessages.includes(oldLoading), 'cleanup removed an older equal loading object');
check(!alexanderMessages.includes(activeLoading), 'success kept active loading object');
check(input.disabled === false, 'success did not restore chat input');
check(sendButton.disabled === false, 'success did not restore Send');
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
        "globalThis.studyHelperAI = { chat: (...args) => globalThis.__chatImpl(...args) };\n"
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
