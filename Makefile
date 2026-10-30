SHELL := /bin/sh

.PHONY: up migrate dev test build lint typecheck python-test hooks uzbek-text

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

# O'zbekcha matn guard (ASCII apostrof) — pre-commit hook va qo'lda tekshiruv.
hooks:
	git config core.hooksPath .githooks
	@echo "Git hooks o'rnatildi: core.hooksPath=.githooks"

uzbek-text:
	python scripts/check_uzbek_text.py --staged
