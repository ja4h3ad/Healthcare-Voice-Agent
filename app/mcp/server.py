# app/mcp/server.py

"""
Lightweight MCP Server for Healthcare EHR
Provides tools for AI agent to interact with patient and appointment data
"""

import asyncio
import json
import logging
from typing import Any, Sequence, List
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server

logger = logging.getLogger(__name__)

# initialize mcp service

mcp_server = Server("healthcare-ehr")

@mcp_server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available tools for the LLM"""
    return [
        Tool(
            name="get_patient_by_phone",
            description="Look up a patient by their mobile phone number",
            inputSchema={
                "type": "object",
                "properties": {
                    "mobile_number": {
                        "type": "string",
                        "description": "Patient's mobile number"
                    }
                },
                "required": ["mobile_number"]
            }
        ),
        Tool(
            name="get_patient_by_account",
            description="Look up a patient by their account number",
            inputSchema={
                "type": "object",
                "properties": {
                    "account_number": {
                        "type": "string",
                        "description": "Patient's account number"
                    }
                },
                "required": ["account_number"]
            }
        ),
        Tool(
            name="get_upcoming_appointments",
            description="Get upcoming appointments for a patient. Returns appointments with provider details.",
            inputSchema={
                "type": "object",
                "properties": {
                    "patient_id": {
                        "type": "string",
                        "description": "Patient's internal ID (MongoDB _id)"
                    },
                    "days_ahead": {
                        "type": "integer",
                        "description": "Number of days to look ahead (default: 30)",
                        "default": 30
                    }
                },
                "required": ["patient_id"]
            }
        ),
        Tool(
            name="get_appointment_details",
            description="Get full details of a specific appointment including patient and provider info",
            inputSchema={
                "type": "object",
                "properties": {
                    "appointment_id": {
                        "type": "string",
                        "description": "Appointment ID (MongoDB _id)"
                    }
                },
                "required": ["appointment_id"]
            }
        ),
        Tool(
            name="update_appointment",
            description="Update an appointment (reschedule, change status, etc)",
            inputSchema={
                "type": "object",
                "properties": {
                    "appointment_id": {
                        "type": "string",
                        "description": "Appointment ID to update"
                    },
                    "appointmentDateTime": {
                        "type": "string",
                        "description": "New appointment datetime (ISO format or 'YYYY-MM-DD HH:MM:SS')"
                    },
                    "status": {
                        "type": "string",
                        "enum": ["requested", "confirmed", "cancelled"],
                        "description": "New appointment status"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for the update"
                    }
                },
                "required": ["appointment_id"]
            }
        ),
        Tool(
            name="get_provider_info",
            description="Get information about a physician or aesthetician",
            inputSchema={
                "type": "object",
                "properties": {
                    "provider_id": {
                        "type": "string",
                        "description": "Provider's ID (doctorID)"
                    }
                },
                "required": ["provider_id"]
            }
        )
    ]

@mcp_server.call_tool()
async def call_tool(name: str, arguments: Any) -> Sequence [TextContent]:
    """Route tool calls to appropriate handlers"""
    logger.info(f"Tool called: {name} with arguments: {arguments}")
    from app.mcp.tools.patient_tools import (get_patient_by_phone_tool, get_patient_by_account_tool)
    from app.mcp.tools.appointment_tools import (get_upcoming_appointments_tool, get_appointment_details_tool, update_appointment_tool)
    from app.mcp.tools.provider_tools import get_provider_info_tool

    try:
        if name == "get_patient_by_phone":
            result = await get_patient_by_phone_tool(arguments["mobile_number"])
        elif name == "get_patient_by_account":
            result = await get_patient_by_account_tool(arguments["account_number"])
        elif name == "get_upcoming_appointments":
            result = await get_upcoming_appointments_tool(
                patient_id=arguments["patient_id"],
                days_ahead=arguments.get("days_ahead", 30)
            )
        elif name == "get_appointment_details":
            result = await get_appointment_details_tool(arguments["appointment_id"])
        elif name == "update_appointment":
            result = await update_appointment_tool(
                appointment_id=arguments["appointment_id"],
                update_data={k: v for k, v in arguments.items() if k != "appointment_id" and v is not None}
            )
        elif name == "get_provider_info":
            result = await get_provider_info_tool(arguments["provider_id"])
        else:
            raise ValueError(f"Unknown tool: {name}")

        return [TextContent(type="text", text=result)]

    except Exception as e:
        logger.error(f"Error calling tool: {name} with arguments: {arguments}:  {str(e)}", exc_info=True)
        error_response = {
            "error": str(e),
            "tool": name,
            "arguments": arguments
        }
        return [TextContent(type="text", text=json.dumps(error_response, indent=2))]

async def run_server():
    """
    Run the MCP server using stdio transport
    """

    async def run_server():
        """Run the MCP server using stdio transport"""
        async with stdio_server() as (read_stream, write_stream):
            await mcp_server.run(
                read_stream,
                write_stream,
                mcp_server.create_initialization_options()
            )


def main():
    """
    Entry point for MCP server
    """
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_server())

if __name__ == "__main__":
    main()
