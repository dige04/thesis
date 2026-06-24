# Codex Review Request — A/B Gate STOP, root-cause fix, and a gate-interpretation decision

**You previously approved** the trustworthy-rerun spec (`docs/superpowers/specs/2026-06-22-trustworthy-rerun.md`),
including the A/B instrument-health gate with these GO/STOP criteria:

> STOP if: edit **path/index failures > 0**, OR overall **edit failure ratio > 0.15**, OR
> total_edit_file == 0, OR token inflation (fixed median > 1.5× legacy on prompt/total tokens).
> GO if all pass. Scale to 144 ONLY on 36/36 + GO.

We ran the 36-cell A/B at production config (temp=1, container, experiment_sha 2133b47,
deepseek-v4-flash, 9-worker fleet). **36/36 RUN_COMPLETED, 0 RUN_FAILED.** The gate returned
**STOP**. This document asks you to adversarially review (a) the root-cause fix and (b) a
proposed gate-interpretation that would let us proceed to the 144 — **with explicit attention
to whether that interpretation is goalpost-moving** (a critique you have rightly raised before).

---

## 1. Gate result (STOP)

```json
{
  "gate": "STOP",
  "metrics": {
    "total_edit_file_calls": 567, "failed_edit_file_calls": 172,
    "edit_failure_ratio": 0.303, "edit_path_index_failures": 82,
    "prompt_inflation_ratio": 1.014, "total_inflation_ratio": 1.023
  },
  "reported_deltas": {"resolved_delta": 0.1525, "fixed_resolve_rate": 0.582, "legacy_resolve_rate": 0.429},
  "reasons": ["edit path/index failures == 82 (must be 0)", "edit failure ratio 0.303 > 0.15 threshold"]
}
```
PASS: token inflation 1.01–1.02× (≪1.5×), pairing, no dup, no tool_mode mismatch.

## 2. Root cause: a real bug in the Task-2b fix (now fixed)

`edit_file` (fixed mode) normalised the **diff** paths but compared each normalised diff path
`p` against the **raw, un-normalised** `path` argument:

```python
touched = _collect_diff_paths(diff)   # e.g. 'src/_pytest/unittest.py'
if p != path:                         # path = '/testbed/src/_pytest/unittest.py' (RAW absolute)
    raise ValueError("Security: diff touches '{p}' but path='{path}'")
```

The model legitimately passes the absolute container path (`/testbed/...`) with relative diff
headers. Same file, different normalisation state → false reject. **Verified: 77 of 78 security
rejections satisfy `strip(touched) == strip(path)`** (same file); only 1 is a genuine multi-file
diff (correctly rejected). A second, related gap: `a//testbed/x` (git `a/` prefix + absolute
path → double slash) survived normalisation (2 cases) because the leading slash was stripped
*before* `a/`, so `testbed/` never matched after `a/` removal.

**Fix** (diff in §5): extract module-level `_strip_container_prefix` (strip `a/|b/` once →
`lstrip('/')` → `testbed/` → repo_root), and normalise the `path` ARG up-front in `edit_file`
(before the existence check and the `p != path` guard). 3 regression tests added; **all 25
tests in `tests/test_agents_tools.py` pass, no legacy-mode regression.**

## 3. Decomposition: instrument-attributable vs model-quality

Computed over the existing A/B trajectories (per-failure classification):

| failure class | fixed (567 calls) | legacy (335 calls) | attributable to |
|---|---|---|---|
| security-bug rejection | 77 | 0 | INSTRUMENT (now fixed) |
| normalize gap (`a//testbed`) | 2 | 0 | INSTRUMENT (now fixed) |
| genuine cross-file | 1 | 0 | correct reject (not a failure) |
| malformed diff | 49 | 58 | MODEL |
| wrong-path / file-not-found | 43 | 24 | MODEL |
| **instrument-attributable** | **79 (13.9%) → ~0 post-fix** | **0** | |
| **model-quality** | **92 (16.2%)** | **84 (25.1%)** | |
| total fail ratio | 30.3% | 25.1% | |

Two observations:
- **Discriminator passes:** after the fix, instrument-attributable failures collapse to ~0
  (the deterministic unit tests confirm the exact production cases now apply). No hidden 3rd gap.
- **Model-quality failure RATE is LOWER in fixed (16.2%) than legacy (25.1%)** — the read_file
  line-range / observation-truncation fixes actively reduce the model's diff errors. With
  **+15.3pp resolve rate**, the fixed instrument is unambiguously net-positive.

## 4. The decision we want your review on

Even post-fix, the gate's **total** edit-failure-ratio criterion (0.15) will STILL fail,
because ~16% of edits are **model-quality** failures (deepseek-v4-flash inherently emits
malformed diffs / wrong paths) that **no instrument can prevent**, and which the agent recovers
from via retry/write_file. A blind A/B re-run cannot move this number.

