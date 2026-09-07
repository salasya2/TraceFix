from tracefix.github.signature import sign_body, verify_webhook_signature


def test_accepts_valid_signature():
    body = b'{"ok": true}'
    secret = "super-secret"
    header = sign_body(secret=secret, body=body)
    assert verify_webhook_signature(secret=secret, body=body, header=header)


def test_rejects_forged_and_modified():
    body = b'{"ok": true}'
    secret = "super-secret"
    header = sign_body(secret=secret, body=body)
    assert not verify_webhook_signature(secret=secret, body=b'{"ok": false}', header=header)
    assert not verify_webhook_signature(secret="other", body=body, header=header)
    assert not verify_webhook_signature(secret=secret, body=body, header="sha256=deadbeef")
    assert not verify_webhook_signature(secret=secret, body=body, header=None)
