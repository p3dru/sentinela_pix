.PHONY: up down seed stream test lint logs

up:
	docker compose up -d --build

down:
	docker compose down

seed:
	docker compose exec api python -m sentinela.seed

stream:
	docker compose exec api python -m sentinela.produtor --tps 10 --minutos 10

test:
	cd backend && pytest -q

lint:
	cd backend && ruff check .

logs:
	docker compose logs -f --tail=100
