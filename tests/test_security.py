"""Unit tests for AlphaStack security modules.

Covers:
- Password hashing (Argon2id) and policy enforcement
- JWT token creation, verification, refresh, and revocation
- TOTP 2FA setup, verification, and backup codes
- Session management and rate limiting
- 7-layer order validation pipeline
- Circuit breaker triggers and reset
- Kill switch activation and deactivation
- Position limits enforcement
- Encryption (AES-256-GCM)
- Request signing (HMAC-SHA256)
- IP allowlisting
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_key_dir(tmp_path: Path) -> Path:
    """Temporary directory for RSA key storage."""
    key_dir = tmp_path / "keys"
    key_dir.mkdir()
    return key_dir


@pytest.fixture()
def rsa_keypair() -> tuple[bytes, bytes]:
    """Generate a fresh RSA-4096 keypair for testing."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


@pytest.fixture()
def jwt_manager(rsa_keypair: tuple[bytes, bytes]) -> "JWTManager":
    from alphastack.security.auth import JWTManager
    priv, pub = rsa_keypair
    return JWTManager(private_key_pem=priv, public_key_pem=pub)


@pytest.fixture()
def session_manager() -> "SessionManager":
    from alphastack.security.auth import SessionManager
    return SessionManager()


@pytest.fixture()
def auth_manager(jwt_manager, session_manager) -> "AuthManager":
    from alphastack.security.auth import AuthManager
    return AuthManager(jwt_manager=jwt_manager, session_manager=session_manager)


@pytest.fixture()
def circuit_breaker() -> "CircuitBreaker":
    from alphastack.security.validation import CircuitBreaker
    return CircuitBreaker()


@pytest.fixture()
def kill_switch() -> "KillSwitch":
    from alphastack.security.validation import KillSwitch
    return KillSwitch()


@pytest.fixture()
def order_pipeline() -> "OrderValidationPipeline":
    from alphastack.security.validation import OrderValidationPipeline
    return OrderValidationPipeline()


@pytest.fixture()
def encryption_service() -> "EncryptionService":
    from alphastack.security.encryption import EncryptionService
    return EncryptionService()


# ===================================================================
# PASSWORD HASHING (Argon2id)
# ===================================================================

class TestPasswordHashing:
    def test_hash_and_verify(self):
        from alphastack.security.auth import hash_password, verify_password
        password = "SuperSecure!2026"
        h = hash_password(password)
        assert h != password
        assert verify_password(password, h) is True

    def test_wrong_password_fails(self):
        from alphastack.security.auth import hash_password, verify_password
        h = hash_password("CorrectPassword!1")
        assert verify_password("WrongPassword!1", h) is False

    def test_different_hashes_per_call(self):
        from alphastack.security.auth import hash_password
        h1 = hash_password("SamePassword!1")
        h2 = hash_password("SamePassword!1")
        assert h1 != h2  # Different salts

    def test_argon2id_prefix(self):
        from alphastack.security.auth import hash_password
        h = hash_password("TestPassword!1")
        assert h.startswith("$argon2id$")


