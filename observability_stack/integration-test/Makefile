.PHONY: up down reset dashboard gen-csv gen-om logs help

DOCKER_COMPOSE = docker compose

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

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

dashboard: ## Regenerate Grafana dashboard JSON from YAML config
	@echo "Generating Grafana dashboard JSON..."
	cd grafana && pip install -q jinja2 pyyaml && python generate_dashboard.py
	@echo "Done: grafana/dashboards/slo_test.json"

## ── Data generation (local, no Docker) ───────────────────────────────────

gen-csv: ## Generate all scenarios as CSV files (no Docker, no remote backends)
	cd generator && pip install -q -r requirements.txt && \
	python main.py --scenario all --days 7 --resolution 30 \
		--output-dir ./output --skip-influxdb --skip-prometheus

gen-om: ## Generate OpenMetrics files for promtool backfill (no Docker)
	cd generator && pip install -q -r requirements.txt && \
	python main.py --scenario all --days 7 --resolution 30 \
		--output-dir ./output --skip-influxdb

gen-healthy: ## Generate healthy scenario only (CSV)
	cd generator && python main.py --scenario healthy --days 7 --resolution 30 \
		--output-dir ./output --skip-influxdb --skip-prometheus

gen-outage: ## Generate outage scenario only (CSV)
	cd generator && python main.py --scenario outage --outage-duration 30 \
		--days 7 --resolution 30 --output-dir ./output --skip-influxdb --skip-prometheus

gen-degradation: ## Generate degradation scenario only (CSV)
	cd generator && python main.py --scenario degradation \
		--days 7 --resolution 30 --output-dir ./output --skip-influxdb --skip-prometheus

## ── Service URLs (after `make up`) ───────────────────────────────────────

urls: ## Print service URLs
	@echo ""
	@echo "  Grafana:    http://localhost:3000  (admin / admin)"
	@echo "  Prometheus: http://localhost:9090"
	@echo "  InfluxDB:   http://localhost:8086  (admin / adminpassword)"
	@echo ""
