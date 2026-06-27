.PHONY: help setup verify-env build-probe smoke pilot run-condition run-all aggregate stats plots lint test typecheck cost-report clean

# Interpreter — defaults to the project venv so `make pilot` works after
# `make setup`. Override with `make PYTHON=python3 ...` to use another interp.
PYTHON ?= .venv/bin/python
CURRICULUM ?= data/SWE-Bench-CL-Curriculum.json

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
	@echo "Setting up environment (idempotent)..."
	@bash scripts/setup_env.sh

verify-env:
	@$(PYTHON) scripts/verify_env.py

build-probe:
	@echo "Probing arm64 buildability + SWE-bench_Verified coverage over all 273 tasks..."
	@$(PYTHON) -m src.benchmark.build_probe --curriculum $(CURRICULUM)

# ─────────────────────────────────────────────────────────────────
# Spike Week (Calibration)
# ─────────────────────────────────────────────────────────────────

smoke:
	@echo "Running smoke test (real curriculum easy tasks, NoMemory)..."
	@$(PYTHON) -m src.benchmark.smoke_test

pilot:
	@echo "Running pilot experiment: django + pytest x 6 policies x 1 seed = 12 runs (decision I)..."
	@$(PYTHON) -m src.benchmark.experiment_runner --mode pilot \
		--sequences django_django_sequence,pytest-dev_pytest_sequence \
		--curriculum $(CURRICULUM)

# ─────────────────────────────────────────────────────────────────
# Full Experiment
# ─────────────────────────────────────────────────────────────────

run-condition:
ifndef POLICY
	$(error POLICY is required, e.g. make run-condition POLICY=type_aware_decay SEED=1)
endif
ifndef SEED
	$(error SEED is required, e.g. make run-condition POLICY=type_aware_decay SEED=1)
endif
	@echo "Running condition: POLICY=$(POLICY) SEED=$(SEED) (all 8 sequences)..."
	@$(PYTHON) -m src.benchmark.experiment_runner --mode condition --policy $(POLICY) --seed $(SEED) --curriculum $(CURRICULUM)

run-all:
	@echo "Running full experiment: 8 sequences x 6 policies x 3 seeds = 144 runs (sequential)..."
	@$(PYTHON) -m src.benchmark.experiment_runner --mode full --curriculum $(CURRICULUM)

# ─────────────────────────────────────────────────────────────────
# Analysis
# ─────────────────────────────────────────────────────────────────

RUNS ?= runs
RESULTS ?= results

aggregate:
	.venv/bin/python -m scripts.run_analysis --stage aggregate --runs-dir $(RUNS) --out $(RESULTS)

stats:
	.venv/bin/python -m scripts.run_analysis --stage stats --runs-dir $(RUNS) --out $(RESULTS)

plots:
	.venv/bin/python -m scripts.run_analysis --stage plots --runs-dir $(RUNS) --out $(RESULTS)

# Full pipeline: aggregate -> stats (+TOST) -> plots -> E7 interdependence.
results:
	.venv/bin/python -m scripts.run_analysis --stage all --runs-dir $(RUNS) --out $(RESULTS)

# ─────────────────────────────────────────────────────────────────
# Development
# ─────────────────────────────────────────────────────────────────

lint:
	@echo "Running ruff linter..."
	$(PYTHON) -m ruff check src/ tests/

test:
	@echo "Running pytest..."
	$(PYTHON) -m pytest tests/ -v --cov=src --cov-report=term-missing

typecheck:
	@echo "Running mypy type checker..."
	$(PYTHON) -m mypy src/ --strict

# ─────────────────────────────────────────────────────────────────
# Monitoring
# ─────────────────────────────────────────────────────────────────

cost-report:
	@echo "Generating cost report..."
	@python -c "from src.metrics.cost_tracker import generate_daily_cost_report, check_budget_alert; \
		report = generate_daily_cost_report('runs'); \
		print(f'\nDaily Cost Report:'); \
		print(f'  Total runs: {report[\"total_runs\"]}'); \
		print(f'  Total cost: \$${report[\"total_cost\"]:.2f}'); \
		print(f'\n  Cost by policy:'); \
		[print(f'    {policy}: \$${cost:.2f}') for policy, cost in sorted(report['cost_by_policy'].items())]; \
		print(f'\n  Cost by date:'); \
		[print(f'    {date}: \$${cost:.2f}') for date, cost in sorted(report['cost_by_date'].items())]; \
		print(f'\n  Report written to: runs/daily_cost_report.json'); \
		alert = check_budget_alert('runs', daily_budget=100.0, total_budget=1000.0); \
		print(f'\nBudget Status:'); \
		print(f'  Daily: \$${alert[\"daily_cost\"]:.2f} / \$${alert[\"daily_budget\"]:.2f} ({\"ALERT\" if alert[\"daily_alert\"] else \"OK\"})'); \
		print(f'  Total: \$${alert[\"total_cost\"]:.2f} / \$${alert[\"total_budget\"]:.2f} ({\"ALERT\" if alert[\"total_alert\"] else \"OK\"})')"

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
