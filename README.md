# datawrapper-mcp-server

A model context protocol server for interacting with the Datawrapper API

**Warning: Alpha software -- use at your own risk!**

I've only tested with Claude Desktop on OS X.

## Installation

1. Create [a Datawrapper API key](https://app.datawrapper.de/account/api-tokens) -- probably make it read-only since this is alpha software!

Clone this repo, and then run this, replacing your actual API key:

```bash
uv run mcp install src/datawrapper/server.py --env-var DATAWRAPPER_API_KEY=YOUR_KEY_HERE
```

Alternatively you can edit your Claude configuration manually. It's at: `~/Library/Application\ Support/Claude/claude_desktop_config.json`.

## Testing

To view logs (when connected to Claude Desktop):

```bash
tail -n 20 -F ~/Library/Logs/Claude/mcp*.log
```

Test this MCP server interactively with [inspector](https://github.com/modelcontextprotocol/inspector):

```bash
uv run mcp dev src/datawraper/server.py
```
