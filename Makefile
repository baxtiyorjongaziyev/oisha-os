SHELL := /bin/sh

.PHONY: up migrate dev test build lint typecheck python-test

up:
	docker compose up -d postgres redis minio

migrate:
	pnpm --filter @salescoach/api prisma:migrate

dev:
	pnpm dev

test:
	pnpm test

build:
	pnpm build

lint:
	pnpm lint

typecheck:
	pnpm typecheck

python-test:
	python -m pytest -q
