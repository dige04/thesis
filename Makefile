.PHONY: help setup verify-env smoke pilot run-condition run-all aggregate stats plots lint test typecheck cost-report clean

# Default target
help:
	@echo "Memory Pruning Research System - Makefile"
	@echo ""
	@echo "Environment Setup:"
	@echo "  make setup          - Install dependencies and build Docker images"
	@echo "  make verify-env     - Check API keys, VPS resources, FAISS, Docker"
	@echo ""
	@echo "Spike Week (Calibration):"
	@echo "  make smoke          - 3-task smoke run on eval_v3 (Day 1 gate: >15%% pass = GO)"
	@echo "  make pilot          - 2 sequences × 6 policies × 1 seed = 12 runs"
	@echo ""
	@echo "Full Experiment:"
	@echo "  make run-condition  - Run single condition (requires POLICY= and SEED=)"
	@echo "  make run-all        - Execute all 144 runs (long-running, monitored)"
	@echo ""
	@echo "Analysis:"
	@echo "  make aggregate      - Aggregate raw results into summary tables"
	@echo "  make stats          - Run statistical tests (Wilcoxon, GLMM, bootstrap)"
	@echo "  make plots          - Generate all plots and visualizations"
	@echo ""
	@echo "Development:"
	@echo "  make lint           - Run ruff linter"
	@echo "  make test           - Run pytest test suite"
	@echo "  make typecheck      - Run mypy type checker"
	@echo ""
	@echo "Monitoring:"
	@echo "  make cost-report    - Generate daily cost summary from wandb"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean          - Remove build artifacts and caches"

# ─────────────────────────────────────────────────────────────────
# Environment Setup
# ─────────────────────────────────────────────────────────────────

setup:
	@echo "Setting up environment..."
	@echo "TODO: Implement during Spike Week"
	@echo "  - Create Python 3.11+ virtual environment"
	@echo "  - Install dependencies from pyproject.toml"
	@echo "  - Build Docker images for eval_v3"
	@echo "  - Initialize FAISS indices"
	@echo "  - Verify API keys in .env"

verify-env:
	@echo "Verifying environment..."
	@echo "TODO: Implement during Spike Week"
	@echo "  - Check Python version >= 3.11"
	@echo "  - Check API keys (OPENAI_API_KEY, ANTHROPIC_API_KEY)"
	@echo "  - Check VPS resources (32GB RAM, 250GB disk, 8 cores)"
	@echo "  - Check Docker daemon running"
	@echo "  - Check FAISS installation"
	@echo "  - Check wandb login"

# ─────────────────────────────────────────────────────────────────
# Spike Week (Calibration)
# ─────────────────────────────────────────────────────────────────

smoke:
	@echo "Running smoke test (3 tasks)..."
	@echo "TODO: Implement during Spike Week"
	@echo "  - Load 3 tasks from one sequence"
	@echo "  - Execute with No Memory policy"
	@echo "  - Verify eval_v3 Docker invocation"
	@echo "  - Verify logging schemas"
	@echo "  - Gate: >15%% pass rate = GO for full experiment"

pilot:
	@echo "Running pilot experiment (12 runs)..."
	@echo "TODO: Implement during Spike Week"
	@echo "  - 2 sequences × 6 policies × 1 seed = 12 runs"
	@echo "  - Verify all policies execute without crashes"
	@echo "  - Verify memory snapshots generated"
	@echo "  - Verify cost tracking accurate"
	@echo "  - Gate: Calibrate top_k and max_context_tokens"

# ─────────────────────────────────────────────────────────────────
# Full Experiment
# ─────────────────────────────────────────────────────────────────

run-condition:
	@echo "Running single condition..."
	@echo "TODO: Implement during Week 5"
	@echo "  - Requires POLICY= and SEED= environment variables"
	@echo "  - Example: make run-condition POLICY=type_aware_decay SEED=1"
	@echo "  - Executes all 8 sequences for specified policy and seed"

run-all:
	@echo "Running full experiment (144 runs)..."
	@echo "TODO: Implement during Week 5"
	@echo "  - 8 sequences × 6 policies × 3 seeds = 144 runs"
	@echo "  - Long-running (estimated 7-10 days)"
	@echo "  - Monitored via wandb + tmux"
	@echo "  - Automatic cost tracking and alerts"

# ─────────────────────────────────────────────────────────────────
# Analysis
# ─────────────────────────────────────────────────────────────────

aggregate:
	@echo "Aggregating results..."
	@echo "TODO: Implement during Week 6"
	@echo "  - Read all task_results.jsonl files"
	@echo "  - Compute sequence-level means"
	@echo "  - Generate accuracy matrices"
	@echo "  - Compute CL-F1, Plasticity, Stability"
	@echo "  - Output to results/aggregated/"

stats:
	@echo "Running statistical tests..."
	@echo "TODO: Implement during Week 6"
	@echo "  - Wilcoxon signed-rank on 5 pre-registered contrasts"
	@echo "  - Holm correction for multiple comparisons"
	@echo "  - Bootstrap BCa confidence intervals (5000 iterations)"
	@echo "  - Task-level GLMM with crossed random effects"
	@echo "  - Feature importance (PR-AUC + VIF check)"
	@echo "  - Output to results/aggregated/stats.json"

plots:
	@echo "Generating plots..."
	@echo "TODO: Implement during Week 6"
	@echo "  - Pareto frontier (CL-F1 vs cost)"
	@echo "  - Sequence-level performance by policy"
	@echo "  - Memory growth over time"
	@echo "  - Retrieval quality metrics"
	@echo "  - Behavioral metrics (tool calls, syntax errors)"
	@echo "  - Output to results/plots/"

# ─────────────────────────────────────────────────────────────────
# Development
# ─────────────────────────────────────────────────────────────────

lint:
	@echo "Running ruff linter..."
	ruff check src/ tests/

test:
	@echo "Running pytest..."
	pytest tests/ -v --cov=src --cov-report=term-missing

typecheck:
	@echo "Running mypy type checker..."
	mypy src/ --strict

# ─────────────────────────────────────────────────────────────────
# Monitoring
# ─────────────────────────────────────────────────────────────────

cost-report:
	@echo "Generating cost report..."
	@echo "TODO: Implement during Week 5"
	@echo "  - Query wandb for all active runs"
	@echo "  - Aggregate costs by policy, sequence, date"
	@echo "  - Generate daily cost summary"
	@echo "  - Alert if daily spend exceeds budget"

# ─────────────────────────────────────────────────────────────────
# Cleanup
# ─────────────────────────────────────────────────────────────────

clean:
	@echo "Cleaning build artifacts and caches..."
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	@echo "Clean complete."