class TestPasswordPolicy:
    def test_valid_password(self):
        from alphastack.security.auth import PasswordPolicy
        errors = PasswordPolicy.validate("MyStr0ng!Pass#2026")
        assert errors == []

    def test_too_short(self):
        from alphastack.security.auth import PasswordPolicy
        errors = PasswordPolicy.validate("Sh0rt!")
        assert any("Minimum" in e for e in errors)

    def test_no_uppercase(self):
        from alphastack.security.auth import PasswordPolicy
        errors = PasswordPolicy.validate("nouppercase1!2026")
        assert any("uppercase" in e for e in errors)

    def test_no_digit(self):
        from alphastack.security.auth import PasswordPolicy
        errors = PasswordPolicy.validate("NoDigitsHere!Abc")
        assert any("digit" in e for e in errors)

    def test_no_special_char(self):
        from alphastack.security.auth import PasswordPolicy
        errors = PasswordPolicy.validate("NoSpecial12345A")
        assert any("special" in e for e in errors)

    def test_sequential_chars_rejected(self):
        from alphastack.security.auth import PasswordPolicy
        errors = PasswordPolicy.validate("Abcdef1234!Xy")
        assert any("sequential" in e.lower() for e in errors)

    def test_repeated_chars_rejected(self):
        from alphastack.security.auth import PasswordPolicy
        errors = PasswordPolicy.validate("Aaaa1111!Xyzw")
        assert any("repeated" in e.lower() for e in errors)

    def test_email_local_part_rejected(self):
        from alphastack.security.auth import PasswordPolicy
        errors = PasswordPolicy.validate("alice2026!Pass", email="alice@example.com")
        assert any("email" in e.lower() for e in errors)


# ===================================================================
# JWT TOKENS (RS256)
# ===================================================================

class TestJWTManager:
    def test_create_and_decode_access_token(self, jwt_manager):
        token = jwt_manager.create_access_token("user123", "test@example.com")
        claims = jwt_manager.decode_token(token)
        assert claims["sub"] == "user123"
        assert claims["email"] == "test@example.com"
        assert claims["iss"] == "https://api.alphastack.io"
        assert claims["aud"] == "alphastack-app"
        assert "exp" in claims
        assert "iat" in claims

    def test_create_and_decode_refresh_token(self, jwt_manager):
        token = jwt_manager.create_refresh_token("user123", "session_abc")
        claims = jwt_manager.decode_token(token)
        assert claims["sub"] == "user123"
        assert claims["sid"] == "session_abc"
        assert claims["type"] == "refresh"

    def test_partial_token(self, jwt_manager):
        token = jwt_manager.create_partial_token("user123")
        claims = jwt_manager.decode_token(token)
        assert claims["sub"] == "user123"
        assert claims["type"] == "partial"

    def test_expired_token_raises(self, jwt_manager):
        import jwt as pyjwt
        import time as _time
        # Create a token that's already expired
        now = int(_time.time())
        payload = {
            "sub": "u1", "iss": "https://api.alphastack.io",
            "aud": "alphastack-app", "iat": now - 200, "exp": now - 100,
        }
        token = pyjwt.encode(payload, jwt_manager._private_key, algorithm="RS256",
                              headers={"kid": jwt_manager._key_id})
        with pytest.raises(Exception):
            jwt_manager.decode_token(token)

    def test_different_key_rejects_token(self, jwt_manager, rsa_keypair):
        # Sign with jwt_manager, try to decode with different keys
        from alphastack.security.auth import JWTManager
        token = jwt_manager.create_access_token("user1", "u@e.com")
        _, other_pub = rsa_keypair  # Same keypair for this test — create a new one
        from cryptography.hazmat.primitives.asymmetric import rsa as _rsa
        from cryptography.hazmat.primitives import serialization as _ser
        other_priv_key = _rsa.generate_private_key(65537, 4096)
        other_priv = other_priv_key.private_bytes(_ser.Encoding.PEM, _ser.PrivateFormat.PKCS8, _ser.NoEncryption())
        other_pub = other_priv_key.public_key().public_bytes(_ser.Encoding.PEM, _ser.PublicFormat.SubjectPublicKeyInfo)
        other_mgr = JWTManager(other_priv, other_pub)
        with pytest.raises(Exception):
            other_mgr.decode_token(token)

    def test_key_rotation(self, jwt_manager, rsa_keypair):
        token_before = jwt_manager.create_access_token("u1", "u@e.com")
        new_priv, new_pub = rsa_keypair
        jwt_manager.rotate_keys(new_priv, new_pub, "new-kid")
        # Old token should still be verifiable if using same keypair,
        # but after rotation with a NEW keypair it should fail
        # (since we replaced the private key)
        # Actually, the public key also changed, so old token fails
        token_after = jwt_manager.create_access_token("u1", "u@e.com")
        claims = jwt_manager.decode_token(token_after)
        assert claims["sub"] == "u1"


