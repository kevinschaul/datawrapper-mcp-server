import os
import sys
from pathlib import Path
import re
import httpx
from typing import Optional, Dict, Any, Union
from mcp.server.fastmcp import Context, FastMCP, Image
import logging

API_KEY = os.environ.get("DATAWRAPPER_MCP_API_KEY", "")
API_BASE_URL = "https://api.datawrapper.de/v3"
DIRECTORY = os.environ.get("DATAWRAPPER_MCP_DIRECTORY", "")

# TODO bail if API_KEY or DIRECTORY are missing

logger = logging.getLogger("datawrapper_mcp")

current_dir = os.path.dirname(os.path.abspath(__file__))
logging.basicConfig(
    filename=os.path.join(current_dir, "..", "..", "datawrapper_mcp_server.log"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.DEBUG,
)


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
) -> httpx.Response:
    """
    Helper function to make API requests to Datawrapper
    """
    if headers is None:
        headers = {}

    headers["Authorization"] = f"Bearer {API_KEY}"
    url = f"{API_BASE_URL}/{endpoint}"

    async with httpx.AsyncClient(timeout=10) as client:
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
        logger.info(f"eprint response: {response}")

        response.raise_for_status()
        return response


def find_writable_directory():
    possible_paths = ["/tmp", "/var/tmp", "/dev/shm", os.getcwd()]
    for path in possible_paths:
        test_file = os.path.join(path, "write_test.txt")
        try:
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            logger.info("Writable path found: %s", path)
            return path
        except Exception as e:
            logger.info("Path not writable: %s (%s)", path, e)
    raise RuntimeError("No writable path found.")


def write_file(directory: str, filename: str, content: bytes) -> Path:
    """
    Writes content to a file with proper filename sanitization.

    Args:
        directory: The allowed directory to write inside of
        filename: The name of the file to write to
        content: The binary content to write to the file

    Raises:
        ValueError: If the filename is invalid or attempts to access parent directories

    Returns: The sanitized filepath that was written to
    """
    logger.info(f"write_file: {filename}")
    logger.info(f"os.getcwd(): {os.getcwd()}")

    if (
        not filename
        or ".." in filename
        or filename.startswith("/")
        or filename.startswith("\\")
    ):
        raise ValueError("Invalid filename: potential directory traversal attempt")

    Path(directory).mkdir(parents=True, exist_ok=True)
    safe_path = Path(directory) / Path(filename).name

    if not safe_path.resolve().is_relative_to(Path(directory).resolve()):
        raise ValueError(f"Invalid path: {filename} attempts to escape directory")

    try:
        with open(safe_path, "wb") as f:
            f.write(content)
        return safe_path
    except Exception as e:
        logger.error(e)
        raise IOError(f"Failed to write to file: {str(e)}")


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
    filepath: str,
    format: str = "png",
    width: Optional[int] = None,
    height: Optional[int] = None,
    plain: bool = False,
    transparent: bool = False,
) -> str:
    """
    Export a chart to different formats

    Args:
        chart_id: ID of the chart to export
        format: Export format (png, pdf, svg, or html)
        filepath: File name to save chart to
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

    response = await _make_request(ctx, method="GET", endpoint=endpoint, params=params)
    final_path = write_file(DIRECTORY, filepath, response.content)
    return f"Chart exported to {final_path}"


if __name__ == "__main__":
    logger.info("Starting Datawrapper MCP server")
    mcp.run()
