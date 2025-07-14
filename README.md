# datawrapper-mcp-server

A model context protocol server for interacting with the Datawrapper API

**Warning: Alpha software -- use at your own risk!**

I've only tested with Claude Desktop on OS X.

## Installation

1. Create [a Datawrapper API key](https://app.datawrapper.de/account/api-tokens) -- probably make it read-only since this is alpha software!

2. Clone this repo somewhere

3. Copy `.env.template` to `.env` and fill out the variables:

- `DATAWRAPPER_MCP_API_KEY` Your API key
- `DATAWRAPPER_MCP_DIRECTORY` Absolute path to a directory for this server to save files in

4. Install it in Claude Code by running:

```bash
just install
```

Alternatively you can edit your Claude configuration manually. It's at: `~/Library/Application\ Support/Claude/claude_desktop_config.json`. It should look like this:

```json
{
  "mcpServers": {
    "datawrapper": {
      "command": "/opt/homebrew/bin/uv",
      "args": [
        "run",
        "--with",
        "mcp[cli]",
        "mcp",
        "run",
        "/Users/kevin/dev/datawrapper-mcp-server/src/datawrapper_mcp_server/server.py"
      ],
      "env": {
        "DATAWRAPPER_MCP_API_KEY": "YOUR_KEY_HERE",
        "DATAWRAPPER_MCP_DIRECTORY": "/Users/kevin/datawrapper-mpc-server-files"
      }
    }
  }
}
```

## Testing

To view logs (when connected to Claude Desktop):

```bash
tail -n 20 -F ~/Library/Logs/Claude/mcp*.log
```

Test this MCP server interactively with [inspector](https://github.com/modelcontextprotocol/inspector):

```bash
just dev
```