# ===================================================================
# TOTP 2FA
# ===================================================================

class TestTOTPManager:
    def test_generate_secret(self):
        from alphastack.security.auth import TOTPManager
        mgr = TOTPManager()
        secret = mgr.generate_secret()
        assert len(secret) >= 32
        assert secret.isalnum()

    def test_provisioning_uri(self):
        from alphastack.security.auth import TOTPManager
        mgr = TOTPManager()
        mgr.generate_secret()
        uri = mgr.provisioning_uri("test@example.com")
        assert uri.startswith("otpauth://totp/")
        assert "AlphaStack" in uri

    def test_verify_valid_code(self):
        import pyotp
        from alphastack.security.auth import TOTPManager
        mgr = TOTPManager()
        secret = mgr.generate_secret()
        totp = pyotp.TOTP(secret)
        code = totp.now()
        assert mgr.verify(code) is True

    def test_verify_invalid_code(self):
        from alphastack.security.auth import TOTPManager
        mgr = TOTPManager()
        mgr.generate_secret()
        assert mgr.verify("000000") is False

    def test_backup_codes(self):
        from alphastack.security.auth import TOTPManager
        codes = TOTPManager.generate_backup_codes(count=10)
        assert len(codes) == 10
        for code in codes:
            assert len(code) == 8
            assert code.isalnum()

    def test_backup_code_hash_and_verify(self):
        from alphastack.security.auth import TOTPManager
        code = "ABCD1234"
        h = TOTPManager.hash_backup_code(code)
        assert TOTPManager.verify_backup_code(code, h) is True
        assert TOTPManager.verify_backup_code("WRONG123", h) is False


# ===================================================================
# SESSION MANAGEMENT
# ===================================================================

class TestSessionManager:
    def test_create_session(self, session_manager):
        session = session_manager.create(
            user_id="u1", device_id="d1", device_name="Chrome",
            ip_address="1.2.3.4", user_agent="Mozilla/5.0", refresh_token="rt",
        )
        assert session.user_id == "u1"
        assert session.device_id == "d1"
        assert session.is_revoked is False

    def test_revoke_session(self, session_manager):
        session = session_manager.create(
            user_id="u1", device_id="d1", device_name="Chrome",
            ip_address="1.2.3.4", user_agent="", refresh_token="rt",
        )
        session_manager.revoke(session.session_id, "test")
        retrieved = session_manager.get(session.session_id)
        assert retrieved is not None
        assert retrieved.is_revoked is True

    def test_revoke_all_for_user(self, session_manager):
        for i in range(5):
            session_manager.create(
                user_id="u1", device_id=f"d{i}", device_name="test",
                ip_address="1.2.3.4", user_agent="", refresh_token=f"rt{i}",
            )
        count = session_manager.revoke_all_for_user("u1", "logout_all")
        assert count == 5
        assert session_manager.active_count("u1") == 0

    def test_session_limit_enforced(self, session_manager):
        for i in range(15):
            session_manager.create(
                user_id="u1", device_id=f"d{i}", device_name="test",
                ip_address="1.2.3.4", user_agent="", refresh_token=f"rt{i}",
            )
        # Should enforce 10-session limit
        assert session_manager.active_count("u1") <= 10


# ===================================================================
# RATE LIMITER
# ===================================================================

