.PHONY: setup infra-up infra-down app-up app-down dev-backend migrate migrate-local test

# 초기 설정
setup: ## First-time project setup (infra + backend + frontend)
	@echo "=== Step 1: Starting infrastructure ==="
	cd infra && docker compose up -d
	@echo "=== Step 2: Setting up backend ==="
	cd backend && python -m venv .venv && .venv/bin/pip install -e ".[dev]"
	@echo "=== Step 3: Database migration ==="
	cd backend && .venv/bin/alembic upgrade head
	@echo "=== Step 4: Setting up frontend ==="
	cd frontend && npm install
	@echo ""
	@echo "=== Setup complete! ==="
	@echo "Start backend:  cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000"
	@echo "Start frontend: cd frontend && npm run dev"

# 인프라
infra-up:
	cd infra && docker compose up -d

infra-down:
	cd infra && docker compose down

# 앱
app-up:
	docker compose up -d

app-down:
	docker compose down

# 개발
dev-backend:
	cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 마이그레이션
migrate:
	docker compose run --rm rag-api alembic upgrade head

migrate-local:
	cd backend && source .venv/bin/activate && alembic upgrade head

# 테스트
test:
	cd backend && source .venv/bin/activate && pytest --tb=short -q
