"""Unit tests for the pure parts of backend/auth.py (hashing, tokens, policy, helpers)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import auth  # noqa: E402
from guards import rate_limit  # noqa: E402


def test_password_hash_roundtrip():
    stored = auth.hash_password("correct horse battery")
    assert stored.startswith("pbkdf2_sha256$")
    assert auth.verify_password("correct horse battery", stored)


def test_wrong_password_rejected():
    assert not auth.verify_password("wrong", auth.hash_password("right-password"))


def test_hashes_are_salted():
    assert auth.hash_password("same-password") != auth.hash_password("same-password")


@pytest.mark.parametrize("bad", ["", "not-a-hash", "md5$1$aa$bb", "pbkdf2_sha256$x$zz$yy"])
def test_malformed_stored_hash_never_verifies(bad):
    assert auth.verify_password("anything", bad) is False


def test_token_hash_is_deterministic_and_hides_the_token():
    digest = auth.hash_token("abc123")
    assert digest == auth.hash_token("abc123")
    assert len(digest) == 64 and "abc123" not in digest


@pytest.mark.parametrize("pw,expected_problem", [("short", True), ("12345678", True), ("Password", True), ("Tr0ub4dor&3", False), ("a-decent-passphrase", False)])
def test_password_policy(pw, expected_problem):
    assert (auth.check_password_strength(pw) is not None) == expected_problem


def test_email_html_contains_link_and_branding():
    html = auth._email_html("Hello", "Intro", "Go", "https://example.com/verify.html?token=t", "Footer")
    assert "https://example.com/verify.html?token=t" in html and "Radar" in html


class _Req:
    def __init__(self, scheme="http", headers=None):
        self.url = type("U", (), {"scheme": scheme})()
        self.headers = headers or {}


def test_https_detection_behind_a_proxy():
    assert auth._is_https(_Req("http", {"x-forwarded-proto": "https"}))
    assert auth._is_https(_Req("https"))
    assert not auth._is_https(_Req("http"))


def test_rate_limit_blocks_after_cap():
    check = rate_limit("unit-test-bucket", per_ip=2, overall=10)
    req = type("R", (), {"headers": {"x-forwarded-for": "9.9.9.9"}, "client": None})()
    check(req)
    check(req)
    with pytest.raises(Exception) as exc:
        check(req)
    assert getattr(exc.value, "status_code", None) == 429


def test_verification_email_escapes_a_hostile_name_but_keeps_the_link():
    text, body = auth.verification_email('<script>alert(1)</script>', "https://x.test/verify.html?token=abc")
    assert "<script>" not in body and "&lt;script&gt;" in body
    assert "https://x.test/verify.html?token=abc" in body and "https://x.test/verify.html?token=abc" in text


def test_reset_email_contains_the_link():
    text, body = auth.reset_email("https://x.test/reset.html?token=zzz")
    assert "https://x.test/reset.html?token=zzz" in text and "https://x.test/reset.html?token=zzz" in body


def test_send_email_uses_brevo_payload(monkeypatch):
    import asyncio
    import auth
    seen = {}

    class FakeResp:
        status_code = 201
        text = ""

    class FakeClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, headers=None, json=None):
            seen.update(url=url, headers=headers, json=json)
            return FakeResp()

    monkeypatch.setenv("BREVO_API_KEY", "k")
    monkeypatch.setenv("EMAIL_FROM", "RoleRadar <me@gmail.com>")
    monkeypatch.setattr(auth.httpx, "AsyncClient", FakeClient)
    assert asyncio.run(auth.send_email("u@x.com", "S", "<b>h</b>", "t")) is True
    assert seen["url"] == "https://api.brevo.com/v3/smtp/email"
    assert seen["headers"] == {"api-key": "k"}
    assert seen["json"]["sender"] == {"name": "RoleRadar", "email": "me@gmail.com"}
    assert seen["json"]["to"] == [{"email": "u@x.com"}]
