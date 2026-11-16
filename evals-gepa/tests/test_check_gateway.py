import check_gateway
import gateway


def test_ok(stand_in, capsys):
    assert check_gateway.main() == 0
    out = capsys.readouterr().out
    assert "qwen3.6-35b-a3b" in out and "CAD" in out and "OK" in out


def test_token_not_set(stand_in, monkeypatch, capsys):
    monkeypatch.delenv("KB_MCP_TOKEN")
    assert check_gateway.main() == 1
    assert "KB_MCP_TOKEN is not set" in capsys.readouterr().out


def test_401_wrong_token(stand_in, monkeypatch, capsys):
    monkeypatch.setenv("KB_MCP_TOKEN", "not-my-token")
    assert check_gateway.main() == 1
    assert "401" in capsys.readouterr().out


def test_403_model_not_allowed(stand_in, monkeypatch, capsys):
    monkeypatch.setattr(gateway, "WORKER", "gpt-5.4-nano")
    assert check_gateway.main() == 1
    out = capsys.readouterr().out
    assert "403" in out and "qwen3.6-35b-a3b" in out


def test_502_once_then_retry_ok(stand_in, capsys):
    stand_in.fail_502 = 1
    assert check_gateway.main() == 0
    assert stand_in.chat_calls == 2
    assert "502 from the gateway, retry 1 of 3" in capsys.readouterr().err


def test_502_every_time_gives_plain_message(stand_in, capsys):
    stand_in.fail_502 = 10
    assert check_gateway.main() == 1
    assert stand_in.chat_calls == 1 + gateway.RETRIES_502
    assert "502: the model behind the gateway did not answer" in capsys.readouterr().out


def test_timeout_has_its_own_message():
    import httpx
    import openai

    e = openai.APITimeoutError(request=httpx.Request("POST", "http://x"))
    assert "longer than 90 s" in gateway.plain(e)
