.PHONY: run test check docker-up docker-down

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

test:
	python -m unittest discover -s tests -v

check:
	python -m compileall -q app tests
	node --check app/static/app.js
	docker compose config

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down
