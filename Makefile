.PHONY: setup infra-up infra-down app-up app-down dev-backend dev-backend-bg dev-backend-stop dev-frontend dev-frontend-bg dev-frontend-stop migrate migrate-local test help

BACKEND_PID_FILE := .backend.pid
FRONTEND_PID_FILE := .frontend.pid

# 도움말 (기본 타겟)
help: ## 사용 가능한 명령어 목록 출력
	@echo ""
	@echo "UrstoryRAG - 사용 가능한 명령어"
	@echo "================================"
	@echo ""
	@echo "  초기 설정:"
	@echo "    make setup              전체 초기 설정 (인프라 + 백엔드 + 프론트엔드)"
	@echo ""
	@echo "  인프라 (PostgreSQL, Elasticsearch, Redis):"
	@echo "    make infra-up           인프라 시작"
	@echo "    make infra-down         인프라 중지"
	@echo ""
	@echo "  앱 (Docker Compose):"
	@echo "    make app-up             전체 앱 시작 (Docker)"
	@echo "    make app-down           전체 앱 중지"
	@echo ""
	@echo "  백엔드 개발 서버:"
	@echo "    make dev-backend        포그라운드 실행 (Ctrl+C로 종료)"
	@echo "    make dev-backend-bg     백그라운드 실행"
	@echo "    make dev-backend-stop   백그라운드 서버 종료"
	@echo ""
	@echo "  프론트엔드 개발 서버:"
	@echo "    make dev-frontend       포그라운드 실행 (Ctrl+C로 종료)"
	@echo "    make dev-frontend-bg    백그라운드 실행"
	@echo "    make dev-frontend-stop  백그라운드 서버 종료"
	@echo ""
	@echo "  DB 마이그레이션:"
	@echo "    make migrate            Docker 환경 마이그레이션"
	@echo "    make migrate-local      로컬 환경 마이그레이션"
	@echo ""
	@echo "  테스트:"
	@echo "    make test               백엔드 테스트 실행"
	@echo ""
	@echo "  포트 정보:"
	@echo "    백엔드 API     http://localhost:8000"
	@echo "    Swagger UI     http://localhost:8000/docs"
	@echo "    프론트엔드     http://localhost:3500"
	@echo "    Langfuse       http://localhost:3100"
	@echo ""

# 초기 설정
setup: ## 전체 초기 설정 (인프라 + 백엔드 + 프론트엔드)
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
	@echo "Run 'make help' for available commands."

# 인프라
infra-up: ## 인프라 시작 (PostgreSQL, Elasticsearch, Redis)
	cd infra && docker compose up -d

infra-down: ## 인프라 중지
	cd infra && docker compose down

# 앱
app-up: ## 전체 앱 시작 (Docker Compose)
	docker compose up -d

app-down: ## 전체 앱 중지
	docker compose down

# 백엔드 개발 서버
dev-backend: ## 백엔드 포그라운드 실행 (Ctrl+C로 종료)
	cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-backend-bg: ## 백엔드 백그라운드 실행
	@if [ -f $(BACKEND_PID_FILE) ] && kill -0 $$(cat $(BACKEND_PID_FILE)) 2>/dev/null; then \
		echo "백엔드가 이미 실행 중입니다 (PID: $$(cat $(BACKEND_PID_FILE)))"; \
	else \
		cd backend && source .venv/bin/activate && \
		nohup uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 > ../logs/backend.log 2>&1 & \
		echo $$! > ../$(BACKEND_PID_FILE); \
		echo "백엔드 시작됨 (PID: $$(cat ../$(BACKEND_PID_FILE)))"; \
		echo "로그: tail -f logs/backend.log"; \
	fi

dev-backend-stop: ## 백그라운드 백엔드 종료
	@FOUND=0; \
	if [ -f $(BACKEND_PID_FILE) ]; then \
		PID=$$(cat $(BACKEND_PID_FILE)); \
		if kill -0 $$PID 2>/dev/null; then \
			kill $$PID; \
			echo "백엔드 종료됨 (PID: $$PID)"; \
			FOUND=1; \
		fi; \
		rm -f $(BACKEND_PID_FILE); \
	fi; \
	if [ $$FOUND -eq 0 ]; then \
		PIDS=$$(lsof -ti :8000 2>/dev/null || true); \
		if [ -n "$$PIDS" ]; then \
			echo "$$PIDS" | xargs kill; \
			echo "포트 8000 점유 프로세스 종료됨 (PID: $$PIDS)"; \
		else \
			echo "실행 중인 백엔드가 없습니다"; \
		fi; \
	fi

# 프론트엔드 개발 서버
dev-frontend: ## 프론트엔드 포그라운드 실행 (Ctrl+C로 종료)
	@PIDS=$$(lsof -ti :3500 2>/dev/null || true); \
	if [ -n "$$PIDS" ]; then \
		echo "포트 3500 점유 프로세스 종료 (PID: $$PIDS)"; \
		echo "$$PIDS" | xargs kill -9; \
		sleep 1; \
	fi
	cd frontend && pnpm dev --port 3500

dev-frontend-bg: ## 프론트엔드 백그라운드 실행
	@if [ -f $(FRONTEND_PID_FILE) ] && kill -0 $$(cat $(FRONTEND_PID_FILE)) 2>/dev/null; then \
		echo "프론트엔드가 이미 실행 중입니다 (PID: $$(cat $(FRONTEND_PID_FILE)))"; \
	else \
		cd frontend && \
		nohup pnpm dev --port 3500 > ../logs/frontend.log 2>&1 & \
		echo $$! > ../$(FRONTEND_PID_FILE); \
		echo "프론트엔드 시작됨 (PID: $$(cat ../$(FRONTEND_PID_FILE)))"; \
		echo "로그: tail -f logs/frontend.log"; \
	fi

dev-frontend-stop: ## 백그라운드 프론트엔드 종료
	@FOUND=0; \
	if [ -f $(FRONTEND_PID_FILE) ]; then \
		PID=$$(cat $(FRONTEND_PID_FILE)); \
		if kill -0 $$PID 2>/dev/null; then \
			kill $$PID; \
			echo "프론트엔드 종료됨 (PID: $$PID)"; \
			FOUND=1; \
		fi; \
		rm -f $(FRONTEND_PID_FILE); \
	fi; \
	if [ $$FOUND -eq 0 ]; then \
		PIDS=$$(lsof -ti :3500 2>/dev/null || true); \
		if [ -n "$$PIDS" ]; then \
			echo "$$PIDS" | xargs kill; \
			echo "포트 3500 점유 프로세스 종료됨 (PID: $$PIDS)"; \
		else \
			echo "실행 중인 프론트엔드가 없습니다"; \
		fi; \
	fi

# 마이그레이션
migrate: ## Docker 환경 DB 마이그레이션
	docker compose run --rm rag-api alembic upgrade head

migrate-local: ## 로컬 환경 DB 마이그레이션
	cd backend && source .venv/bin/activate && alembic upgrade head

# 테스트
test: ## 백엔드 테스트 실행
	cd backend && source .venv/bin/activate && pytest --tb=short -q
