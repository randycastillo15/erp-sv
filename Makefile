up:
	docker compose -f infra/compose/docker-compose.yml up -d --build

down:
	docker compose -f infra/compose/docker-compose.yml down

logs:
	docker compose -f infra/compose/docker-compose.yml logs -f

ps:
	docker compose -f infra/compose/docker-compose.yml ps

test:
	docker compose -f infra/compose/docker-compose.yml exec dte-gateway pytest

shell:
	docker compose -f infra/compose/docker-compose.yml exec dte-gateway bash