class TestRateLimiter:
    def test_allows_within_limit(self):
        from alphastack.security.auth import RateLimiter
        rl = RateLimiter(rate=10, burst=5)
        for _ in range(5):
            assert rl.allow("ip1") is True

    def test_blocks_when_exhausted(self):
        from alphastack.security.auth import RateLimiter
        rl = RateLimiter(rate=1, burst=2, block_seconds=60)
        assert rl.allow("ip1") is True
        assert rl.allow("ip1") is True
        assert rl.allow("ip1") is False  # Exhausted

    def test_different_keys_independent(self):
        from alphastack.security.auth import RateLimiter
        rl = RateLimiter(rate=1, burst=1)
        assert rl.allow("ip1") is True
        assert rl.allow("ip2") is True
        assert rl.allow("ip1") is False

    def test_reset(self):
        from alphastack.security.auth import RateLimiter
        rl = RateLimiter(rate=1, burst=1)
        rl.allow("ip1")
        assert rl.allow("ip1") is False
        rl.reset("ip1")
        assert rl.allow("ip1") is True


# ===================================================================
# 7-LAYER ORDER VALIDATION PIPELINE
# ===================================================================

class TestOrderValidationPipeline:
    from alphastack.security.validation import OrderValidationPipeline

    VALID_ORDER = {
        "symbol": "EUR/USD",
        "side": "buy",
        "quantity": 1.0,
        "order_type": "limit",
        "price": 1.0850,
        "stop_loss": 1.0800,
        "take_profit": 1.0950,
    }

    VALID_CONTEXT = {
        "current_positions": [],
        "daily_pnl_pct": 0,
        "recent_trades": [],
        "market_volatility": 15,
        "strategy_confidence": 0.85,
        "recent_signals": [],
        "current_prices": {"EUR/USD": 1.0850},
    }

    def test_valid_order_passes(self, order_pipeline):
        result = order_pipeline.validate(self.VALID_ORDER, self.VALID_CONTEXT)
        assert result.passed is True
        assert result.failures == []

    def test_kill_switch_blocks_all(self, order_pipeline, kill_switch):
        kill_switch.activate("test halt", "test")
        order_pipeline._kill_switch = kill_switch
        result = order_pipeline.validate(self.VALID_ORDER, self.VALID_CONTEXT)
        assert result.passed is False
        assert any("kill_switch" in f.layer for f in result.failures)

    def test_missing_stop_loss_rejected(self, order_pipeline):
        order = {**self.VALID_ORDER, "stop_loss": None}
        result = order_pipeline.validate(order, self.VALID_CONTEXT)
        assert result.passed is False
        assert any("stop_loss" in f.reason.lower() for f in result.failures)

    def test_invalid_symbol_rejected(self, order_pipeline):
        order = {**self.VALID_ORDER, "symbol": "FAKE/COIN"}
        result = order_pipeline.validate(order, self.VALID_CONTEXT)
        assert result.passed is False
        assert any("not in the allowed" in f.reason.lower() for f in result.failures)

    def test_invalid_side_rejected(self, order_pipeline):
        order = {**self.VALID_ORDER, "side": "hold"}
        result = order_pipeline.validate(order, self.VALID_CONTEXT)
        assert result.passed is False

    def test_buy_stop_loss_above_entry_rejected(self, order_pipeline):
        order = {**self.VALID_ORDER, "stop_loss": 1.0900}  # Above entry
        result = order_pipeline.validate(order, self.VALID_CONTEXT)
        assert result.passed is False
        assert any("stop-loss" in f.reason.lower() for f in result.failures)

    def test_sell_stop_loss_below_entry_rejected(self, order_pipeline):
        order = {**self.VALID_ORDER, "side": "sell", "stop_loss": 1.0800}  # Below entry for sell
        result = order_pipeline.validate(order, self.VALID_CONTEXT)
        assert result.passed is False

    def test_poor_risk_reward_rejected(self, order_pipeline):
        order = {**self.VALID_ORDER, "take_profit": 1.0860}  # Tiny reward vs risk
        result = order_pipeline.validate(order, self.VALID_CONTEXT)
        assert result.passed is False
        assert any("risk/reward" in f.reason.lower() for f in result.failures)

    def test_order_size_exceeds_limit(self, order_pipeline):
        from alphastack.security.validation import PositionLimits
        limits = PositionLimits(max_order_size=0.5)
        pipeline = OrderValidationPipeline(limits=limits)
        result = pipeline.validate(self.VALID_ORDER, self.VALID_CONTEXT)
        assert result.passed is False
        assert any("order size" in f.reason.lower() for f in result.failures)

    def test_order_value_exceeds_limit(self, order_pipeline):
        from alphastack.security.validation import PositionLimits
        limits = PositionLimits(max_order_value_usd=100)
        pipeline = OrderValidationPipeline(limits=limits)
        order = {**self.VALID_ORDER, "quantity": 1.0, "price": 1000.0,
                 "stop_loss": 900.0, "take_profit": 1200.0}
        ctx = {**self.VALID_CONTEXT, "current_prices": {"EUR/USD": 1000.0}}
        result = pipeline.validate(order, ctx)
        assert result.passed is False

    def test_position_per_symbol_limit(self, order_pipeline):
        positions = [{"symbol": "EUR/USD", "quantity": 49.5, "current_price": 1.0850}]
        ctx = {**self.VALID_CONTEXT, "current_positions": positions}
        result = order_pipeline.validate(self.VALID_ORDER, ctx)
        assert result.passed is False
        assert any("symbol position" in f.reason.lower() for f in result.failures)

    def test_total_positions_limit(self, order_pipeline):
        positions = [{"symbol": f"SYM{i}", "quantity": 1.0, "current_price": 100} for i in range(50)]
        ctx = {**self.VALID_CONTEXT, "current_positions": positions}
        result = order_pipeline.validate(self.VALID_ORDER, ctx)
        assert result.passed is False
        assert any("max" in f.reason.lower() and "positions" in f.reason.lower() for f in result.failures)

    def test_drawdown_exceeded(self, order_pipeline):
        ctx = {**self.VALID_CONTEXT, "daily_pnl_pct": -20.0}
        result = order_pipeline.validate(self.VALID_ORDER, ctx)
        assert result.passed is False
        assert any("drawdown" in f.reason.lower() for f in result.failures)

    def test_price_deviation_rejected(self, order_pipeline):
        order = {**self.VALID_ORDER, "price": 2.0}  # Way off from 1.0850
        ctx = {**self.VALID_CONTEXT, "current_prices": {"EUR/USD": 1.0850}}
        result = order_pipeline.validate(order, ctx)
        assert result.passed is False
        assert any("deviates" in f.reason.lower() for f in result.failures)

    def test_duplicate_order_rejected(self, order_pipeline):
        result1 = order_pipeline.validate(self.VALID_ORDER, self.VALID_CONTEXT)
        assert result1.passed is True
        # Same order immediately → duplicate
        result2 = order_pipeline.validate(self.VALID_ORDER, self.VALID_CONTEXT)
        assert result2.passed is False
        assert any("duplicate" in f.reason.lower() for f in result2.failures)

    def test_market_order_skips_price_check(self, order_pipeline):
        order = {**self.VALID_ORDER, "order_type": "market", "price": None}
        ctx = {**self.VALID_CONTEXT, "current_prices": {"EUR/USD": 1.0850}}
        result = order_pipeline.validate(order, ctx)
        # Should pass price check (market orders don't need it)
        assert not any(f.layer == "price_check" for f in result.failures)


