import os
import httpx
from typing import Optional, Dict, Any, Union
from mcp.server.fastmcp import Context, FastMCP, Image

API_KEY = os.environ.get("DATAWRAPPER_API_KEY", "")
API_BASE_URL = "https://api.datawrapper.de/v3"

mcp = FastMCP(
    name="datawrapper",
    instructions="MCP server for interacting with Datawrapper API to create and manage data visualizations",
)


async def _make_request(
    ctx: Context,
    method: str,
    endpoint: str,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    data: Optional[Any] = None,
    json_data: Optional[Dict[str, Any]] = None,
    files: Optional[Dict[str, Any]] = None,
) -> Any:
    """
    Helper function to make API requests to Datawrapper
    """
    if headers is None:
        headers = {}

    headers["Authorization"] = f"Bearer {API_KEY}"
    url = f"{API_BASE_URL}/{endpoint}"

    async with httpx.AsyncClient() as client:
        response = await client.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            data=data,
            json=json_data,
            files=files,
        )

        await ctx.log(
            level="info",
            message=f"response: {response}",
        )
        await ctx.log(
            level="info",
            message=f"{response.content}",
        )

        response.raise_for_status()

        return response.content

        # if "json" in response.headers["content-type"]:
        #     return response.json()
        # else:
        #     return response.content


@mcp.tool()
async def get_chart_image(chart_id: str, ctx: Context) -> Union[str, Image]:
    """
    Get image for a specific chart

    Args:
        chart_id: ID of the chart to get image for

    Returns:
        The chart as an image
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{API_BASE_URL}/charts/{chart_id}/export/png",
                headers={"Authorization": f"Bearer {API_KEY}"},
            )

            if response.status_code >= 400:
                return f"Error getting chart image: HTTP {response.status_code} - {response.text}"

            return Image(data=response.content, format="png")

    except Exception as e:
        return f"Error getting chart image: {str(e)}"


@mcp.tool()
async def export_chart(
    ctx: Context,
    chart_id: str,
    format: str = "png",
    width: Optional[int] = None,
    height: Optional[int] = None,
    plain: bool = False,
    transparent: bool = False,
) -> Image:
    """
    Export a chart to different formats

    Args:
        chart_id: ID of the chart to export
        format: Export format (png, pdf, svg, or html)
        width: Image width in pixels (optional)
        height: Image height in pixels (optional)
        plain: Whether to export without Datawrapper branding (optional)
        transparent: Whether to use transparent background (PNG only, optional)

    Returns:
        JSON response with export details
    """
    endpoint = f"charts/{chart_id}/export/{format}"
    params = {}

    if width:
        params["width"] = width

    if height:
        params["height"] = height

    if plain:
        params["plain"] = "true"

    if transparent and format.lower() == "png":
        params["transparent"] = "true"

    content = await _make_request(ctx, method="GET", endpoint=endpoint, params=params)
    return Image(data=content, format="png")


if __name__ == "__main__":
    mcp.run()
