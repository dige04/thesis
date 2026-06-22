from src.agents.langgraph_agent import _truncate_obs, _MAX_OBS


def test_truncate_preserves_tail():
    body = "HEAD" + "x" * (_MAX_OBS * 2) + "FAIL: assert 1 == 2"
    out = _truncate_obs(body)
    assert out.startswith("HEAD")
    assert "FAIL: assert 1 == 2" in out
    assert "chars omitted" in out
    assert len(out) <= _MAX_OBS


def test_truncate_noop_when_short():
    assert _truncate_obs("short") == "short"