# ===================================================================
# CIRCUIT BREAKER
# ===================================================================

class TestCircuitBreaker:
    def test_no_trigger_under_threshold(self, circuit_breaker):
        ctx = {"daily_pnl_pct": -1.0, "recent_trades": [], "market_volatility": 15}
        assert circuit_breaker.check(ctx) is True
        assert circuit_breaker.is_triggered is False

    def test_daily_loss_triggers(self, circuit_breaker):
        ctx = {"daily_pnl_pct": -10.0}  # Exceeds 5% default
        assert circuit_breaker.check(ctx) is False
        assert circuit_breaker.is_triggered is True
        assert "daily loss" in circuit_breaker.trigger_reason.lower()

    def test_consecutive_losses_trigger(self, circuit_breaker):
        trades = [{"pnl": -100} for _ in range(6)]
        ctx = {"recent_trades": trades}
        assert circuit_breaker.check(ctx) is False
        assert "consecutive" in circuit_breaker.trigger_reason.lower()

    def test_concentration_triggers(self, circuit_breaker):
        positions = [
            {"symbol": "BTC/USDT", "quantity": 10, "current_price": 60000},
            {"symbol": "BTC/USDT", "quantity": 5, "current_price": 60000},
            {"symbol": "ETH/USDT", "quantity": 1, "current_price": 3000},
        ]
        ctx = {"positions": positions}
        assert circuit_breaker.check(ctx) is False
        assert "concentration" in circuit_breaker.trigger_reason.lower()

    def test_volatility_spike_triggers(self, circuit_breaker):
        ctx = {"market_volatility": 50}  # VIX > 40
        assert circuit_breaker.check(ctx) is False
        assert "volatility" in circuit_breaker.trigger_reason.lower()

    def test_low_agent_confidence_triggers(self, circuit_breaker):
        ctx = {"strategy_confidence": 0.3}  # Below 0.6
        assert circuit_breaker.check(ctx) is False
        assert "confidence" in circuit_breaker.trigger_reason.lower()

    def test_contradictory_signals_trigger(self, circuit_breaker):
        signals = [
            {"direction": "long"},
            {"direction": "short"},
            {"direction": "long"},
        ]
        ctx = {"recent_signals": signals, "strategy_confidence": 0.9}
        assert circuit_breaker.check(ctx) is False
        assert "contradictory" in circuit_breaker.trigger_reason.lower()

    def test_reset_requires_operator(self, circuit_breaker):
        ctx = {"daily_pnl_pct": -10.0}
        circuit_breaker.check(ctx)
        assert circuit_breaker.is_triggered is True
        circuit_breaker.reset("admin", "manual review complete")
        assert circuit_breaker.is_triggered is False

    def test_cooldown_auto_reset(self):
        from alphastack.security.validation import CircuitBreaker, CircuitBreakerConfig
        config = CircuitBreakerConfig(cooldown_seconds=0)  # Instant cooldown
        cb = CircuitBreaker(config=config)
        cb._is_triggered = True
        cb._trigger_reason = "test"
        cb._trigger_time = time.time() - 1
        assert cb.check({}) is True  # Should auto-reset after cooldown


