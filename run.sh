#!/usr/bin/env bash
# Ein-Befehl-Start/Neustart des StarCraft-Kampagnen-MCP-Servers.
#
#   ./run.sh           -> baut (falls noetig) und startet/neustartet den Container
#   ./run.sh logs      -> zeigt die Live-Logs
#   ./run.sh selftest  -> fuehrt den Selbsttest im Container aus
#   ./run.sh stop      -> stoppt den Container
set -euo pipefail
cd "$(dirname "$0")"

# docker compose (v2) bevorzugen, sonst docker-compose (v1).
if docker compose version >/dev/null 2>&1; then
	DC="docker compose"
else
	DC="docker-compose"
fi

cmd="${1:-up}"
case "$cmd" in
	up|"")
		$DC up -d --build
		echo
		echo "Server laeuft. Streamable-HTTP-Endpunkt intern: http://sc-mcp:8000/mcp"
		echo "Oeffentlich (via Caddy): https://sc-mcp.pixel-by-design.de/mcp"
		;;
	logs)
		$DC logs -f sc-mcp
		;;
	selftest)
		$DC run --rm sc-mcp python selftest.py
		;;
	stop|down)
		$DC down
		;;
	*)
		echo "Unbekannter Befehl: $cmd"
		echo "Nutze: ./run.sh [up|logs|selftest|stop]"
		exit 1
		;;
esac
