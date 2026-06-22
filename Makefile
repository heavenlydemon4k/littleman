.PHONY: install migrate run scheduler session test lint format clean

install:
	uv sync --all-extras

migrate:
	uv run alembic upgrade head

run:
	uv run python -m littleman

scheduler:
	uv run python -m littleman.heartbeat.scheduler

session:
	uv run python -m littleman.agent.session $(ARGS)

test:
	uv run pytest tests/ -v

lint:
	uv run ruff check littleman/

format:
	uv run ruff format littleman/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; \
	find . -name "*.pyc" -delete 2>/dev/null; \
	rm -f littleman.db; \
	echo "cleaned"