# ===================================================================
# KILL SWITCH
# ===================================================================

class TestKillSwitch:
    def test_activate(self, kill_switch):
        kill_switch.activate("emergency", "api")
        assert kill_switch.is_active is True
        assert kill_switch.status["reason"] == "emergency"

    def test_deactivate_requires_auth(self, kill_switch):
        kill_switch.activate("test", "api")
        kill_switch.set_authorization("admin", "secret123")
        # Wrong code
        result = kill_switch.deactivate("admin", "wrong")
        assert result is False
        assert kill_switch.is_active is True
        # Correct code
        result = kill_switch.deactivate("admin", "secret123")
        assert result is True
        assert kill_switch.is_active is False

    def test_double_activate_idempotent(self, kill_switch):
        kill_switch.activate("first", "api")
        kill_switch.activate("second", "api")
        assert kill_switch.is_active is True

    def test_callback_fired_on_activate(self, kill_switch):
        fired = []
        kill_switch.register_activation_callback(lambda: fired.append(True))
        kill_switch.activate("test", "api")
        assert fired == [True]


# ===================================================================
# POSITION LIMITS
# ===================================================================

class TestPositionLimits:
    def test_default_limits_are_immutable(self):
        from alphastack.security.validation import PositionLimits
        limits = PositionLimits()
        with pytest.raises(AttributeError):
            limits.max_order_size = 999  # type: ignore

    def test_allowed_symbols(self):
        from alphastack.security.validation import PositionLimits
        limits = PositionLimits()
        assert "EUR/USD" in limits.allowed_symbols
        assert "BTC/USDT" in limits.allowed_symbols
        assert "FAKE/COIN" not in limits.allowed_symbols

    def test_custom_limits(self):
        from alphastack.security.validation import PositionLimits
        limits = PositionLimits(max_order_size=0.1)
        assert limits.max_order_size == 0.1


