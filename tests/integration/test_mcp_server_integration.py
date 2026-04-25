import asyncio
from pathlib import Path

import pytest
from fastmcp import Client

from ltspice_mcp.app import create_mcp_server
from ltspice_mcp.config import ServerConfig


async def _poll_execute_status(client: Client, timeout_s: float = 3.0) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout_s
    while asyncio.get_event_loop().time() < deadline:
        status = (await client.call_tool("execute_status")).data
        if status.get("status") != "performing LTspice operation in progress":
            return status
        await asyncio.sleep(0.05)
    return (await client.call_tool("execute_status")).data


@pytest.mark.asyncio
async def test_mcp_server_tools_end_to_end(tmp_path: Path):
    cfg = ServerConfig(
        mcp_server_name="My PyLTSpice MCP Server",
        mcp_server_url="stdio://",
        wine_path=str((tmp_path / "wine").resolve()),
        ltspice_path=str((tmp_path / "LTspice.exe").resolve()),
        enable_extra_tools=True,
        timeout=3,
    )
    server = create_mcp_server(config=cfg, project_root=tmp_path)

    async with Client(server) as client:
        tools = await client.list_tools()
        tool_names = {tool.name for tool in tools}
        assert {"runtime_info", "execute_status", "stop_reset", "execute"}.issubset(tool_names)

        runtime_started = (await client.call_tool("runtime_info")).data
        assert runtime_started["status"] == "performing LTspice operation in progress"

        runtime_final = await _poll_execute_status(client)
        assert runtime_final["operation"] in {"runtime_info", "execute"}
        assert runtime_final["status"] in {"simulator not configured!", "LTspice operation completed!"}

        execute_started = (await client.call_tool("execute", {"api_name": "all_loggers", "inputs": {}})).data
        assert execute_started["status"] == "performing LTspice operation in progress"

        execute_final = await _poll_execute_status(client)
        assert execute_final["status"] == "LTspice operation completed!"
        assert execute_final["operation"] == "execute"
        assert "result" in execute_final["output"]

        missing_file = (
            await client.call_tool(
                "execute",
                {
                    "api_name": "RawRead",
                    "inputs": {"raw_file": str((tmp_path / "missing.raw").resolve())},
                },
            )
        ).data
        assert missing_file["status"] == "performing LTspice operation in progress"

        missing_final = await _poll_execute_status(client)
        assert missing_final["status"] == "file not found!"

        reset_started = (await client.call_tool("stop_reset")).data
        assert reset_started["status"] == "performing LTspice operation in progress"

        reset_final = await _poll_execute_status(client)
        assert reset_final["status"] == "LTspice operation completed!"
        assert reset_final["operation"] == "stop_reset"