**Proposed interpretation:** instrument health = **instrument-attributable failures → 0**
(path/index + the now-fixed normalisation bug), which the fix achieves and the unit tests
confirm. The 0.15 *total*-ratio criterion conflates **model-quality** diff errors — a disclosed
property of the frozen model, present in BOTH arms and held constant across all 6 policies × 3
seeds — with instrument health. We argue this is the same logic as declared deviations D1–D5
(a factor held constant across conditions does not invalidate between-condition contrasts
H1–H5), NOT a post-hoc redefinition to pass.

**Plan if you concur:** commit the fix → run a 2-task smoke (~$1) → run the 144 → compute
instrument-health (instrument-attributable → 0) ON the 144 data as the final check;
disclose the model-quality edit-error rate in Methods.

### Questions for you (please be adversarial)
1. Is the instrument-vs-model decomposition **principled**, or is it goalpost-moving? Is the
   D1–D5 analogy (factor-held-constant ⇒ non-confounding) valid here?
2. Is "instrument-attributable failures → 0" the right operationalisation of instrument health,
   given the 0.15 total-ratio was pre-registered? Should we instead **lower-bound** by also
   requiring model-quality rate(fixed) ≤ rate(legacy) (currently 16.2% ≤ 25.1% ✓)?
3. Is the fix in §5 correct and complete? Any path shape it still mishandles?
4. Is skipping the A/B re-run (relying on deterministic unit tests for the fix + 144-data for
   instrument-health) defensible, or do you require fresh A/B data before the 144?

## 5. The fix (diff)

