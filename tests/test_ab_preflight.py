"""Preflight tests for the post-hotfix A/B (Codex 2026-06-24 review).

Proves, BEFORE any compute, that:
  - shard_units enumerates per-unit tool_mode (worker-field + modulo modes);
  - the A/B manifest has 36 cells, complete pairing, pairs co-located on one worker;
  - the amended gate BLOCKS on missing/incomplete/RUN_FAILED/provenance/unpaired,
    STOPs on instrument!=0 / inflation>1.5x / model-rate fixed>legacy,
    GOes on clean data, and does NOT use the retired 0.15 total-ratio.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.shard_units import enumerate_units
from scripts.build_ab_manifest import build_ab_manifest, build_worker_map
from scripts.ab_gate_amended import ab_gate_amended, classify_edit_failure
from scripts.ab_schedule import ab_schedule

SHA = "cceb3253d7b7cfeae16123af30197a8271e1d84a"
CFG = "2e7f341cc35d31c2"


# ---------------------------------------------------------------------------
# shard_units: per-unit tool_mode
# ---------------------------------------------------------------------------

def _write_manifest(tmp_path, runs) -> str:
    p = tmp_path / "m.json"
    p.write_text(json.dumps({"runs": runs}), encoding="utf-8")
    return str(p)


def test_shard_units_worker_field_selects_by_worker_and_emits_tool_mode(tmp_path):
    runs = [
        {"run_id": "a_legacy", "policy": "p", "seed": 1, "sequence_name": "s", "tool_mode": "legacy", "worker": 0},
        {"run_id": "a_fixed", "policy": "p", "seed": 1, "sequence_name": "s", "tool_mode": "fixed", "worker": 0},
        {"run_id": "b_legacy", "policy": "p", "seed": 2, "sequence_name": "s", "tool_mode": "legacy", "worker": 1},
    ]
    units = enumerate_units(_write_manifest(tmp_path, runs), shard=0, num=9)
    assert {u["run_id"] for u in units} == {"a_legacy", "a_fixed"}
    assert {u["run_id"]: u["tool_mode"] for u in units} == {"a_legacy": "legacy", "a_fixed": "fixed"}


def test_shard_units_modulo_fallback_when_no_worker_field(tmp_path):
    runs = [
        {"run_id": f"r{i}", "policy": "p", "seed": 1, "sequence_name": "s", "tool_mode": "fixed"}
        for i in range(4)
    ]
    units = enumerate_units(_write_manifest(tmp_path, runs), shard=1, num=2)
    assert {u["run_id"] for u in units} == {"r1", "r3"}  # index % 2 == 1


def test_shard_units_tool_mode_defaults_empty_when_absent(tmp_path):
    runs = [{"run_id": "r0", "policy": "p", "seed": 1, "sequence_name": "s"}]
    units = enumerate_units(_write_manifest(tmp_path, runs), shard=0, num=1)
    assert units[0]["tool_mode"] == ""  # runner falls back to AGENT_TOOL_MODE env


# ---------------------------------------------------------------------------
# build_ab_manifest: 36 cells, paired, co-located
# ---------------------------------------------------------------------------

def test_ab_manifest_36_cells_all_paired_and_colocated():
    m = build_ab_manifest()
    assert m["n_runs"] == 36
    assert m["experiment_sha"] == SHA
    pairs: dict[tuple, dict[str, int]] = {}
    for r in m["runs"]:
        assert r["tool_mode"] in ("legacy", "fixed")
        pairs.setdefault((r["sequence_name"], r["policy"], r["seed"]), {})[r["tool_mode"]] = r["worker"]
    assert len(pairs) == 18
    for key, modes in pairs.items():
        assert set(modes) == {"legacy", "fixed"}, f"{key} unpaired: {modes}"
        assert modes["legacy"] == modes["fixed"], f"{key} split across workers: {modes}"


def test_worker_map_covers_all_runs():
    m = build_ab_manifest()
    wm = build_worker_map(m)
    flat = [rid for ids in wm["workers"].values() for rid in ids]
    assert sorted(flat) == sorted(r["run_id"] for r in m["runs"])


# ---------------------------------------------------------------------------
# classify_edit_failure
# ---------------------------------------------------------------------------

def test_classify_false_security_reject_is_instrument():
    obs = ("ERROR: tool 'edit_file' failed: Security: diff touches 'src/x.py' but "
           "path='/testbed/src/x.py'. The diff must only modify ...")
    assert classify_edit_failure(obs) == "instrument"


def test_classify_genuine_cross_file_is_correct_reject():
    obs = ("ERROR: tool 'edit_file' failed: Security: diff touches 'other.py' but "
           "path='m.py'. The diff must only modify ...")
    assert classify_edit_failure(obs) == "correct_reject"


def test_classify_normalize_gap_is_instrument():
    obs = ("ERROR: tool 'edit_file' failed: Could not apply the diff to "
           "/testbed/sklearn/x.py: error: b/testbed/sklearn/x.py: No such file or directory")
    assert classify_edit_failure(obs) == "instrument"


def test_classify_corrupt_patch_is_model():
    obs = ("ERROR: tool 'edit_file' failed: Could not apply the diff to src/x.py: "
           "error: corrupt patch at line 5")
    assert classify_edit_failure(obs) == "model"


def test_classify_success_is_none():
    assert classify_edit_failure("Edited src/x.py") is None


# ---------------------------------------------------------------------------
# amended gate fixtures
# ---------------------------------------------------------------------------

_SEQ_TASKS = {
    "pytest-dev_pytest_sequence": ["p-1", "p-2"],
    "scikit-learn_scikit-learn_sequence": ["s-1", "s-2"],
}
OBS_OK = "Edited m.py"
OBS_INSTRUMENT = ("ERROR: tool 'edit_file' failed: Security: diff touches 'src/x.py' but "
                  "path='/testbed/src/x.py'. ...")
OBS_MODEL = ("ERROR: tool 'edit_file' failed: Could not apply the diff to src/x.py: "
             "error: corrupt patch at line 5")


def _write_run(root, run_id, mode, sha, cfg, task_ids, edit_obs, tokens):
    d = root / run_id
    (d / "trajectories").mkdir(parents=True)
    (d / "RUN_COMPLETED.json").write_text(json.dumps({
        "experiment_sha": sha, "config_hash": cfg, "manifest_hash": "x",
        "tool_mode": mode, "task_count": len(task_ids), "validated_at": "t",
    }), encoding="utf-8")
    rows = [{"task_id": t, "prompt_tokens": tokens[0], "total_tokens": tokens[1],
             "resolved": 0, "tool_mode": mode} for t in task_ids]
    (d / "task_results.jsonl").write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    steps = [{"step": i, "action": "edit_file", "observation_summary": o} for i, o in enumerate(edit_obs)]
    (d / "trajectories" / f"{task_ids[0]}.json").write_text(json.dumps({"steps": steps}), encoding="utf-8")


def _make_tree(root, sha=SHA, cfg=CFG, fixed_obs=(OBS_OK,), legacy_obs=(OBS_OK,),
               fixed_tokens=(1000, 1200), legacy_tokens=(1000, 1200)):
    for c in ab_schedule(20260622):
        tids = _SEQ_TASKS[c["sequence_name"]]
        if c["tool_mode"] == "fixed":
            _write_run(root, c["run_id"], "fixed", sha, cfg, tids, list(fixed_obs), fixed_tokens)
        else:
            _write_run(root, c["run_id"], "legacy", sha, cfg, tids, list(legacy_obs), legacy_tokens)


def test_amended_gate_go_on_clean_tree(tmp_path):
    _make_tree(tmp_path)
    r = ab_gate_amended(tmp_path, expected_sha=SHA, expected_config_hash=CFG)
    assert r["gate"] == "GO", r


def test_amended_gate_blocked_missing_run(tmp_path):
    _make_tree(tmp_path)
    # remove one run dir
    rid = ab_schedule(20260622)[0]["run_id"]
    import shutil
    shutil.rmtree(tmp_path / rid)
    r = ab_gate_amended(tmp_path, expected_sha=SHA)
    assert r["gate"] == "BLOCKED" and "missing" in r["reason"]


def test_amended_gate_blocked_run_failed(tmp_path):
    _make_tree(tmp_path)
    rid = ab_schedule(20260622)[0]["run_id"]
    (tmp_path / rid / "RUN_FAILED.json").write_text("{}", encoding="utf-8")
    r = ab_gate_amended(tmp_path, expected_sha=SHA)
    assert r["gate"] == "BLOCKED" and "RUN_FAILED" in r["reason"]


def test_amended_gate_blocked_wrong_sha(tmp_path):
    _make_tree(tmp_path, sha="deadbeef")
    r = ab_gate_amended(tmp_path, expected_sha=SHA)
    assert r["gate"] == "BLOCKED" and "experiment_sha" in r["reason"]


def test_amended_gate_blocked_wrong_tool_mode(tmp_path):
    _make_tree(tmp_path)
    # corrupt one run's recorded tool_mode
    rid = next(c["run_id"] for c in ab_schedule(20260622) if c["tool_mode"] == "fixed")
    p = tmp_path / rid / "RUN_COMPLETED.json"
    d = json.loads(p.read_text()); d["tool_mode"] = "legacy"; p.write_text(json.dumps(d))
    r = ab_gate_amended(tmp_path, expected_sha=SHA)
    assert r["gate"] == "BLOCKED" and "tool_mode" in r["reason"]


def test_amended_gate_blocked_wrong_config_hash(tmp_path):
    _make_tree(tmp_path, cfg="badcfg")
    r = ab_gate_amended(tmp_path, expected_sha=SHA, expected_config_hash=CFG)
    assert r["gate"] == "BLOCKED" and "config_hash" in r["reason"]


def test_amended_gate_blocked_unpaired_task_ids(tmp_path):
    _make_tree(tmp_path)
    # mutate one fixed run's task_results so its task_ids differ from its legacy pair
    rid = next(c["run_id"] for c in ab_schedule(20260622) if c["tool_mode"] == "fixed")
    p = tmp_path / rid / "task_results.jsonl"
    p.write_text(json.dumps({"task_id": "ODD", "prompt_tokens": 1, "total_tokens": 1,
                             "resolved": 0, "tool_mode": "fixed"}), encoding="utf-8")
    r = ab_gate_amended(tmp_path, expected_sha=SHA)
    assert r["gate"] == "BLOCKED" and "task_ids" in r["reason"]


def test_amended_gate_blocked_task_row_tool_mode_mismatch(tmp_path):
    """A run whose RUN_COMPLETED.tool_mode is CORRECT but whose task_results rows
    carry the WRONG tool_mode must BLOCK — data from the other mode was written
    into this dir. Codex 2026-06-24 reproduction: sentinel check alone returned GO.
    """
    _make_tree(tmp_path)
    rid = next(c["run_id"] for c in ab_schedule(20260622) if c["tool_mode"] == "fixed")
    # sentinel stays "fixed"; rewrite the task rows to "legacy".
    p = tmp_path / rid / "task_results.jsonl"
    rows = [json.loads(line) for line in p.read_text().splitlines() if line.strip()]
    for r in rows:
        r["tool_mode"] = "legacy"
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    # sentinel must still be the correct mode (proves the gap is row-level)
    sent = json.loads((tmp_path / rid / "RUN_COMPLETED.json").read_text())
    assert sent["tool_mode"] == "fixed"
    r = ab_gate_amended(tmp_path, expected_sha=SHA)
    assert r["gate"] == "BLOCKED" and "tool_mode" in r["reason"]


def test_amended_gate_stop_on_instrument_failure(tmp_path):
    # fixed arm has a false-security (instrument) failure
    _make_tree(tmp_path, fixed_obs=(OBS_OK, OBS_INSTRUMENT), legacy_obs=(OBS_OK,))
    r = ab_gate_amended(tmp_path, expected_sha=SHA)
    assert r["gate"] == "STOP" and any("instrument" in x for x in r["reasons"])


def test_amended_gate_stop_on_token_inflation(tmp_path):
    _make_tree(tmp_path, fixed_tokens=(3000, 3600), legacy_tokens=(1000, 1200))
    r = ab_gate_amended(tmp_path, expected_sha=SHA)
    assert r["gate"] == "STOP" and any("inflation" in x for x in r["reasons"])


def test_amended_gate_stop_when_fixed_model_rate_exceeds_legacy(tmp_path):
    # fixed all-model-fail, legacy all-clean -> fixed model rate > legacy
    _make_tree(tmp_path, fixed_obs=(OBS_MODEL, OBS_MODEL), legacy_obs=(OBS_OK,))
    r = ab_gate_amended(tmp_path, expected_sha=SHA)
    assert r["gate"] == "STOP" and any("model-quality" in x for x in r["reasons"])


def test_amended_gate_go_despite_high_model_ratio_proves_no_0_15_rule(tmp_path):
    # BOTH arms have a high model-failure ratio (0.5 >> 0.15) but instrument==0,
    # inflation==1.0, and fixed model-rate == legacy -> GO. The OLD 0.15 gate
    # would STOP here; the amended gate must NOT.
    _make_tree(tmp_path, fixed_obs=(OBS_OK, OBS_MODEL), legacy_obs=(OBS_OK, OBS_MODEL))
    r = ab_gate_amended(tmp_path, expected_sha=SHA)
    assert r["gate"] == "GO", r
    assert r["metrics"]["fixed"]["model_quality_rate"] == 0.5  # > 0.15, yet GO
