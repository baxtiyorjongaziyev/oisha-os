.PHONY: up down dev build test migrate seed lint format install

# Start all infrastructure (postgres, redis, minio)
up:
	docker compose up -d
	@echo "✓ Infrastructure started. Postgres: 5432, Redis: 6379, MinIO: 9000 (console: 9001)"

# Stop infrastructure
down:
	docker compose down

# Install all dependencies
install:
	pnpm install

# Run all apps in dev mode
dev:
	pnpm dev

# Build all apps
build:
	pnpm build

# Run all tests
test:
	pnpm test

# Run DB migrations
migrate:
	pnpm --filter api exec prisma migrate dev

# Seed DB with default data
seed:
	pnpm --filter api exec prisma db seed

# Lint all packages
lint:
	pnpm lint

# Format all files
format:
	pnpm format

# Full setup from scratch
setup: install up
	@echo "Waiting for postgres..."
	@sleep 3
	$(MAKE) migrate
	$(MAKE) seed
	@echo "✓ SalesCoach AI is ready. Run 'make dev' to start."