```diff
diff --git a/src/agents/tools.py b/src/agents/tools.py
index 5fa220c..bf01c17 100644
--- a/src/agents/tools.py
+++ b/src/agents/tools.py
@@ -405,6 +405,42 @@ class ContainerSession:
         self.stop()
 
 
+def _strip_container_prefix(token: str, repo_root: str | None = None) -> str:
+    """Strip git-diff and container-root prefixes, returning a repo-relative path.
+
+    Handles, in order: the git ``a/``|``b/`` diff prefix (stripped ONCE), any
+    leading slashes (absolute → relative — this also re-exposes a prefix hidden
+    behind ``a/``), the ``testbed/`` container working-dir prefix, and an explicit
+    ``repo_root``.
+
+    The ordering and the ``lstrip("/")`` fix the 2026-06-24 A/B normalize gap:
+    ``a//testbed/x`` (git ``a/`` prefix + absolute ``/testbed/...`` path → double
+    slash) previously survived because the leading slash was stripped BEFORE
+    ``a/``, so after removing ``a/`` the path was ``/testbed/x`` and the
+    ``testbed/`` check (no leading slash expected) never fired. ``/dev/null`` is
+    preserved verbatim (pure add / pure delete diffs).
+    """
+    if token in ("/dev/null", "dev/null"):
+        return token
+    p = token
+    # 1. git diff prefix a/ or b/ — stripped ONCE (it is the -p1 prefix; do not
+    #    iterate, or a real leading directory literally named 'a'/'b' is lost).
+    if p.startswith(("a/", "b/")):
+        p = p[2:]
+    # 2. leading slash(es): absolute → relative; also handles 'a//testbed/...'
+    #    where stripping 'a/' re-exposed a leading '/'.
+    p = p.lstrip("/")
+    # 3. container working-dir prefix
+    if p.startswith("testbed/"):
+        p = p[len("testbed/"):]
+    # 4. backend-resolved repo root (absolute working dir, e.g. 'home/user/repo/')
+    if repo_root:
+        root = repo_root.strip("/") + "/"
+        if root != "/" and p.startswith(root):
+            p = p[len(root):]
+    return p
+
+
 def _normalize_diff_paths(diff: str, repo_root: str | None) -> str:
     """Rewrite diff path headers so that ``git apply -p1`` can apply them.
 
@@ -425,26 +461,8 @@ def _normalize_diff_paths(diff: str, repo_root: str | None) -> str:
     """
 
     def _strip_path(token: str) -> str:
-        """Strip known prefixes and return a repo-relative path."""
-        if token in ("/dev/null", "dev/null"):
-            return token
-        p = token
-        # 1. Strip leading slash
-        if p.startswith("/"):
-            p = p[1:]
-        # 2. Strip a/ or b/ git diff prefix (must happen early so subsequent
-        #    checks see the bare path, e.g. "a/testbed/m.py" → "testbed/m.py")
-        if p.startswith(("a/", "b/")):
-            p = p[2:]
-        # 3. Strip "testbed/" container prefix
-        if p.startswith("testbed/"):
-            p = p[len("testbed/"):]
-        # 4. Strip repo_root prefix (absolute, e.g. "home/user/repo/m.py")
-        if repo_root:
-            root = repo_root.strip("/") + "/"
-            if p.startswith(root):
-                p = p[len(root):]
-        return p
+        """Strip known prefixes and return a repo-relative path (module helper)."""
+        return _strip_container_prefix(token, repo_root)
 
     def _reanchor(prefix: str, token: str) -> str:
         """Return ``prefix/<relpath>`` preserving /dev/null verbatim."""
@@ -648,7 +666,22 @@ class AgentTools:
         """
         args = {"path": path, "diff_length": len(diff)}
 
-        # ── 1. existence check first (keeps existing test_edit_file behaviour) ──
+        # ── 0. (fixed mode) normalise the path ARG up-front ───────────────────
+        # The model usually passes the absolute container path ('/testbed/src/x.py')
+        # while the diff headers are relative ('a/src/x.py'). Normalising path here
+        # (BEFORE the existence check and the security comparison) ensures all three
+        # — exists(), the `p != path` guard, and git apply — see the same
+        # repo-relative path. Without this, the guard compared the normalised diff
+        # path against the RAW absolute arg → 77/78 false rejections in the
+        # 2026-06-24 A/B. `args` keeps the original path for logging fidelity.
+        repo_root: str | None = None
+        if tool_mode() == "fixed":
+            raw_root = getattr(self.backend, "working_dir", None) or getattr(self.backend, "repo_dir", None)
+            if raw_root is not None:
+                repo_root = str(raw_root).rstrip("/")
+            path = _strip_container_prefix(path, repo_root)
+
+        # ── 1. existence check (on the normalised path in fixed mode) ──────────
         if not self.backend.exists(path):
             error = f"File not found: {path}"
             self.tracker.record_call("edit_file", args, None, error)
@@ -659,11 +692,6 @@ class AgentTools:
 
         if tool_mode() == "fixed":
             # ── 2. normalise container-root / absolute path headers ───────────
-            # Resolve repo_root from whichever attribute the backend exposes.
-            repo_root: str | None = None
-            raw_root = getattr(self.backend, "working_dir", None) or getattr(self.backend, "repo_dir", None)
-            if raw_root is not None:
-                repo_root = str(raw_root).rstrip("/")
             diff = _normalize_diff_paths(diff, repo_root)
 
             # ── 3. security validation — before any disk write ────────────────
diff --git a/tests/test_agents_tools.py b/tests/test_agents_tools.py
index 1963631..b1c4c29 100644
--- a/tests/test_agents_tools.py
+++ b/tests/test_agents_tools.py
@@ -353,6 +353,61 @@ def test_edit_file_absolute_testbed_path_applies(git_repo):
     assert (git_repo / "m.py").read_text() == "x = 42\n"
 
 
+def test_edit_file_absolute_path_arg_applies(git_repo):
+    """path='/testbed/m.py' (absolute container path) + relative diff headers must
+    normalise BOTH sides and apply.
+
+    Regression for the 2026-06-24 A/B STOP: 77/78 'security rejections' were false
+    because the guard compared the NORMALISED diff path ('m.py') against the RAW
+    absolute `path` arg ('/testbed/m.py') → false 'diff touches m.py but
+    path=/testbed/m.py'. The LLM legitimately passes the absolute container path."""
+    tools = AgentTools(str(git_repo))
+    diff = (
+        "--- a/m.py\n"
+        "+++ b/m.py\n"
+        "@@ -1 +1 @@\n"
+        "-x = 1\n"
+        "+x = 7\n"
+    )
+    tools.edit_file("/testbed/m.py", diff)
+    assert (git_repo / "m.py").read_text() == "x = 7\n"
+
+
+def test_edit_file_double_slash_testbed_applies(git_repo):
+    """diff headers '--- a//testbed/m.py' (git 'a/' prefix + absolute '/testbed/...'
+    path → double slash) must normalise and apply.
+
+    Regression for the 2026-06-24 A/B normalize gap: `_strip_path` stripped 'a/'
+    then failed to re-strip the now-exposed leading '/' before the 'testbed/'
+    check, so 'a//testbed/m.py' survived → git apply 'b/testbed/...: No such file'."""
+    tools = AgentTools(str(git_repo))
+    diff = (
+        "--- a//testbed/m.py\n"
+        "+++ b//testbed/m.py\n"
+        "@@ -1 +1 @@\n"
+        "-x = 1\n"
+        "+x = 5\n"
+    )
+    tools.edit_file("/testbed/m.py", diff)
+    assert (git_repo / "m.py").read_text() == "x = 5\n"
+
+
+def test_edit_file_cross_file_rejected_with_abs_path_arg(git_repo):
+    """Even with an absolute path arg, a diff touching a DIFFERENT file must still
+    be rejected — the fix must not over-permit after normalising both sides."""
+    tools = AgentTools(str(git_repo))
+    diff = (
+        "--- a/other.py\n"
+        "+++ b/other.py\n"
+        "@@ -1 +1 @@\n"
+        "-y = 2\n"
+        "+y = 9\n"
+    )
+    with pytest.raises(ValueError, match=r"(?i)(security|other\.py|path)"):
+        tools.edit_file("/testbed/m.py", diff)
+    assert (git_repo / "m.py").read_text() == "x = 1\n"
+
+
 def test_edit_file_cross_file_rejected(git_repo):
     """A diff touching other.py while path='m.py' must raise ValueError; m.py unchanged."""
     tools = AgentTools(str(git_repo))
```
