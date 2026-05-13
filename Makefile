# french-rain-radar — top-level developer Makefile

.PHONY: help setup backend-sync backend-test backend-lint backend-cli \
        fake-data dev-caddy dev-caddy-stop dev-stack dev-stack-stop \
        client-android client-wasm client-test schema-validate clean

help:
	@echo "Common targets:"
	@echo "  setup           — bootstrap toolchains (uv + Gradle wrapper)"
	@echo "  backend-sync    — uv sync (install Python deps)"
	@echo "  backend-test    — run backend pytest suite"
	@echo "  backend-lint    — run ruff over backend"
	@echo "  fake-data       — generate fake PNGs + manifest into dev/data/tiles"
	@echo "  dev-caddy       — start local Caddy (HTTP, basic auth dev/dev) via docker compose"
	@echo "  dev-caddy-stop  — stop local Caddy"
	@echo "  client-android  — build Android debug APK"
	@echo "  client-wasm     — run the Wasm app in dev mode"
	@echo "  client-test     — run KMP shared tests"
	@echo "  schema-validate — validate the example manifest against the JSON schema"
	@echo "  clean           — remove build artifacts"

setup:
	./setup.sh

backend-sync:
	cd backend && uv sync

backend-test:
	cd backend && uv run pytest

backend-lint:
	cd backend && uv run ruff check .

backend-cli:
	cd backend && uv run radar --help

fake-data:
	cd backend && uv run python ../dev/fake-data.py

dev-caddy:
	cd dev && docker compose up -d caddy

dev-caddy-stop:
	cd dev && docker compose down

dev-stack: fake-data dev-caddy
	@echo "Local stack up at http://localhost:8080  (basic auth: dev / dev)"

dev-stack-stop: dev-caddy-stop

client-android:
	cd client && ./gradlew :androidApp:assembleDebug

client-wasm:
	cd client && ./gradlew :wasmJsApp:wasmJsBrowserDevelopmentRun

client-test:
	cd client && ./gradlew :shared:allTests

schema-validate:
	cd backend && uv run check-jsonschema --schemafile ../schema/manifest.schema.json ../schema/examples/manifest.example.json

clean:
	rm -rf dev/data
	cd client && ./gradlew clean || true
	find backend -type d \( -name __pycache__ -o -name .pytest_cache -o -name .ruff_cache \) -prune -exec rm -rf {} +