# ===================================================================
# ENCRYPTION (AES-256-GCM)
# ===================================================================

class TestEncryptionService:
    def test_encrypt_decrypt_roundtrip(self, encryption_service):
        plaintext = "sensitive-api-key-12345"
        token = encryption_service.encrypt(plaintext)
        decrypted = encryption_service.decrypt(token).decode("utf-8")
        assert decrypted == plaintext

    def test_different_ciphertexts(self, encryption_service):
        plaintext = "same data"
        t1 = encryption_service.encrypt(plaintext)
        t2 = encryption_service.encrypt(plaintext)
        assert t1 != t2  # Different nonces

    def test_tampered_ciphertext_fails(self, encryption_service):
        token = encryption_service.encrypt("secret")
        raw = bytearray(bytes.fromhex(token) if token.startswith("v") else __import__("base64").b64decode(token))
        # Flip a bit in the ciphertext
        if len(raw) > 20:
            raw[-5] ^= 0xFF
        import base64
        tampered = base64.b64encode(bytes(raw)).decode()
        with pytest.raises(Exception):
            encryption_service.decrypt(tampered)

    def test_key_rotation(self, encryption_service):
        old_token = encryption_service.encrypt("before_rotation")
        new_version = encryption_service.rotate()
        assert new_version is not None
        # Old token should still decrypt (grace period)
        assert encryption_service.decrypt(old_token).decode() == "before_rotation"
        # New token uses new key
        new_token = encryption_service.encrypt("after_rotation")
        assert encryption_service.decrypt(new_token).decode() == "after_rotation"

    def test_config_encrypt_decrypt(self, encryption_service, tmp_path):
        config = {"api_key": "secret123", "broker": "binance"}
        config_path = tmp_path / "config.enc"
        encryption_service.encrypt_config(config, config_path)
        decrypted = encryption_service.decrypt_config(config_path)
        assert decrypted == config

    def test_aad_binding(self, encryption_service):
        plaintext = "bound data"
        aad = b"context-info"
        token = encryption_service.encrypt(plaintext, aad=aad)
        # Correct AAD
        assert encryption_service.decrypt(token, aad=aad).decode() == plaintext
        # Wrong AAD should fail
        with pytest.raises(Exception):
            encryption_service.decrypt(token, aad=b"wrong-context")


# ===================================================================
# REQUEST SIGNING
# ===================================================================

class TestRequestSigning:
    def test_compute_and_verify(self):
        from alphastack.security.middleware import compute_request_signature, verify_request_signature
        key = "test-signing-key-2026"
        body = b'{"symbol":"EUR/USD"}'
        sig = compute_request_signature(key, "POST", "/api/v1/trades", 1700000000, body)
        assert len(sig) == 64  # SHA-256 hex
        assert verify_request_signature(key, "POST", "/api/v1/trades", 1700000000, body, sig) is True

    def test_wrong_key_fails(self):
        from alphastack.security.middleware import compute_request_signature, verify_request_signature
        body = b"test"
        sig = compute_request_signature("correct-key", "GET", "/api/v1/data", 1700000000, body)
        assert verify_request_signature("wrong-key", "GET", "/api/v1/data", 1700000000, body, sig) is False

    def test_tampered_body_fails(self):
        from alphastack.security.middleware import compute_request_signature, verify_request_signature
        key = "key123"
        sig = compute_request_signature(key, "POST", "/path", 1700000000, b"original")
        assert verify_request_signature(key, "POST", "/path", 1700000000, b"tampered", sig) is False

    def test_different_method_fails(self):
        from alphastack.security.middleware import compute_request_signature, verify_request_signature
        key = "key123"
        body = b"data"
        sig = compute_request_signature(key, "POST", "/path", 1700000000, body)
        assert verify_request_signature(key, "GET", "/path", 1700000000, body, sig) is False


