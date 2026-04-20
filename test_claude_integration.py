#!/usr/bin/env python3
"""
Quick test script to verify Claude integration is working
Run with: python test_claude_integration.py
"""

import os
import sys
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_api_key():
    """Test that API key is configured"""
    print("1️⃣  Testing API Key Configuration...")
    api_key = os.getenv("ANTHROPIC_API_KEY")
    
    if not api_key:
        print("   ❌ ANTHROPIC_API_KEY not found in .env")
        print("   ℹ️  Add to .env: ANTHROPIC_API_KEY=sk-ant-xxxxx")
        return False
    
    if not api_key.startswith("sk-ant-"):
        print("   ⚠️  API key doesn't look valid (should start with sk-ant-)")
        return False
    
    print(f"   ✅ API Key configured: {api_key[:20]}...")
    return True

def test_anthropic_import():
    """Test that anthropic SDK is installed"""
    print("\n2️⃣  Testing Anthropic SDK...")
    try:
        import anthropic
        print(f"   ✅ anthropic SDK installed (v{anthropic.__version__})")
        return True
    except ImportError:
        print("   ❌ anthropic SDK not found")
        print("   ℹ️  Install with: pip install anthropic")
        return False

def test_answer_module():
    """Test that answer.py module exists and imports"""
    print("\n3️⃣  Testing answer.py Module...")
    try:
        import src.answer as answer
        print("   ✅ src/answer.py imports successfully")
        
        # Check required functions exist
        funcs = ['answer_prompt', 'search_files_for_context', 'chat_with_sources']
        for func in funcs:
            if hasattr(answer, func):
                print(f"   ✅ Function {func}() found")
            else:
                print(f"   ❌ Function {func}() missing")
                return False
        return True
    except ImportError as e:
        print(f"   ❌ Failed to import src/answer.py: {e}")
        return False

def test_flask_app():
    """Test that Flask app loads"""
    print("\n4️⃣  Testing Flask App...")
    try:
        # Mock the database setup
        os.environ['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        
        import app as flask_app
        print("   ✅ Flask app imports successfully")
        
        # Check endpoints exist
        endpoints = ['/api/answer/prompt', '/api/answer/chat']
        routes = [str(rule) for rule in flask_app.app.url_map.iter_rules()]
        
        for endpoint in endpoints:
            if endpoint in routes:
                print(f"   ✅ Endpoint {endpoint} registered")
            else:
                print(f"   ❌ Endpoint {endpoint} not found")
                return False
        
        return True
    except Exception as e:
        print(f"   ❌ Failed to load Flask app: {e}")
        return False

def test_claude_api():
    """Test connection to Claude API"""
    print("\n5️⃣  Testing Claude API Connection...")
    
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("   ⏭️  Skipping (no API key)")
        return None
    
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=10,
            messages=[
                {"role": "user", "content": "Say OK"}
            ]
        )
        print("   ✅ Claude API connection successful")
        print(f"   ✅ Response: {message.content[0].text}")
        return True
    except Exception as e:
        print(f"   ❌ Claude API error: {e}")
        if "401" in str(e) or "Unauthorized" in str(e):
            print("   ℹ️  Check your API key is valid")
        return False

def main():
    """Run all tests"""
    print("=" * 50)
    print("Claude Integration Test Suite")
    print("=" * 50)
    
    results = {
        "API Key": test_api_key(),
        "Anthropic SDK": test_anthropic_import(),
        "answer.py Module": test_answer_module(),
        "Flask App": test_flask_app(),
        "Claude API": test_claude_api(),
    }
    
    print("\n" + "=" * 50)
    print("Summary")
    print("=" * 50)
    
    passed = sum(1 for r in results.values() if r)
    total = sum(1 for r in results.values() if r is not None)
    
    for test_name, result in results.items():
        status = "✅" if result else ("❌" if result is False else "⏭️")
        print(f"{status} {test_name}")
    
    print(f"\nPassed: {passed}/{total}")
    
    if passed == total:
        print("\n🎉 All systems ready! Your Claude integration is working!")
        print("\nNext steps:")
        print("1. Start the Flask app: python app.py")
        print("2. Upload some study files")
        print("3. Try POST /api/answer/prompt with a question")
        return 0
    else:
        print("\n⚠️  Some tests failed. Check configuration above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
