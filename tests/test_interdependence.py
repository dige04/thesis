"""Tests for E7 interdependence machinery (THESIS_REVIEW.md #19/E7).

E7 answers the thesis's load-bearing question: *does memory actually help, and
are the SWE-Bench-CL tasks genuinely interdependent* — or just chronological?
If Full ≈ No-Memory and tasks share no structure, the forgetting question is
moot regardless of policy. These are pure analyses over already-logged data
(resolved-by-position) and the gold patches (touched files); they run on the
gate-3 / full-run output.
"""

import pytest

from src.analysis.interdependence import (
    memory_lift_by_position,
    parse_patch_files,
    sequence_task_files,
    structural_interdependence,
)

# ---------------------------------------------------------------------------
# parse_patch_files — touched files from a unified/git diff
# ---------------------------------------------------------------------------

_GIT_PATCH = """diff --git a/src/foo.py b/src/foo.py
index 1111..2222 100644
--- a/src/foo.py
+++ b/src/foo.py
@@ -1,3 +1,3 @@
-old
+new
diff --git a/tests/test_foo.py b/tests/test_foo.py
--- a/tests/test_foo.py
+++ b/tests/test_foo.py
@@ -0,0 +1 @@
+added
"""


def test_parse_patch_files_git_diff():
    assert parse_patch_files(_GIT_PATCH) == {"src/foo.py", "tests/test_foo.py"}


def test_parse_patch_files_new_file_dev_null():
    patch = "--- /dev/null\n+++ b/pkg/new_module.py\n@@ -0,0 +1 @@\n+x = 1\n"
    assert parse_patch_files(patch) == {"pkg/new_module.py"}


def test_parse_patch_files_empty():
    assert parse_patch_files("") == set()


def test_sequence_task_files_maps_each_patch():
    files = sequence_task_files([_GIT_PATCH, "", "--- a/x.py\n+++ b/x.py\n"])
    assert files == [{"src/foo.py", "tests/test_foo.py"}, set(), {"x.py"}]


# ---------------------------------------------------------------------------
# structural_interdependence — do later tasks touch earlier tasks' files?
# ---------------------------------------------------------------------------


def test_disjoint_tasks_are_not_interdependent():
    result = structural_interdependence([{"a"}, {"b"}, {"c"}])
    assert result["mean_prior_overlap"] == pytest.approx(0.0)
    assert result["frac_tasks_with_dependency"] == pytest.approx(0.0)


def test_fully_reused_files_are_interdependent():
    result = structural_interdependence([{"a"}, {"a"}, {"a"}])
    assert result["mean_prior_overlap"] == pytest.approx(1.0)
    assert result["frac_tasks_with_dependency"] == pytest.approx(1.0)


def test_partial_overlap():
    # task1 {b,c} vs prior {a,b} -> {b}/2 = 0.5; task2 {c,d} vs {a,b,c} -> {c}/2 = 0.5
    result = structural_interdependence([{"a", "b"}, {"b", "c"}, {"c", "d"}])
    assert result["per_task_prior_overlap"] == pytest.approx([0.0, 0.5, 0.5])
    assert result["mean_prior_overlap"] == pytest.approx(0.5)
    assert result["frac_tasks_with_dependency"] == pytest.approx(1.0)


def test_single_task_has_no_dependency():
    result = structural_interdependence([{"a"}])
    assert result["mean_prior_overlap"] == pytest.approx(0.0)
    assert result["frac_tasks_with_dependency"] == pytest.approx(0.0)
    assert result["n_tasks"] == 1


def test_empty_task_files_handled():
    result = structural_interdependence([{"a"}, set(), {"a"}])
    # task with no files contributes 0 overlap and does not crash.
    assert result["per_task_prior_overlap"][1] == pytest.approx(0.0)
    assert result["per_task_prior_overlap"][2] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# memory_lift_by_position — does memory help, and does it help more LATE?
# ---------------------------------------------------------------------------


def test_no_lift_when_identical():
    result = memory_lift_by_position([1, 0, 1, 0], [1, 0, 1, 0])
    assert result["overall_lift"] == pytest.approx(0.0)
    assert result["first_half_lift"] == pytest.approx(0.0)
    assert result["second_half_lift"] == pytest.approx(0.0)


def test_uniform_lift():
    result = memory_lift_by_position([0, 0, 0, 0], [1, 1, 1, 1])
    assert result["overall_lift"] == pytest.approx(1.0)
    assert result["first_half_lift"] == pytest.approx(1.0)
    assert result["second_half_lift"] == pytest.approx(1.0)
    assert result["late_minus_early"] == pytest.approx(0.0)


def test_memory_helps_more_late_is_the_interdependence_signal():
    # No-Memory solves the first half, fails the second; Full solves all.
    # Memory's benefit is concentrated LATE -> positive late_minus_early.
    result = memory_lift_by_position([1, 1, 0, 0], [1, 1, 1, 1])
    assert result["overall_lift"] == pytest.approx(0.5)
    assert result["first_half_lift"] == pytest.approx(0.0)
    assert result["second_half_lift"] == pytest.approx(1.0)
    assert result["late_minus_early"] == pytest.approx(1.0)


def test_mismatched_lengths_raise():
    with pytest.raises(ValueError):
        memory_lift_by_position([1, 0], [1, 0, 1])
