"""Quick ping of the 3 APIs used by debate_runner."""
from debate_runner import call_claude, call_openai, call_gemini

print("testing claude...")
try:
    r = call_claude("You are terse.", "Say PING in one word.", max_tokens=20)
    print(f"  claude: {r.strip()!r}")
except Exception as e:
    print(f"  claude FAIL: {e}")

print("testing gemini...")
try:
    r = call_gemini("You are terse.", "Say PING in one word.", max_tokens=20)
    print(f"  gemini: {r.strip()!r}")
except Exception as e:
    print(f"  gemini FAIL: {e}")

print("testing openai...")
try:
    r = call_openai("You are terse.", "Say PING in one word.", max_tokens=20)
    print(f"  openai: {r.strip()!r}")
except Exception as e:
    print(f"  openai FAIL: {e}")
