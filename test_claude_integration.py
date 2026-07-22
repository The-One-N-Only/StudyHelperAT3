#!/usr/bin/env python3
"""
Quick check to verify Claude integration is working.
Run with: python test_claude_integration.py
"""

__test__ = False

import os
import sys
from dotenv import load_dotenv

load_dotenv()


def test_api_key():
    print("Testing API Key Configuration...")
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        print("   FAIL ANTHROPIC_API_KEY not found in .env")
        print("   Add to .env: ANTHROPIC_API_KEY=sk-ant-xxxxx")
        return False

    if not api_key.startswith("sk-ant-"):
        print("   WARNING API key doesn't look valid (should start with sk-ant-)")
        return False

    print("   OK ANTHROPIC_API_KEY is configured")
    return True


def test_anthropic_import():
    print("Testing Anthropic SDK...")
    try:
        import anthropic
        print(f"   OK anthropic SDK installed (v{anthropic.__version__})")
        return True
    except ImportError:
        print("   FAIL anthropic SDK not found")
        print("   Install with: pip install anthropic")
        return False


def test_answer_module():
    print("Testing answer.py Module...")
    try:
        import src.answer as answer
        print("   OK src/answer.py imports successfully")

        funcs = ['answer_prompt', 'search_files_for_context', 'chat_with_sources']
        for func in funcs:
            if hasattr(answer, func):
                print(f"   OK Function {func}() found")
            else:
                print(f"   FAIL Function {func}() missing")
                return False
        return True
    except ImportError as e:
        print(f"   FAIL Failed to import src/answer.py: {e}")
        return False


def test_flask_app():
    print("Testing Flask App...")
    try:
        os.environ['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'

        import app as flask_app
        print("   OK Flask app imports successfully")

        endpoints = ['/api/answer/prompt', '/api/answer/chat']
        routes = [str(rule) for rule in flask_app.app.url_map.iter_rules()]

        for endpoint in endpoints:
            if endpoint in routes:
                print(f"   OK Endpoint {endpoint} registered")
            else:
                print(f"   FAIL Endpoint {endpoint} not found")
                return False

        return True
    except Exception as e:
        print(f"   FAIL Failed to load Flask app: {e}")
        return False


def test_claude_api():
    print("Testing Claude API Connection...")

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("   SKIP (no API key)")
        return None

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        message = client.messages.create(
            model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
            max_tokens=10,
            messages=[
                {"role": "user", "content": "Say OK"}
            ]
        )
        print("   OK Claude API connection successful")
        print(f"   Response: {message.content[0].text}")
        return True
    except Exception as e:
        print(f"   FAIL Claude API error: {e}")
        if "401" in str(e) or "Unauthorized" in str(e):
            print("   Check your API key is valid")
        return False


def main():
    print("=" * 50)
    print("Claude Integration Test Suite")
    print("=" * 50)

    results = {}
    results["API Key"] = test_api_key()
    results["Anthropic SDK"] = test_anthropic_import()
    results["answer.py Module"] = test_answer_module()
    results["Flask App"] = test_flask_app()
    results["Claude API"] = test_claude_api()

    print()
    print("=" * 50)
    print("Summary")
    print("=" * 50)

    passed = sum(1 for r in results.values() if r)
    total = sum(1 for r in results.values() if r is not None)

    for test_name, result in results.items():
        if result is None:
            status = "SKIP"
        elif result:
            status = "PASS"
        else:
            status = "FAIL"
        print(f"{status} {test_name}")

    print(f"\nPassed: {passed}/{total}")

    if passed == total:
        print("All systems ready. Your Claude integration is working.")
        return 0
    else:
        print("Some tests failed. Check configuration above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
