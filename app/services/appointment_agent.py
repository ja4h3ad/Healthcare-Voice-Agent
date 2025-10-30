# app/services/appointment_agent.py
"""
Orchestrates the appointment reminder flow
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from app.mcp.tools.patient_tools import get_patient_by_phone_tool
from app.mcp.tools.appointment_tools import (
    get_upcoming_appointments_tool,
    update_appointment_tool
)

logger = logging.getLogger(__name__)


class AppointmentReminderAgent:
    """
    Agent that handles appointment reminder conversations
    Integrates LLM with MCP tools
    """

    def __init__(self):
        self.conversation_state = {}

    async def handle_sms_trigger(self, phone_number: str) -> Dict[str, Any]:
        """
        Called when SMS is received
        Gathers patient/appointment info before call is made

        Returns context for the LLM to use during the call
        """
        logger.info(f"Gathering appointment info for {phone_number}")

        # Use MCP tool directly (no server needed)
        patient_data_json = await get_patient_by_phone_tool(phone_number)
        patient_data = json.loads(patient_data_json)

        if patient_data['status'] != 'success':
            return {
                'success': False,
                'error': 'Patient not found'
            }

        patient = patient_data['patient']
        patient_id = patient['_id']
        patient_name = f"{patient['firstName']} {patient['lastName']}"

        # Get upcoming appointments using MCP tool
        appointments_json = await get_upcoming_appointments_tool(
            patient_id=patient_id,
            days_ahead=30
        )
        appointments_data = json.loads(appointments_json)

        upcoming_appointments = appointments_data.get('appointments', [])

        # Build context for LLM
        context = {
            'success': True,
            'phone_number': phone_number,
            'patient_id': patient_id,
            'patient_name': patient_name,
            'patient_info': patient,
            'upcoming_appointments': upcoming_appointments,
            'system_prompt': self._build_system_prompt(patient_name, upcoming_appointments)
        }

        return context

    def _build_system_prompt(self, patient_name: str, appointments: list) -> str:
        """
        Build the system prompt for the LLM based on patient context
        """
        if not appointments:
            return f"""You are a helpful medical office assistant calling {patient_name}.

Unfortunately, we don't see any upcoming appointments scheduled for you. 
Would you like to schedule an appointment?"""

        # Format appointment info
        next_appt = appointments[0]
        appt_datetime = next_appt.get('appointmentDateTime')
        appt_type = next_appt.get('appointmentType', 'appointment')
        provider_info = next_appt.get('providerInfo', {})
        provider_name = f"Dr. {provider_info.get('lastName', 'Unknown')}"

        return f"""You are a helpful medical office assistant calling {patient_name}.

You are calling to remind them about their upcoming {appt_type} appointment.

Appointment Details:
- Date/Time: {appt_datetime}
- Provider: {provider_name}
- Type: {appt_type}

Your goal:
1. Confirm they received the reminder
2. Ask if they can keep the appointment
3. If they want to reschedule or cancel, gather their preference

Available actions you can take:
- confirm_appointment: Patient confirms they will attend
- request_reschedule: Patient wants to change the date/time
- request_cancellation: Patient wants to cancel

Be warm, professional, and helpful. Keep responses concise since this is a voice call."""

    async def handle_tool_call(self, tool_name: str, tool_args: Dict[str, Any]) -> str:
        """
        Handle tool calls from the LLM during conversation
        This is called when Deepgram Flux invokes a function
        """
        logger.info(f"LLM requested tool: {tool_name} with args: {tool_args}")

        if tool_name == "confirm_appointment":
            # Mark appointment as confirmed
            appointment_id = tool_args.get('appointment_id')
            result = await update_appointment_tool(
                appointment_id=appointment_id,
                update_data={'status': 'confirmed'}
            )
            return result

        elif tool_name == "request_reschedule":
            # Initiate reschedule flow
            return json.dumps({
                "status": "reschedule_requested",
                "message": "I'd be happy to help you reschedule. What date and time works better for you?"
            })

        elif tool_name == "request_cancellation":
            appointment_id = tool_args.get('appointment_id')
            reason = tool_args.get('reason', 'Patient requested cancellation')
            result = await update_appointment_tool(
                appointment_id=appointment_id,
                update_data={
                    'status': 'cancelled',
                    'reason': reason
                }
            )
            return result

        else:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})