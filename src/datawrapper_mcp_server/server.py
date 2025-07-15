import os
import logging
from pathlib import Path
from typing import Annotated, Literal, Optional, Dict, Any

import httpx
from pydantic import Field
from mcp.server.fastmcp import Context, FastMCP, Image

logger = logging.getLogger("datawrapper_mcp")


def get_required_env(key: str) -> str:
    """Get a required environment variable or raise an error if not set"""
    value = os.environ.get(key)
    if not value:
        raise ValueError(f"{key} environment variable is not set")
    return value


API_BASE_URL = "https://api.datawrapper.de/v3"
API_KEY = get_required_env("DATAWRAPPER_MCP_API_KEY")
DIRECTORY = Path(get_required_env("DATAWRAPPER_MCP_DIRECTORY"))

CHART_TYPES = Literal[
    "d3-bars",
    "d3-bars-split",
    "d3-bars-stacked",
    "d3-bars-bullet",
    "d3-dot-plot",
    "d3-range-plot",
    "d3-arrow-plot",
    "column-chart",
    "grouped-column-chart",
    "stacked-column-chart",
    "d3-area",
    "d3-lines",
    "multiple-lines",
    "d3-pies",
    "d3-donuts",
    "d3-multiple-pies",
    "d3-multiple-donuts",
    "election-donut-chart",
    "d3-scatter-plot",
    "tables",
    "d3-maps-choropleth",
    "d3-maps-symbols",
    "locator-map",
]

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

    Args:
        ctx: The MCP context for logging
        method: HTTP method (GET, POST, etc.)
        endpoint: API endpoint path
        headers: Optional HTTP headers
        params: Optional query parameters
        data: Optional request body data
        json_data: Optional JSON request body
        files: Optional files to upload

    Returns:
        The HTTP response object
    """
    headers = headers or {}
    headers["Authorization"] = f"Bearer {API_KEY}"

    url = f"{API_BASE_URL}/{endpoint}"

    async with httpx.AsyncClient(timeout=10) as client:
        request_params = {
            "method": method,
            "url": url,
            "headers": headers,
            "params": params,
            "data": data,
            "json": json_data,
            "files": files,
        }
        request_params = {k: v for k, v in request_params.items() if v is not None}
        logger.info(f"Request: {method} {url}")
        response = await client.request(**request_params)

        # Handle logging based on content type
        content_type = response.headers.get("content-type", "")
        if content_type and (
            "image" in content_type or "application/octet-stream" in content_type
        ):
            log_message = f"Response: <binary data> [{len(response.content)} bytes]"
        else:
            log_message = f"Response: {response.status_code} - {response.text[:200]}{'...' if len(response.text) > 200 else ''}"

        await ctx.log(level="info", message=log_message)
        logger.info(log_message)

        response.raise_for_status()
        return response


def write_file(base_dir: Path, file_path: Path, content: bytes) -> Path:
    """
    Writes content to a file with proper filename sanitization and security checks.

    Args:
        base_dir: The allowed base directory to write inside of
        file_path: The relative path of the file within base_dir (can include subdirectories)
        content: The binary content to write to the file

    Raises:
        ValueError: If the file_path is invalid or attempts to access parent directories
        IOError: If writing to the file fails

    Returns:
        The sanitized filepath that was written to
    """
    logger.info(f"Writing file: {file_path}")

    if not file_path.name:
        raise ValueError("Invalid file path: empty filename")

    file_path_str = str(file_path)
    if file_path_str.startswith("/") or file_path_str.startswith("\\"):
        raise ValueError("Invalid file path: must be relative, not absolute")

    base_dir.mkdir(parents=True, exist_ok=True)

    target_path = base_dir / file_path
    target_path.parent.mkdir(parents=True, exist_ok=True)

    if not target_path.resolve().is_relative_to(base_dir.resolve()):
        raise ValueError(
            f"Security error: Path '{file_path}' attempts to escape base directory"
        )

    try:
        with target_path.open("wb") as f:
            f.write(content)
        logger.info(f"Successfully wrote {len(content)} bytes to {target_path}")
        return target_path
    except Exception as e:
        logger.error(f"File write error: {e}")
        raise IOError(f"Failed to write to file: {str(e)}")


@mcp.tool()
async def preview_chart(
    ctx: Context,
    chart_id: Annotated[
        str, Field(pattern=r"^[a-zA-Z0-9]{5}$", description="Chart ID")
    ],
) -> Image:
    """View a screenshot of the chart as a PNG image"""
    endpoint = f"charts/{chart_id}/export/png"
    response = await _make_request(ctx, method="GET", endpoint=endpoint)
    return Image(data=response.content, format="png")


@mcp.tool()
async def export_chart(
    ctx: Context,
    chart_id: Annotated[
        str, Field(pattern=r"^[a-zA-Z0-9]{5}$", description="Chart ID")
    ],
    filepath: Annotated[Path, Field(description="File to save chart to")],
    format: Annotated[
        Literal["png", "pdf", "svg"], Field(description="Export format")
    ] = "png",
    width: Annotated[
        Optional[float], Field(description="Width of the chart", ge=1)
    ] = None,
    height: Annotated[
        Optional[float], Field(description="Height of the chart", ge=1)
    ] = None,
    unit: Annotated[
        Literal["px", "mm", "in"],
        Field(description="Unit for measurements (borderWidth, height, width)"),
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
    transparent: Annotated[
        bool,
        Field(description="Whether to use transparent background (png format only)"),
    ] = False,
    borderWidth: Annotated[
        Optional[float], Field(description="Width of the chart border")
    ] = None,
    borderColor: Annotated[
        Optional[str], Field(description="Color of the chart border")
    ] = None,
    plain: Annotated[
        bool,
        Field(
            description="Export only the visualization (true) or include header/footer (false)"
        ),
    ] = False,
    fullVector: Annotated[
        bool, Field(description="Whether to use full vector graphics")
    ] = False,
    ligatures: Annotated[bool, Field(description="Whether to use ligatures")] = True,
    logo: Annotated[str, Field(description="Logo display setting")] = "auto",
    logoId: Annotated[Optional[str], Field(description="ID of the logo to use")] = None,
    dark: Annotated[bool, Field(description="Whether to use dark mode")] = False,
) -> str:
    """Export a chart to different formats (PNG, PDF, SVG)"""
    endpoint = f"charts/{chart_id}/export/{format}"
    params = {
        "width": width,
        "height": height,
        "unit": unit,
        "mode": mode if format.lower() == "pdf" else None,
        "scale": scale if format.lower() == "pdf" else None,
        "zoom": zoom if format.lower() == "png" else None,
        "transparent": transparent if format.lower() == "png" else None,
        "borderWidth": borderWidth,
        "borderColor": borderColor,
        "plain": plain,
        "fullVector": fullVector,
        "ligatures": ligatures,
        "logo": logo,
        "logoId": logoId,
        "dark": dark,
    }
    params = {k: v for k, v in params.items() if v is not None}

    response = await _make_request(ctx, method="GET", endpoint=endpoint, params=params)
    final_path = write_file(DIRECTORY, filepath, response.content)
    return f"Chart exported to {final_path}"


@mcp.tool()
async def search_charts(
    ctx: Context,
    userId: Annotated[
        Optional[int], Field(description="User ID of visualization author")
    ] = None,
    authorId: Annotated[
        Optional[int],
        Field(description="User ID of visualization author (alternative)"),
    ] = None,
    published: Annotated[
        Optional[bool], Field(description="Filter by publish status")
    ] = None,
    search: Annotated[
        Optional[str], Field(description="Search for charts with a specific title")
    ] = None,
    folderId: Annotated[
        Optional[int], Field(description="List visualizations inside a specific folder")
    ] = None,
    teamId: Annotated[
        Optional[str],
        Field(
            description="List visualizations for a specific team (use teamId=null for user visualizations not in a team)"
        ),
    ] = None,
    order: Annotated[
        Literal["ASC", "DESC"],
        Field(description="Result order (ascending or descending)"),
    ] = "DESC",
    orderBy: Annotated[str, Field(description="Attribute to order by")] = "createdAt",
    limit: Annotated[int, Field(description="Maximum items to fetch", ge=1)] = 100,
    offset: Annotated[int, Field(description="Number of items to skip", ge=0)] = 0,
    minLastEditStep: Annotated[
        Optional[int],
        Field(
            description="Filter by last editor step (1=upload, 2=describe, 3=visualize, etc)",
            ge=0,
            le=5,
        ),
    ] = None,
    expand: Annotated[
        bool, Field(description="Whether to include full chart metadata")
    ] = False,
):
    """Search and filter a list of your charts"""
    endpoint = "charts"
    params = {
        "userId": userId,
        "authorId": authorId,
        "published": published,
        "search": search,
        "folderId": folderId,
        "teamId": teamId,
        "order": order,
        "orderBy": orderBy,
        "limit": limit,
        "offset": offset,
        "minLastEditStep": minLastEditStep,
        "expand": expand,
    }
    params = {k: v for k, v in params.items() if v is not None}
    response = await _make_request(ctx, method="GET", endpoint=endpoint, params=params)
    return response.json()


@mcp.tool()
async def create_chart(
    ctx: Context,
    title: Annotated[
        str,
        Field(
            description="Title of your visualization. This will be the visualization headline."
        ),
    ],
    theme: Annotated[
        str, Field(description="Chart theme to use.", min_length=2)
    ] = "datawrapper",
    type: Annotated[
        CHART_TYPES,
        Field(description="Type of chart to create"),
    ] = "d3-lines",
    forkable: Annotated[
        bool,
        Field(description="Allow other users to fork this visualization"),
    ] = False,
    organizationId: Annotated[
        Optional[str],
        Field(description="Team ID that should own the visualization"),
    ] = None,
    folderId: Annotated[
        Optional[int],
        Field(description="Folder ID to store the visualization in"),
    ] = None,
    externalData: Annotated[
        Optional[str], Field(description="URL of external dataset")
    ] = None,
    language: Annotated[
        Optional[str], Field(description="Visualization locale (e.g., en-US)")
    ] = None,
    metadata: Annotated[
        Optional[Dict[str, Any]], Field(description="Additional metadata for the chart")
    ] = None,
):
    """Create a new chart with the specified properties"""
    endpoint = "charts"
    data = {
        "title": title,
        "theme": theme,
        "type": type,
        "forkable": forkable,
        "organizationId": organizationId,
        "folderId": folderId,
        "externalData": externalData,
        "language": language,
    }
    data = {k: v for k, v in data.items() if v is not None}

    if metadata:
        data.update({"metadata": metadata})

    response = await _make_request(ctx, method="POST", endpoint=endpoint, data=data)
    return response.json()


@mcp.tool()
async def upload_chart_data(
    ctx: Context,
    chart_id: Annotated[
        str,
        Field(
            description="ID of the chart to upload data to", pattern=r"^[a-zA-Z0-9]{5}$"
        ),
    ],
    data: Annotated[
        str,
        Field(description="CSV data or custom JSON map to be uploaded to the chart"),
    ],
    content_type: Annotated[
        Literal["text/csv", "application/json"],
        Field(description="Content type of the data being uploaded"),
    ] = "text/csv",
):
    """
    Upload data for a chart or map.

    The data can be in CSV format (comma or semicolon separated) or JSON format.
    For CSV data, the first row is expected to contain column headers.

    Example CSV data:
    ```
    country;Share of population that lives in the capital;in other urban areas;in rural areas
    Iceland (Reykjavik);56.02;38;6
    Argentina (Buenos Aires);34.95;56.6;8.4
    Japan (Tokyo);29.52;63.5;7
    UK (London);22.7;59.6;17.7
    Denmark (Copenhagen);22.16;65.3;12.5
    France (Paris);16.77;62.5;20.7
    Russia (Moscow);8.39;65.5;26.1
    Niger (Niamey);5.53;12.9;81.5
    Germany (Berlin);4.35;70.7;24.9
    India (Delhi);1.93;30.4;67.6
    USA (Washington, D.C.);1.54;79.9;18.6
    China (Beijing);1.4;53;45.6
    ```
    """
    endpoint = f"charts/{chart_id}/data"
    headers = {"Content-Type": content_type}
    response = await _make_request(
        ctx, method="PUT", endpoint=endpoint, data=data, headers=headers
    )
    return response.json()


@mcp.tool()
async def get_chart_data(
    ctx: Context,
    chart_id: Annotated[
        str,
        Field(
            description="ID of the chart to fetch data from",
            pattern=r"^[a-zA-Z0-9]{5}$",
        ),
    ],
) -> str:
    """Request the data of a chart, which is usually a CSV"""
    endpoint = f"charts/{chart_id}/data"
    response = await _make_request(ctx, method="GET", endpoint=endpoint)

    # Return the raw data (usually CSV)
    return response.text


@mcp.tool()
async def get_chart_metadata(
    ctx: Context,
    chart_id: Annotated[
        str,
        Field(
            description="ID of the chart to fetch metadata from",
            pattern=r"^[a-zA-Z0-9]{5}$",
        ),
    ],
):
    """Request the metadata of a chart including title, type, theme, and other properties"""
    endpoint = f"charts/{chart_id}"
    response = await _make_request(ctx, method="GET", endpoint=endpoint)
    return response.json()


@mcp.tool()
async def update_chart_metadata(
    ctx: Context,
    chart_id: Annotated[
        str,
        Field(
            description="ID of the chart to update",
            pattern=r"^[a-zA-Z0-9]{5}$",
        ),
    ],
    title: Annotated[
        Optional[str],
        Field(description="Title of your chart. This will be the chart headline."),
    ] = None,
    theme: Annotated[
        Optional[str], Field(description="Chart theme to use.", min_length=2)
    ] = None,
    type: Annotated[
        Optional[CHART_TYPES],
        Field(description="Type of the chart"),
    ] = None,
    externalData: Annotated[
        Optional[str], Field(description="URL of external dataset")
    ] = None,
    language: Annotated[
        Optional[str], Field(description="Visualization locale (e.g., en-US)")
    ] = None,
    lastEditStep: Annotated[
        Optional[int],
        Field(description="Current position in chart editor workflow", ge=1, le=5),
    ] = None,
    publicVersion: Annotated[
        Optional[int], Field(description="Public version of the chart")
    ] = None,
    publicUrl: Annotated[
        Optional[str], Field(description="Public URL of the chart")
    ] = None,
    publishedAt: Annotated[Optional[str], Field(description="Publication date")] = None,
    folderId: Annotated[
        Optional[int],
        Field(description="ID of the folder to place the visualization in"),
    ] = None,
    organizationId: Annotated[
        Optional[str],
        Field(description="ID of the team that should own the visualization"),
    ] = None,
    metadata: Annotated[
        Optional[Dict[str, Any]], Field(description="Additional metadata for the chart")
    ] = None,
    forkable: Annotated[
        Optional[bool],
        Field(description="Allow other users to fork this visualization"),
    ] = None,
):
    """Update metadata for an existing chart

    This function allows you to update various properties of an existing chart.
    Only the properties you specify will be updated; all others will remain unchanged.

    Get the current metadata for an existing chart with get_chart_metadata().
    """
    endpoint = f"charts/{chart_id}"
    data = {
        "title": title,
        "theme": theme,
        "type": type,
        "externalData": externalData,
        "language": language,
        "lastEditStep": lastEditStep,
        "publicVersion": publicVersion,
        "publicUrl": publicUrl,
        "publishedAt": publishedAt,
        "folderId": folderId,
        "organizationId": organizationId,
        "forkable": forkable,
    }
    data = {k: v for k, v in data.items() if v is not None}

    if metadata is not None:
        data.update({"metadata": metadata})

    if not data:
        return "No update parameters provided. Chart remains unchanged."

    response = await _make_request(
        ctx, method="PATCH", endpoint=endpoint, json_data=data
    )
    return response.json()


@mcp.tool()
async def list_themes(
    ctx: Context,
    limit: Annotated[
        int,
        Field(
            description="Maximum number of themes to fetch",
            ge=0,
        ),
    ] = 100,
    offset: Annotated[
        int,
        Field(
            description="Number of themes to skip",
            ge=0,
        ),
    ] = 0,
    deleted: Annotated[bool, Field(description="Include deleted themes")] = False,
):
    """Get a list of themes accessible by the authenticated user"""
    endpoint = "themes"
    params = {"limit": limit, "offset": offset, "deleted": deleted}
    response = await _make_request(ctx, method="GET", endpoint=endpoint, params=params)
    return response.json()


if __name__ == "__main__":
    logger.info("Starting Datawrapper MCP server")
    try:
        mcp.run()
    except Exception as e:
        logger.critical(f"Failed to start MCP server: {e}", exc_info=True)
