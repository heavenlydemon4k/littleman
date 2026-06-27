.PHONY: install migrate run start setup api ui build-ui scheduler session boot once test lint format clean

install:
	uv sync --all-extras
	cd frontend && npm install

migrate:
	uv run alembic upgrade head

# First-time setup: install deps, run DB migrations, build frontend
setup: install migrate build-ui

# Start the production-like runtime: API + scheduler in parallel
start: build-ui
	make -j2 api scheduler

# Start development: API (reload) + Vite dev server in parallel
run:
	make -j2 api ui

api:
	uv run uvicorn littleman.api.app:app --host 0.0.0.0 --port 8000 --reload

ui:
	cd frontend && npm run dev

# Build frontend for production (served by the FastAPI static mount)
build-ui:
	cd frontend && npm run build

scheduler:
	uv run python -m littleman.heartbeat.scheduler

session:
	uv run python -m littleman.agent.session $(ARGS)

boot:
	uv run python -m littleman boot

once:
	uv run python -m littleman once

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
