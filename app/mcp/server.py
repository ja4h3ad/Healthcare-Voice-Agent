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