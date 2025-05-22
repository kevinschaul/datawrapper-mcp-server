import os
import json
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
        request_params = {
            "method": method,
            "url": url,
            "headers": headers,
            "params": params,
            "data": data,
            "json": json_data,
            "files": files,
        }
        logger.info(request_params)
        response = await client.request(**request_params)

        content_type = response.headers.get("content-type", "")
        if content_type and (
            "image" in content_type or "application/octet-stream" in content_type
        ):
            log_message = f"response: <binary data> [{len(response.content)} bytes]"
        else:
            log_message = f"response: {response.text}"

        await ctx.log(level="info", message=log_message)
        logger.info(log_message)

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


@mcp.tool()
async def search_charts(
    ctx: Context,
    userId: Annotated[
        Optional[int], Field(description="User id of visualization author")
    ] = None,
    authorId: Annotated[
        Optional[int], Field(description="User id of visualization author")
    ] = None,
    published: Annotated[
        Optional[bool], Field(description="Flag to filter results by publish status")
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
            description="List visualizations belonging to a specific team. Use teamId=null to search for user visualizations not part of a team"
        ),
    ] = None,
    order: Annotated[
        Literal["ASC", "DESC"],
        Field(description="Result order (ascending or descending)"),
    ] = "DESC",
    orderBy: Annotated[str, Field(description="Attribute to order by")] = "createdAt",
    limit: Annotated[
        int, Field(description="Maximum items to fetch. Useful for pagination.", ge=1)
    ] = 100,
    offset: Annotated[
        int, Field(description="Number of items to skip. Useful for pagination.", ge=0)
    ] = 0,
    minLastEditStep: Annotated[
        Optional[int],
        Field(
            description="Filter visualizations by the last editor step they've been opened in (1=upload, 2=describe, 3=visualize, etc)",
            ge=0,
            le=5,
        ),
    ] = None,
    expand: Annotated[
        bool, Field(description="Whether to include full chart metadata")
    ] = False,
) -> str:
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

    if response.status_code == 200:
        charts = response.json()
        return json.dumps(charts, indent=2)
    else:
        return f"Error: {response.status_code} - {response.text}"


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
        Literal[
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
            "d3-scatter-plot",
            "election-donut-chart",
            "tables",
            "d3-maps-choropleth",
            "d3-maps-symbols",
            "locator-map",
        ],
        Field(description="Type of chart to create"),
    ] = "d3-lines",
    forkable: Annotated[
        bool,
        Field(
            description="Set to true if you want to allow other users to fork this visualization"
        ),
    ] = False,
    organizationId: Annotated[
        Optional[str],
        Field(
            description="ID of the team (formerly known as organization) that the visualization should be created in. The authenticated user must have access to this team."
        ),
    ] = None,
    folderId: Annotated[
        Optional[int],
        Field(
            description="ID of the folder that the visualization should be created in. The authenticated user must have access to this folder."
        ),
    ] = None,
    externalData: Annotated[
        Optional[str], Field(description="URL of external dataset")
    ] = None,
    language: Annotated[
        Optional[str], Field(description="Visualization locale (e.g., en-US)")
    ] = None,
    metadata: Annotated[
        Optional[Dict], Field(description="Additional metadata for the chart")
    ] = None,
) -> str:
    """Create a new chart"""
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
        data.update(metadata)

    response = await _make_request(ctx, method="POST", endpoint=endpoint, data=data)

    if response.status_code in (200, 201):
        chart = response.json()
        chart_id = chart.get("id")
        return f"Chart created successfully with ID: {chart_id}\n{json.dumps(chart, indent=2)}"
    else:
        return f"Error creating chart: {response.status_code} - {response.text}"


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
) -> str:
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

    if response.status_code in (200, 204):
        return f"Data successfully uploaded to chart {chart_id}"
    else:
        return f"Error uploading data: {response.status_code} - {response.text}"


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

    if response.status_code == 200:
        # Return the raw data (usually CSV)
        return response.text
    else:
        return f"Error fetching chart data: {response.status_code} - {response.text}"


@mcp.tool()
async def get_chart_metadata(
    ctx: Context,
    chart_id: Annotated[
        str,
        Field(
            description="ID of the chart to fetch data from",
            pattern=r"^[a-zA-Z0-9]{5}$",
        ),
    ],
) -> str:
    """Request the metadata of a chart"""
    endpoint = f"charts/{chart_id}"
    response = await _make_request(ctx, method="GET", endpoint=endpoint)

    if response.status_code == 200:
        charts = response.json()
        return json.dumps(charts, indent=2)
    else:
        return (
            f"Error fetching chart metadata: {response.status_code} - {response.text}"
        )


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
        Optional[
            Literal[
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
                "d3-scatter-plot",
                "election-donut-chart",
                "tables",
                "d3-maps-choropleth",
                "d3-maps-symbols",
                "locator-map",
            ]
        ],
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
        Field(
            description="ID of the folder that the visualization should be placed in. The authenticated user must have access to this folder."
        ),
    ] = None,
    organizationId: Annotated[
        Optional[str],
        Field(
            description="ID of the team (formerly known as organization) that the visualization should belong to. The authenticated user must have access to this team."
        ),
    ] = None,
    metadata: Annotated[
        Optional[Dict], Field(description="Additional metadata for the chart")
    ] = None,
    forkable: Annotated[
        Optional[bool],
        Field(
            description="Set to true if you want to allow other users to fork this visualization"
        ),
    ] = None,
) -> str:
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
        data.update(metadata)

    if not data:
        return "No update parameters provided. Chart remains unchanged."

    response = await _make_request(
        ctx, method="PATCH", endpoint=endpoint, json_data=data
    )

    if response.status_code in (200, 204):
        return f"Chart {chart_id} updated successfully\n{json.dumps(response.json(), indent=2) if response.text else 'No content returned'}"
    else:
        return (
            f"Error updating chart metadata: {response.status_code} - {response.text}"
        )


@mcp.tool()
async def list_themes(
    ctx: Context,
    limit: Annotated[
        int,
        Field(
            description="Maximum items to fetch. Useful for pagination.",
            ge=0,
            default=100,
        ),
    ] = 100,
    offset: Annotated[
        int,
        Field(
            description="Number of items to skip. Useful for pagination.",
            ge=0,
            default=0,
        ),
    ] = 0,
    deleted: Annotated[
        bool, Field(description="Whether to include deleted themes.", default=False)
    ] = False,
) -> str:
    """Get a list of themes accessible by the authenticated user"""
    endpoint = "themes"

    params = {"limit": limit, "offset": offset, "deleted": deleted}
    response = await _make_request(ctx, method="GET", endpoint=endpoint, params=params)

    if response.status_code == 200:
        themes = response.json()
        return json.dumps(themes, indent=2)
    else:
        return f"Error fetching themes: {response.status_code} - {response.text}"


if __name__ == "__main__":
    logger.info("Starting Datawrapper MCP server")
    mcp.run()
