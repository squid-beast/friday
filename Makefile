# friday · Makefile
# setup:     uv sync + pre-fetch Silero VAD weights (no surprise download mid-demo)
# voice:     voice loop on local mic/speakers — the Phase 1 demo path (no docker needed)
# run:       docker livekit + voice worker in dev mode (chroma is embedded, no docker)
# test:      L1 unit tests (mocked, no network, <5s)
# lint:      ruff check .
# eval:      router/persona evals (armed in Phase 2+)
# doctor:    scripts/healthcheck.py full mode (real API pings)
# snapshot:  scripts/snapshot.sh -> ~/friday-snapshots/ (the no-git safety net)
.PHONY: setup run voice gesture test test-unit test-integration test-scenario lint eval doctor snapshot install-launchd collect dashboard ui

setup:
	uv sync
	uv run python -m voice.agent download-files

voice:
	uv run python -m voice.agent console

gesture:  # G0: build the native Apple Vision hand-pose spike (needs macOS + swiftc)
	swiftc -O gesture/handpose.swift -o gesture/handpose

run:
	docker compose up -d
	uv run python -m voice.agent dev

test: test-unit

test-unit:
	uv run pytest tests/unit -q

test-integration:
	uv run pytest tests/integration -q

test-scenario:
	uv run pytest tests/scenario -q

install-launchd:
	@bash scripts/install_launchd.sh

collect:
	uv run python -m integrations.collect

dashboard:
	uv run python -m integrations.server

lint:
	uv run ruff check .

eval:
	uv run pytest tests/evals -q

doctor:
	uv run python -m scripts.healthcheck

snapshot:
	@bash scripts/snapshot.sh

ui:
	cd ui && npm install --no-fund --no-audit && npm run build
