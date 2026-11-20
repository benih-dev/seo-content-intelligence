.PHONY: dev seed check
dev:
	./scripts/dev.sh
seed:
	cd backend && uv run python seed.py
check:
	cd backend && uv run ruff check . && uv run pytest -q
	cd frontend && npm run lint && npm run typecheck && npm run build
