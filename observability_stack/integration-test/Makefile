.PHONY: up down reset dashboard gen-csv gen-om gen-healthy gen-outage gen-degradation test logs logs-generator urls help

DOCKER_COMPOSE = docker compose

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

## ── Stack management ──────────────────────────────────────────────────────

up: dashboard ## Build images, generate data, start all services
	$(DOCKER_COMPOSE) up --build -d

down: ## Stop all services
	$(DOCKER_COMPOSE) down

reset: ## Wipe all data volumes and restart from scratch
	$(DOCKER_COMPOSE) down -v
	$(MAKE) up

logs: ## Tail logs for all services
	$(DOCKER_COMPOSE) logs -f

logs-generator: ## Tail generator logs only
	$(DOCKER_COMPOSE) logs -f generator

## ── Dashboard generation ──────────────────────────────────────────────────

dashboard: ## Regenerate all 3 Grafana dashboard JSONs from YAML config
	@echo "Generating Grafana dashboard JSONs..."
	uv run --directory grafana python generate_dashboard.py
	@echo "Done: grafana/dashboards/"

## ── Data generation (local, no Docker) ───────────────────────────────────

gen-csv: ## Generate all scenarios as CSV files (no Docker, no remote backends)
	uv run --directory generator slo-generate \
		--backends csv \
		--scenario all --days 7 --resolution 30 \
		--output-dir ./output

gen-om: ## Generate OpenMetrics files for promtool backfill (no Docker)
	uv run --directory generator slo-generate \
		--backends prometheus \
		--scenario all --days 7 --resolution 30 \
		--output-dir ./output

gen-healthy: ## Generate healthy scenario only (CSV)
	uv run --directory generator slo-generate \
		--backends csv \
		--scenario healthy --days 7 --resolution 30 \
		--output-dir ./output

gen-outage: ## Generate outage scenario only (CSV)
	uv run --directory generator slo-generate \
		--backends csv \
		--scenario outage --outage-duration 30 \
		--days 7 --resolution 30 \
		--output-dir ./output

gen-degradation: ## Generate degradation scenario only (CSV)
	uv run --directory generator slo-generate \
		--backends csv \
		--scenario degradation --days 7 --resolution 30 \
		--output-dir ./output

## ── Tests ─────────────────────────────────────────────────────────────────

test: ## Run generator unit tests
	uv run --directory generator pytest tests/ -v

## ── Service URLs (after `make up`) ───────────────────────────────────────

urls: ## Print service URLs
	@echo ""
	@echo "  Grafana:      http://localhost:3100  (admin / admin)"
	@echo "  Prometheus:   http://localhost:9090"
	@echo "  InfluxDB:     http://localhost:8086  (admin / adminpassword)"
	@echo "  TimescaleDB:  localhost:5432"
	@echo ""
