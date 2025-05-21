from pathlib import Path
from mcp.types import TextContent
import pytest
from unittest.mock import patch, Mock
from mcp.shared.memory import (
    create_connected_server_and_client_session as client_session,
)
from pytest_httpx import HTTPXMock
from datawrapper_mcp_server.server import mcp


@pytest.mark.asyncio
async def test_tool_functionality(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://api.datawrapper.de/v3/charts/ZZZZZZ/export/png",
        content=b"some fake image bytes",
    )

    with patch(
        "datawrapper_mcp_server.server.write_file", new=Mock()
    ) as mock_write_file:
        mock_write_file.return_value = Path("/tmp/ZZZZZZ.png")

        async with client_session(mcp._mcp_server) as client:
            result = await client.call_tool(
                "export_chart", {"chart_id": "ZZZZZZ", "filepath": "ZZZZZZ.png"}
            )
            assert not result.isError
            assert len(result.content) == 1
            assert isinstance(result.content[0], TextContent)
            assert result.content[0].text == "Chart exported to /tmp/ZZZZZZ.png"
            mock_write_file.assert_called_once()
