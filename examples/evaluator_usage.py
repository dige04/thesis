"""Example usage of the SWEBenchEvaluator.

This script demonstrates how to use the evaluator to test patches
against the eval_v3 Docker harness.

Note: This is a demonstration script. The actual eval_v3 Docker image
and command structure will be finalized during Spike Week.
"""

from src.benchmark import SWEBenchEvaluator, Task

# Create a sample task
task = Task(
    task_id="django__django-12345",
    repo="django/django",
    base_commit="abc123def456",
    issue_text="Fix bug in authentication middleware",
    test_patch="diff --git a/tests/test_auth.py ...",
    gold_patch="diff --git a/django/auth/middleware.py ...",
    created_at="2023-01-15T10:30:00Z",
    sequence_index=5,
    difficulty_label="medium",
)

# Create evaluator
evaluator = SWEBenchEvaluator(
    docker_image="swebench/eval_v3:latest",
    timeout_seconds=300,
)

# Check if Docker is available (useful for smoke tests)
is_available, error = evaluator.verify_docker_available()
if not is_available:
    print(f"Docker not available: {error}")
    print("Run 'make setup' to build the eval_v3 Docker image")
else:
    print("Docker is available and eval_v3 image found")

    # Evaluate a patch (this will fail until Docker image is built)
    patch = """
diff --git a/django/auth/middleware.py b/django/auth/middleware.py
index abc123..def456 100644
--- a/django/auth/middleware.py
+++ b/django/auth/middleware.py
@@ -10,7 +10,7 @@ class AuthenticationMiddleware:
     def process_request(self, request):
-        request.user = get_user(request)
+        request.user = get_user_safe(request)
         return None
"""

    result = evaluator.evaluate_patch(task, patch)

    print(f"\nEvaluation Result:")
    print(f"  Task ID: {result.task_id}")
    print(f"  Success: {result.success}")
    print(f"  Passed: {result.passed}")
    print(f"  Error: {result.error}")
    print(f"  Execution Time: {result.execution_time:.2f}s")

    # Log result for analysis
    if result.success:
        if result.passed:
            print("\n✓ Patch passed all tests!")
        else:
            print("\n✗ Patch failed tests")
    else:
        print(f"\n⚠ Evaluation error: {result.error}")
