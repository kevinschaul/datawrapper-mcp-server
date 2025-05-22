import os
from pathlib import Path
import httpx
from typing import Annotated, Literal, Optional, Dict, Any
from mcp.server.fastmcp import Context, FastMCP, Image
import logging

from pydantic import Field


def get_required_env(key):
    value = os.environ.get(key)
    if not value:
        raise ValueError(f"{key} environment variable is not set")
    return value


API_BASE_URL = "https://api.datawrapper.de/v3"
API_KEY = get_required_env("DATAWRAPPER_MCP_API_KEY")
DIRECTORY = Path(get_required_env("DATAWRAPPER_MCP_DIRECTORY"))

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


def write_file(base_dir: Path, file_path: Path, content: bytes) -> Path:
    """
    Writes content to a file with proper filename sanitization.
    Args:
        base_dir: The allowed base directory to write inside of
        file_path: The relative path of the file within base_dir (can include subdirectories)
        content: The binary content to write to the file
    Raises:
        ValueError: If the file_path is invalid or attempts to access parent directories
    Returns: The sanitized filepath that was written to
    """
    logger.info(f"write_file: {file_path}")
    logger.info(f"os.getcwd(): {os.getcwd()}")

    if not file_path.name:
        raise ValueError("Invalid file path: empty filename")

    file_path_str = str(file_path)
    if file_path_str.startswith("/") or file_path_str.startswith("\\"):
        raise ValueError("Invalid file path: must be relative, not absolute")

    base_dir.mkdir(parents=True, exist_ok=True)

    target_path = base_dir / file_path
    target_path.parent.mkdir(parents=True, exist_ok=True)

    if not target_path.resolve().is_relative_to(base_dir.resolve()):
        raise ValueError(f"Invalid path: {file_path} attempts to escape base directory")

    try:
        with target_path.open("wb") as f:
            f.write(content)
        return target_path
    except Exception as e:
        logger.error(e)
        raise IOError(f"Failed to write to file: {str(e)}")


@mcp.tool()
async def preview_chart(
    ctx: Context,
    chart_id: Annotated[
        str, Field(pattern=r"^[a-zA-Z0-9]{5}$", description="Chart ID")
    ],
) -> Image:
    """View a chart image"""
    endpoint = f"charts/{chart_id}/export/png"
    response = await _make_request(ctx, method="GET", endpoint=endpoint, params={})
    return Image(data=response.content, format="png")


@mcp.tool()
async def export_chart(
    ctx: Context,
    chart_id: Annotated[
        str, Field(pattern=r"^[a-zA-Z0-9]{5}$", description="Chart ID")
    ],
    filepath: Annotated[Path, Field(description="File to save chart to")],
    format: Annotated[
        Literal["png", "pdf", "svg", "html"], Field(description="Export format")
    ] = "png",
    width: Annotated[
        Optional[int], Field(description="Width of the chart", ge=1)
    ] = None,
    height: Annotated[
        Optional[int], Field(description="Height of the chart", ge=1)
    ] = None,
    unit: Annotated[
        Literal["px", "mm", "in"],
        Field(
            description="Defines the unit in which the borderWidth, height and width will be measured in"
        ),
    ] = "px",
    mode: Annotated[
        Literal["rgb", "cmyk"], Field(description="Color mode (pdf format only)")
    ] = "rgb",
    scale: Annotated[
        float, Field(description="Scale factor for the chart (pdf format only)")
    ] = 1,
    zoom: Annotated[
        float, Field(description="Zoom level for the chart (png format only)")
    ] = 2,
    borderWidth: Annotated[
        Optional[int], Field(description="Width of the chart border")
    ] = None,
    borderColor: Annotated[
        Optional[str], Field(description="Color of the chart border")
    ] = None,
    plain: Annotated[
        bool,
        Field(
            description="Defines if only the visualization should be exported (true), or if it should include header and footer as well (false)"
        ),
    ] = False,
    # TODO what is fullVector?
    fullVector: Annotated[
        bool, Field(description="Whether to use full vector graphics")
    ] = False,
    ligatures: Annotated[bool, Field(description="Whether to use ligatures")] = True,
    transparent: Annotated[
        bool,
        Field(description="Whether to use transparent background (png format only)"),
    ] = False,
    logo: Annotated[str, Field(description="Logo display setting")] = "auto",
    logoId: Annotated[Optional[str], Field(description="ID of the logo to use")] = None,
    dark: Annotated[bool, Field(description="Whether to use dark mode")] = False,
) -> str:
    """Export a chart to different formats"""
    endpoint = f"charts/{chart_id}/export/{format}"
    params = {
        "width": width,
        "height": height,
        "unit": unit,
        "mode": mode,
        "scale": scale,
        "zoom": zoom,
        "borderWidth": borderWidth,
        "borderColor": borderColor,
        "plain": plain,
        "fullVector": fullVector,
        "ligatures": ligatures,
        "transparent": transparent if format.lower() == "png" else None,
        "logo": logo,
        "logoId": logoId,
        "dark": dark,
    }
    params = {k: v for k, v in params.items() if v is not None}

    response = await _make_request(ctx, method="GET", endpoint=endpoint, params=params)
    final_path = write_file(DIRECTORY, filepath, response.content)
    return f"Chart exported to {final_path}"


if __name__ == "__main__":
    logger.info("Starting Datawrapper MCP server")
    mcp.run()
