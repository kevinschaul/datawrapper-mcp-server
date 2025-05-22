set dotenv-load

# Run tests and linters
@default: test lint

# Run pytest with supplied options
@test *options:
  uv run pytest {{options}}

# Run linters
@lint:
  uvx black . --check
  uvx ruff check

# Apply Black
@black:
  uvx black .

# Apply ruff
@ruff:
  uvx ruff check --fix

# Auto-format and fix things
@fix: black ruff

# Run server in MCP Inspector
@dev:
  npx @modelcontextprotocol/inspector -e DATAWRAPPER_MCP_API_KEY=${DATAWRAPPER_MCP_API_KEY} -- uv run src/datawrapper_mcp_server/server.py

@logs-claude:
  tail -f ~/Library/Logs/Claude/mcp-server-datawrapper.log

# @run-export-chart:
#   npx @modelcontextprotocol/inspector -e DATAWRAPPER_MCP_API_KEY=${DATAWRAPPER_MCP_API_KEY} --cli uv run src/datawrapper_mcp_server/server.py --method tools/call --tool-name export_chart --tool-arg chart_id=Yzbqd --tool-arg filepath=Yzbqd.png

# Install this server in Claude Code
@install:
  uv run mcp install src/datawrapper_mcp_server/server.py --env-var DATAWRAPPER_MCP_API_KEY=${DATAWRAPPER_MCP_API_KEY} --env-var DATAWRAPPER_MCP_DIRECTORY=${DATAWRAPPER_MCP_DIRECTORY}

