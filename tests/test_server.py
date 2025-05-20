import pytest
from mcp.shared.memory import (
    create_connected_server_and_client_session as client_session,
)
from pytest_httpx import HTTPXMock
from .server import mcp


@pytest.mark.asyncio
async def test_tool_functionality(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://api.datawrapper.de/v3/charts/ZZZZZZ/export/png",
        content=b'some bytes'
    )

    async with client_session(mcp._mcp_server) as client:
        result = await client.call_tool("export_chart", {"chart_id": "ZZZZZZ"})
        print(result)
        assert result.content == True
