.PHONY: infra-up infra-down app-up app-down dev-backend migrate migrate-local test

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
