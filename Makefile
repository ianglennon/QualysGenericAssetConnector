.PHONY: dev test migrate shell down clean

dev:
	docker compose up --build

test:
	docker compose run --rm backend pytest tests/ -v

migrate:
	docker compose run --rm backend alembic upgrade head

shell:
	docker compose run --rm backend /bin/bash

down:
	docker compose down

# WARNING: destroys the qualys-data volume — all database data will be lost
clean:
	docker compose down -v