# ===================================================================
# IP ALLOWLIST
# ===================================================================

class TestIPAllowlist:
    def test_allows_when_no_list(self):
        from alphastack.security.middleware import IPAllowlistMiddleware
        # When no CIDRs configured, all IPs allowed
        mw = IPAllowlistMiddleware.__new__(IPAllowlistMiddleware)
        mw._networks = []
        assert mw._is_allowed("1.2.3.4") is True

    def test_allows_matching_cidr(self):
        from alphastack.security.middleware import IPAllowlistMiddleware
        import ipaddress
        mw = IPAllowlistMiddleware.__new__(IPAllowlistMiddleware)
        mw._networks = [ipaddress.ip_network("10.0.0.0/8")]
        assert mw._is_allowed("10.1.2.3") is True

    def test_blocks_non_matching_ip(self):
        from alphastack.security.middleware import IPAllowlistMiddleware
        import ipaddress
        mw = IPAllowlistMiddleware.__new__(IPAllowlistMiddleware)
        mw._networks = [ipaddress.ip_network("10.0.0.0/8")]
        assert mw._is_allowed("192.168.1.1") is False

    def test_multiple_cidrs(self):
        from alphastack.security.middleware import IPAllowlistMiddleware
        import ipaddress
        mw = IPAllowlistMiddleware.__new__(IPAllowlistMiddleware)
        mw._networks = [
            ipaddress.ip_network("10.0.0.0/8"),
            ipaddress.ip_network("192.168.0.0/16"),
        ]
        assert mw._is_allowed("10.1.2.3") is True
        assert mw._is_allowed("192.168.1.1") is True
        assert mw._is_allowed("172.16.0.1") is False


# ===================================================================
# AUDIT LOGGER
# ===================================================================

class TestAuditLogger:
    def test_log_event(self, tmp_path):
        from alphastack.security.audit import AuditLogger, AuditCategory
        logger = AuditLogger(store_dir=tmp_path / "audit")
        event_hash = logger.log(
            AuditCategory.AUTH,
            "login_success",
            actor_type="user",
            actor_id="test@example.com",
        )
        assert event_hash
        assert len(event_hash) == 64  # SHA-256 hex

    def test_hash_chain_integrity(self, tmp_path):
        from alphastack.security.audit import AuditLogger, AuditCategory
        logger = AuditLogger(store_dir=tmp_path / "audit")
        events = []
        for i in range(5):
            h = logger.log(AuditCategory.SYSTEM, f"event_{i}")
            events.append({"integrity": {"event_hash": h, "previous_hash": logger._previous_hash}})
        # Verify chain
        logger.flush()
        day_file = list((tmp_path / "audit").glob("*.jsonl"))[0]
        import json as _json
        stored_events = [_json.loads(line) for line in day_file.read_text().strip().split("\n")]
        assert logger.verify_chain(stored_events) is True

    def test_convenience_loggers(self, tmp_path):
        from alphastack.security.audit import AuditLogger
        logger = AuditLogger(store_dir=tmp_path / "audit")
        # Trade log
        h1 = logger.log_trade("user1", "order1", "EUR/USD", "buy", "limit", 1.0, 1.085)
        assert h1
        # Agent log
        h2 = logger.log_agent_action("agent_news", "fetch_data")
        assert h2
        # Security log
        h3 = logger.log_security("rate_limit_hit")
        assert h3
