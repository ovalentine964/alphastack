#!/usr/bin/env python3
"""
AlphaStack Voice Interface — Test Suite

Tests the voice command parser and handler without audio.
Validates command parsing in English, Swahili, and Sheng.

Usage:
    python scripts/test_voice.py              # Run all tests
    python scripts/test_voice.py --verbose    # Show details
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from alphastack.voice.commands import CommandIntent, VoiceCommandParser


# ═══════════════════════════════════════════════════════════
# Test Cases
# ═══════════════════════════════════════════════════════════

TEST_CASES = [
    # ── English Commands ─────────────────────────────────
    {
        "name": "EN: Check balance",
        "text": "check my balance",
        "lang": "en",
        "expected_intent": CommandIntent.GET_BALANCE,
        "expected_symbol": "",
    },
    {
        "name": "EN: Buy BTC with amount",
        "text": "buy bitcoin for $500",
        "lang": "en",
        "expected_intent": CommandIntent.BUY,
        "expected_symbol": "BTC/USDT",
        "expected_amount": 500.0,
    },
    {
        "name": "EN: Buy BTC simple",
        "text": "buy some BTC",
        "lang": "en",
        "expected_intent": CommandIntent.BUY,
        "expected_symbol": "BTC/USDT",
    },
    {
        "name": "EN: Sell ETH",
        "text": "sell ethereum worth $200",
        "lang": "en",
        "expected_intent": CommandIntent.SELL,
        "expected_symbol": "ETH/USDT",
        "expected_amount": 200.0,
    },
    {
        "name": "EN: What's my P&L",
        "text": "what's my profit and loss",
        "lang": "en",
        "expected_intent": CommandIntent.GET_PNL,
    },
    {
        "name": "EN: Market overview",
        "text": "show me the market",
        "lang": "en",
        "expected_intent": CommandIntent.GET_MARKET,
    },
    {
        "name": "EN: BTC price",
        "text": "what's the price of bitcoin",
        "lang": "en",
        "expected_intent": CommandIntent.GET_PRICE,
        "expected_symbol": "BTC/USDT",
    },
    {
        "name": "EN: Kill switch",
        "text": "stop trading now",
        "lang": "en",
        "expected_intent": CommandIntent.KILL_SWITCH,
    },
    {
        "name": "EN: Close all",
        "text": "close all positions",
        "lang": "en",
        "expected_intent": CommandIntent.CLOSE_ALL,
    },
    {
        "name": "EN: Help",
        "text": "help me",
        "lang": "en",
        "expected_intent": CommandIntent.HELP,
    },
    {
        "name": "EN: Confirm",
        "text": "yes confirm",
        "lang": "en",
        "expected_intent": CommandIntent.CONFIRM,
    },
    {
        "name": "EN: Cancel",
        "text": "cancel that",
        "lang": "en",
        "expected_intent": CommandIntent.CANCEL,
    },
    {
        "name": "EN: Buy quantity",
        "text": "buy 0.5 BTC",
        "lang": "en",
        "expected_intent": CommandIntent.BUY,
        "expected_symbol": "BTC/USDT",
        "expected_quantity": 0.5,
    },
    {
        "name": "EN: Long SOL",
        "text": "go long on solana with $1000",
        "lang": "en",
        "expected_intent": CommandIntent.BUY,
        "expected_symbol": "SOL/USDT",
        "expected_amount": 1000.0,
    },

    # ── Swahili Commands ─────────────────────────────────
    {
        "name": "SW: Check balance",
        "text": "hesabu yangu",
        "lang": "sw",
        "expected_intent": CommandIntent.GET_BALANCE,
    },
    {
        "name": "SW: Buy BTC",
        "text": "nunua BTC kwa dola 500",
        "lang": "sw",
        "expected_intent": CommandIntent.BUY,
        "expected_symbol": "BTC/USDT",
        "expected_amount": 500.0,
    },
    {
        "name": "SW: Sell ETH",
        "text": "uza ETH",
        "lang": "sw",
        "expected_intent": CommandIntent.SELL,
        "expected_symbol": "ETH/USDT",
    },
    {
        "name": "SW: My profit",
        "text": "faida yangu",
        "lang": "sw",
        "expected_intent": CommandIntent.GET_PNL,
    },
    {
        "name": "SW: Market",
        "text": "soko gani",
        "lang": "sw",
        "expected_intent": CommandIntent.GET_MARKET,
    },
    {
        "name": "SW: Stop trading",
        "text": "simamisha biashara",
        "lang": "sw",
        "expected_intent": CommandIntent.KILL_SWITCH,
    },
    {
        "name": "SW: BTC price",
        "text": "bei ya BTC",
        "lang": "sw",
        "expected_intent": CommandIntent.GET_PRICE,
        "expected_symbol": "BTC/USDT",
    },
    {
        "name": "SW: Help",
        "text": "msaada",
        "lang": "sw",
        "expected_intent": CommandIntent.HELP,
    },
    {
        "name": "SW: Confirm",
        "text": "ndiyo",
        "lang": "sw",
        "expected_intent": CommandIntent.CONFIRM,
    },
    {
        "name": "SW: Cancel",
        "text": "hapana",
        "lang": "sw",
        "expected_intent": CommandIntent.CANCEL,
    },

    # ── Sheng Commands ───────────────────────────────────
    {
        "name": "SHENG: Buy BTC",
        "text": "nunua bitcoinu ka-500",
        "lang": "sheng",
        "expected_intent": CommandIntent.BUY,
        "expected_symbol": "BTC/USDT",
        "expected_amount": 500.0,
    },
    {
        "name": "SHENG: Balance",
        "text": "pesa zangu ngapi",
        "lang": "sheng",
        "expected_intent": CommandIntent.GET_BALANCE,
    },
    {
        "name": "SHENG: How much",
        "text": "ninapata nn kwa biashara",
        "lang": "sheng",
        "expected_intent": CommandIntent.GET_PNL,
    },

    # ── Edge Cases ───────────────────────────────────────
    {
        "name": "Fuzzy: get me some bitcoin",
        "text": "um can you get me like some bitcoin you know",
        "lang": "en",
        "expected_intent": CommandIntent.BUY,
        "expected_symbol": "BTC/USDT",
    },
    {
        "name": "Gibberish",
        "text": "asdfghjkl",
        "lang": "en",
        "expected_intent": CommandIntent.UNKNOWN,
    },
    {
        "name": "Empty",
        "text": "",
        "lang": "en",
        "expected_intent": CommandIntent.UNKNOWN,
    },
]


# ═══════════════════════════════════════════════════════════
# Test Runner
# ═══════════════════════════════════════════════════════════

def run_parser_tests(verbose: bool = False) -> tuple[int, int]:
    """Run all voice command parser tests."""
    parser = VoiceCommandParser()
    passed = 0
    failed = 0

    print("=" * 60)
    print("  AlphaStack Voice Command Parser Tests")
    print("=" * 60)
    print()

    for tc in TEST_CASES:
        cmd = parser.parse(tc["text"], tc["lang"])
        errors = []

        # Check intent
        if cmd.intent != tc["expected_intent"]:
            errors.append(
                f"intent: got {cmd.intent.value}, expected {tc['expected_intent'].value}"
            )

        # Check symbol if specified
        if "expected_symbol" in tc and cmd.symbol != tc["expected_symbol"]:
            errors.append(
                f"symbol: got '{cmd.symbol}', expected '{tc['expected_symbol']}'"
            )

        # Check amount if specified
        if "expected_amount" in tc and cmd.amount != tc["expected_amount"]:
            errors.append(
                f"amount: got {cmd.amount}, expected {tc['expected_amount']}"
            )

        # Check quantity if specified
        if "expected_quantity" in tc and cmd.quantity != tc["expected_quantity"]:
            errors.append(
                f"quantity: got {cmd.quantity}, expected {tc['expected_quantity']}"
            )

        if errors:
            failed += 1
            status = "❌ FAIL"
        else:
            passed += 1
            status = "✅ PASS"

        print(f"  {status}  {tc['name']}")

        if verbose or errors:
            print(f"         Input: '{tc['text']}'")
            print(f"         Intent: {cmd.intent.value} (conf: {cmd.confidence:.2f})")
            if cmd.symbol:
                print(f"         Symbol: {cmd.symbol}")
            if cmd.amount:
                print(f"         Amount: ${cmd.amount:,.2f}")
            if cmd.quantity:
                print(f"         Quantity: {cmd.quantity}")
            if cmd.needs_confirmation:
                print(f"         ⚠️  Needs confirmation")
            if cmd.missing_params:
                print(f"         Missing: {cmd.missing_params}")
            for err in errors:
                print(f"         → {err}")
            print()

    return passed, failed


def run_confirmation_tests(verbose: bool = False) -> tuple[int, int]:
    """Test confirmation prompt generation."""
    parser = VoiceCommandParser()
    passed = 0
    failed = 0

    print()
    print("=" * 60)
    print("  Confirmation Prompt Tests")
    print("=" * 60)
    print()

    # Test trade confirmation
    cmd = parser.parse("buy BTC for $500", "en")
    prompt = parser.get_confirmation_prompt(cmd)
    if "BTC" in prompt and "500" in prompt:
        passed += 1
        print(f"  ✅ PASS  Trade confirmation prompt")
    else:
        failed += 1
        print(f"  ❌ FAIL  Trade confirmation prompt: {prompt}")

    # Test kill switch confirmation
    cmd = parser.parse("stop trading", "en")
    prompt = parser.get_confirmation_prompt(cmd)
    if "stop" in prompt.lower() and "confirm" in prompt.lower():
        passed += 1
        print(f"  ✅ PASS  Kill switch confirmation prompt")
    else:
        failed += 1
        print(f"  ❌ FAIL  Kill switch confirmation prompt: {prompt}")

    # Test clarification for missing symbol
    cmd = parser.parse("buy", "en")
    prompt = parser.get_clarification_prompt(cmd)
    if "coin" in prompt.lower() or "which" in prompt.lower():
        passed += 1
        print(f"  ✅ PASS  Missing symbol clarification")
    else:
        failed += 1
        print(f"  ❌ FAIL  Missing symbol clarification: {prompt}")

    # Test clarification for missing amount
    cmd = parser.parse("buy BTC", "en")
    prompt = parser.get_clarification_prompt(cmd)
    if "amount" in prompt.lower() or "how much" in prompt.lower() or "dollar" in prompt.lower():
        passed += 1
        print(f"  ✅ PASS  Missing amount clarification")
    else:
        failed += 1
        print(f"  ❌ FAIL  Missing amount clarification: {prompt}")

    # Test Swahili clarification
    cmd = parser.parse("nunua", "sw")
    prompt = parser.get_clarification_prompt(cmd)
    if prompt:  # Should produce some prompt
        passed += 1
        print(f"  ✅ PASS  Swahili clarification prompt")
    else:
        failed += 1
        print(f"  ❌ FAIL  Swahili clarification: empty")

    return passed, failed


def run_symbol_tests(verbose: bool = False) -> tuple[int, int]:
    """Test symbol extraction from various inputs."""
    parser = VoiceCommandParser()
    passed = 0
    failed = 0

    print()
    print("=" * 60)
    print("  Symbol Extraction Tests")
    print("=" * 60)
    print()

    symbol_cases = [
        ("buy BTC", "BTC/USDT"),
        ("buy bitcoin", "BTC/USDT"),
        ("sell ethereum", "ETH/USDT"),
        ("buy some solana", "SOL/USDT"),
        ("nunua BTC", "BTC/USDT"),
        ("what's the price of doge", "DOGE/USDT"),
        ("buy BTC/USDT", "BTC/USDT"),
        ("sell XRP", "XRP/USDT"),
        ("buy cardano", "ADA/USDT"),
        ("nunua mchele", "BTC/USDT"),   # Swahili slang
    ]

    for text, expected in symbol_cases:
        cmd = parser.parse(text, "en")
        if cmd.symbol == expected:
            passed += 1
            print(f"  ✅ PASS  '{text}' → {expected}")
        else:
            failed += 1
            print(f"  ❌ FAIL  '{text}' → got '{cmd.symbol}', expected '{expected}'")

    return passed, failed


def run_language_tests(verbose: bool = False) -> tuple[int, int]:
    """Test language detection from text content."""
    from alphastack.voice.stt import LanguageDetector

    passed = 0
    failed = 0

    print()
    print("=" * 60)
    print("  Language Detection Tests")
    print("=" * 60)
    print()

    lang_cases = [
        ("buy bitcoin for $100", "en"),
        ("nunua BTC kwa dola 100", "sw"),
        ("habari, hesabu yangu", "sw"),
        ("niaje, nunua bitcoinu", "sheng"),
        ("what is my balance", "en"),
        ("faida yangu ni ngapi", "sw"),
        ("soko gani leo", "sw"),
        ("check my P&L", "en"),
    ]

    for text, expected in lang_cases:
        detected = LanguageDetector.detect_from_text(text)
        if detected == expected:
            passed += 1
            print(f"  ✅ PASS  '{text}' → {expected}")
        else:
            failed += 1
            print(f"  ❌ FAIL  '{text}' → got '{detected}', expected '{expected}'")

    return passed, failed


# ═══════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════

def main():
    verbose = "--verbose" in sys.argv or "-v" in sys.argv

    total_passed = 0
    total_failed = 0

    # Run all test suites
    p, f = run_parser_tests(verbose)
    total_passed += p
    total_failed += f

    p, f = run_confirmation_tests(verbose)
    total_passed += p
    total_failed += f

    p, f = run_symbol_tests(verbose)
    total_passed += p
    total_failed += f

    p, f = run_language_tests(verbose)
    total_passed += p
    total_failed += f

    # Summary
    total = total_passed + total_failed
    print()
    print("=" * 60)
    print(f"  RESULTS: {total_passed}/{total} passed, {total_failed} failed")
    print("=" * 60)

    if total_failed > 0:
        sys.exit(1)
    else:
        print("  🎉 All tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
