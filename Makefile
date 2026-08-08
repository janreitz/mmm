# Dev-machine quality gate. Override the tool paths if your venv lives elsewhere:
#   make check RUFF=ruff MYPY=mypy PYTEST=pytest
RUFF ?= env/bin/ruff
MYPY ?= env/bin/mypy
PYTEST ?= env/bin/pytest

.PHONY: check lint format typecheck test

check: lint typecheck test

# Format is deliberately not part of `check` yet: ruff's formatter wants to
# rewrite every legacy module's style in one pass, which would bury stage-2's
# real diffs under whitespace churn. Legacy files get formatted as stage 2
# rewrites them; new code should already be ruff-format-clean (`make format`
# before committing new files).
lint:
	$(RUFF) check .

format:
	$(RUFF) format .
	$(RUFF) check --fix .

typecheck:
	$(MYPY) marta scripts/power_button_daemon.py

test:
	$(PYTEST) -q
