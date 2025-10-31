# app/services/appointment_agent.py (UPDATED)
"""
Appointment agent with FHIR function calling
"""

import json
import logging
from typing import Dict, Any
from datetime import datetime

from app.mcp.tools.patient_tools import get_patient_by_phone_tool, get_patient_by_id_tool
from app.mcp.tools.appointment_tools import (
    get_upcoming_appointments_tool,
    get_appointment_by_id_tool,
    update_appointment_tool
)

logger = logging.getLogger(__name__)


class AppointmentAgent:
    """
    Handles appointment self-service with FHIR-like interface
    """

    @staticmethod
    def build_system_prompt(patient_name: str, appointments: list) -> str:
        """Build system prompt based on patient context"""
        if not appointments:
            return f"""You are a friendly medical office assistant calling {patient_name}.

Unfortunately, we don't have any upcoming appointments on file for you. 

Ask if they would like to schedule an appointment, and let them know they can call our office at 555-0100 to book one.

Keep the conversation brief and professional."""

        # Get the next appointment (first entry in FHIR Bundle)
        next_appt = appointments[0]
        appt_datetime = next_appt.get('start')
        appt_type = next_appt.get('appointmentType', {}).get('coding', [{}])[0].get('display', 'appointment')
        participants = next_appt.get('participant', [])
        provider_name = "Unknown Provider"

        for participant in participants:
            if 'Practitioner' in participant.get('actor', {}).get('reference', ''):
                provider_name = participant.get('actor', {}).get('display', 'Unknown Provider')

        appointment_id = next_appt.get('id')

        return f"""You are a friendly medical office assistant calling {patient_name}.

You are calling to remind them about their upcoming appointment:
- Date/Time: {appt_datetime}
- Type: {appt_type}
- Provider: {provider_name}
- Appointment ID: {appointment_id}

Your conversation flow:
1. Greet the patient warmly
2. Remind them about the appointment details
3. Ask if they can still make it
4. If YES: Use confirm_appointment function
5. If NO: Ask if they want to reschedule or cancel, then use appropriate function

Keep responses conversational and brief - this is a phone call."""

    @staticmethod
    def get_function_definitions() -> list:
        """
        Define FHIR-like functions for the AI
        """
        return [
            {
                "name": "confirm_appointment",
                "description": "Mark appointment as confirmed (FHIR status: booked)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "appointment_id": {
                            "type": "string",
                            "description": "The FHIR Appointment ID"
                        }
                    },
                    "required": ["appointment_id"]
                }
            },
            {
                "name": "cancel_appointment",
                "description": "Cancel the appointment (FHIR status: cancelled)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "appointment_id": {
                            "type": "string",
                            "description": "The FHIR Appointment ID"
                        },
                        "reason": {
                            "type": "string",
                            "description": "Reason for cancellation"
                        }
                    },
                    "required": ["appointment_id"]
                }
            },
            {
                "name": "request_reschedule",
                "description": "Patient wants to reschedule (will be contacted by office)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "appointment_id": {
                            "type": "string",
                            "description": "The FHIR Appointment ID"
                        },
                        "preferred_time": {
                            "type": "string",
                            "description": "Patient's preferred time if mentioned"
                        }
                    },
                    "required": ["appointment_id"]
                }
            }
        ]

    @staticmethod
    async def execute_function(function_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute FHIR-like function calls
        """
        logger.info(f"Executing function: {function_name} with args: {arguments}")

        try:
            if function_name == "confirm_appointment":
                # Update status to 'booked' (FHIR) which maps to 'confirmed' (MongoDB)
                result_json = await update_appointment_tool(
                    appointment_id=arguments['appointment_id'],
                    update_data={'status': 'booked'}  # FHIR status
                )
                return json.loads(result_json)

            elif function_name == "cancel_appointment":
                reason = arguments.get('reason', 'Patient requested cancellation via phone')
                result_json = await update_appointment_tool(
                    appointment_id=arguments['appointment_id'],
                    update_data={
                        'status': 'cancelled',  # FHIR status
                        'reason': reason
                    }
                )
                return json.loads(result_json)

            elif function_name == "request_reschedule":
                # Mark as pending and log request
                return {
                    "resourceType": "OperationOutcome",
                    "issue": [{
                        "severity": "information",
                        "code": "informational",
                        "diagnostics": "Reschedule request noted. Office will call back to schedule."
                    }]
                }

            else:
                return {
                    "resourceType": "OperationOutcome",
                    "issue": [{
                        "severity": "error",
                        "code": "not-supported",
                        "diagnostics": f"Unknown function: {function_name}"
                    }]
                }

        except Exception as e:
            logger.error(f"Error executing function: {str(e)}")
            return {
                "resourceType": "OperationOutcome",
                "issue": [{
                    "severity": "error",
                    "code": "exception",
                    "diagnostics": str(e)
                }]
            }

    @staticmethod
    async def get_call_context(phone_number: str) -> Dict[str, Any]:
        """
        Gather patient and appointment context using FHIR-like calls
        """
        logger.info(f"Gathering FHIR context for {phone_number}")

        # Get patient (FHIR Patient resource)
        patient_json = await get_patient_by_phone_tool(phone_number)
        patient_resource = json.loads(patient_json)

        if patient_resource.get('resourceType') == 'OperationOutcome':
            return {
                'success': False,
                'error': patient_resource['issue'][0]['diagnostics']
            }

        patient_id = patient_resource['id']
        patient_name = patient_resource['name'][0]
        full_name = f"{patient_name['given'][0]} {patient_name['family']}"

        # Get upcoming appointments (FHIR Bundle)
        appointments_json = await get_upcoming_appointments_tool(
            patient_id=patient_id,
            days_ahead=30
        )
        bundle = json.loads(appointments_json)

        # Extract appointments from bundle
        appointments = []
        if bundle.get('resourceType') == 'Bundle':
            appointments = [entry['resource'] for entry in bundle.get('entry', [])]

        # Build system prompt
        system_prompt = AppointmentAgent.build_system_prompt(full_name, appointments)

        return {
            'success': True,
            'phone_number': phone_number,
            'patient_id': patient_id,
            'patient_name': full_name,
            'patient_resource': patient_resource,  # Full FHIR Patient
            'appointments': appointments,  # List of FHIR Appointments
            'system_prompt': system_prompt,
            'functions': AppointmentAgent.get_function_definitions()
        }