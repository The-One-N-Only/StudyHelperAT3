#!/usr/bin/env python3
"""Quick check to verify Claude integration is working."""

import os

import pytest
from dotenv import load_dotenv


@pytest.fixture(autouse=True)
def load_env():
    load_dotenv()


def test_api_key():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    assert api_key, "ANTHROPIC_API_KEY not found in .env"
    assert api_key.startswith("sk-ant-"), "API key doesn't look valid (should start with sk-ant-)"


def test_anthropic_import():
    import anthropic
    assert hasattr(anthropic, "__version__")


def test_answer_module():
    import src.answer as answer
    for func in ['answer_prompt', 'search_files_for_context', 'chat_with_sources']:
        assert hasattr(answer, func), f"Function {func}() missing in src/answer.py"


def test_flask_app():
    from conftest import flask_app
    endpoints = ['/api/answer/prompt', '/api/answer/chat']
    routes = [str(rule) for rule in flask_app.url_map.iter_rules()]
    for endpoint in endpoints:
        assert endpoint in routes, f"Endpoint {endpoint} not registered"


def test_claude_api():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("No API key configured")

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        max_tokens=10,
        messages=[{"role": "user", "content": "Say OK"}]
    )
    assert message.content, "No response from Claude API"
