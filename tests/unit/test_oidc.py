from tracefix.api.oidc import pkce_pair, start_authorization_code, validate_id_token_claims


def test_pkce_and_authorize_url():
    verifier, challenge = pkce_pair()
    assert verifier and challenge and verifier != challenge
    started = start_authorization_code(
        issuer="http://localhost:8081/realms/tracefix",
        client_id="tracefix",
        redirect_uri="http://127.0.0.1:8080/v1/auth/oidc/callback",
        audience="tracefix",
    )
    assert "code_challenge" in started.authorization_url
    assert "state=" in started.authorization_url
    assert started.nonce


def test_id_token_claims_validated():
    claims = {
        "iss": "http://localhost:8081/realms/tracefix",
        "aud": "tracefix",
        "nonce": "n1",
        "email": "maintainer@tracefix.local",
        "sub": "owner-a",
    }
    out = validate_id_token_claims(
        claims,
        issuer="http://localhost:8081/realms/tracefix",
        audience="tracefix",
        nonce="n1",
    )
    assert out["email"].startswith("maintainer")
    try:
        validate_id_token_claims(claims, issuer="https://evil", audience="tracefix", nonce="n1")
        assert False
    except PermissionError:
        pass
