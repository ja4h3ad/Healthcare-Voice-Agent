# app/mcp/tools/appointment_tools.py
"""
Appointment tools that return FHIR-like responses
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional
import pytz
from bson import ObjectId

from app.database.database import Database
from app.mcp.schemas import (
    appointment_to_fhir,
    appointments_to_fhir_bundle,
    fhir_status_to_mongo
)

logger = logging.getLogger(__name__)


async def get_upcoming_appointments_tool(patient_id: str, days_ahead: int = 30) -> str:
    """
    Get upcoming appointments for a patient
    Returns FHIR R4 Bundle (searchset)

    Args:
        patient_id: Patient's ID
        days_ahead: Number of days to look ahead

    Returns:
        JSON string of FHIR Bundle or OperationOutcome
    """
    try:
        db = Database()
        await db.connect()

        # Get patient to retrieve account info
        patient = await db.get_patient_by_id(patient_id)

        if not patient:
            await db.disconnect()
            return json.dumps({
                "resourceType": "OperationOutcome",
                "issue": [{
                    "severity": "error",
                    "code": "not-found",
                    "diagnostics": f"No patient found with ID: {patient_id}"
                }]
            }, indent=2)

        # Get appointments
        patient_info, appointments = await db.get_patient_info(
            account_number=patient.get('accountNumber')
        )

        if not appointments:
            await db.disconnect()
            # Return empty bundle
            return json.dumps({
                "resourceType": "Bundle",
                "type": "searchset",
                "total": 0,
                "entry": []
            }, indent=2)

        # Filter for upcoming appointments
        now = datetime.now(pytz.UTC)
        end_date = now + timedelta(days=days_ahead)

        upcoming = []
        for appt in appointments:
            appt_datetime = appt.get('appointmentDateTime')

            if appt_datetime and not appt_datetime.tzinfo:
                appt_datetime = appt_datetime.replace(tzinfo=pytz.UTC)

            if (appt_datetime and
                    appt_datetime >= now and
                    appt_datetime <= end_date and
                    appt.get('status') != 'cancelled'):

                # Enrich with provider info
                if appt.get('doctorID'):
                    provider = await db.get_provider_info(appt['doctorID'])
                    appt['providerInfo'] = provider

                upcoming.append(appt)

        upcoming.sort(key=lambda x: x.get('appointmentDateTime', datetime.min))

        await db.disconnect()

        # Convert to FHIR Bundle
        fhir_bundle = appointments_to_fhir_bundle(upcoming)
        return json.dumps(fhir_bundle, indent=2, default=str)

    except Exception as e:
        logger.error(f"Error getting appointments: {str(e)}", exc_info=True)
        return json.dumps({
            "resourceType": "OperationOutcome",
            "issue": [{
                "severity": "error",
                "code": "exception",
                "diagnostics": str(e)
            }]
        }, indent=2)


async def get_appointment_by_id_tool(appointment_id: str) -> str:
    """
    Get appointment by ID
    Returns FHIR R4 Appointment resource

    Args:
        appointment_id: Appointment ID

    Returns:
        JSON string of FHIR Appointment or OperationOutcome
    """
    try:
        db = Database()
        await db.connect()

        appointment = await db.get_appointment_by_id(appointment_id)

        if not appointment:
            await db.disconnect()
            return json.dumps({
                "resourceType": "OperationOutcome",
                "issue": [{
                    "severity": "error",
                    "code": "not-found",
                    "diagnostics": f"No appointment found with ID: {appointment_id}"
                }]
            }, indent=2)

        # Enrich with provider info
        if appointment.get('doctorID'):
            provider = await db.get_provider_info(appointment['doctorID'])
            appointment['providerInfo'] = provider

        await db.disconnect()

        # Convert to FHIR
        fhir_appointment = appointment_to_fhir(appointment)
        return json.dumps(fhir_appointment, indent=2, default=str)

    except Exception as e:
        logger.error(f"Error getting appointment: {str(e)}", exc_info=True)
        return json.dumps({
            "resourceType": "OperationOutcome",
            "issue": [{
                "severity": "error",
                "code": "exception",
                "diagnostics": str(e)
            }]
        }, indent=2)


async def update_appointment_tool(appointment_id: str, update_data: dict) -> str:
    """
    Update an appointment
    Returns FHIR R4 Appointment resource

    Args:
        appointment_id: Appointment ID
        update_data: Fields to update (can include FHIR status)

    Returns:
        JSON string of updated FHIR Appointment or OperationOutcome
    """
    try:
        db = Database()
        await db.connect()

        # Convert FHIR status to MongoDB status if present
        if 'status' in update_data:
            update_data['status'] = fhir_status_to_mongo(update_data['status'])

        # Parse datetime if provided
        if 'appointmentDateTime' in update_data and isinstance(update_data['appointmentDateTime'], str):
            try:
                update_data['appointmentDateTime'] = datetime.strptime(
                    update_data['appointmentDateTime'],
                    "%Y-%m-%d %H:%M:%S"
                ).replace(tzinfo=pytz.UTC)
            except ValueError:
                update_data['appointmentDateTime'] = datetime.fromisoformat(
                    update_data['appointmentDateTime'].replace('Z', '+00:00')
                )

        # Update
        success = await db.update_appointment(appointment_id, update_data)

        if not success:
            await db.disconnect()
            return json.dumps({
                "resourceType": "OperationOutcome",
                "issue": [{
                    "severity": "error",
                    "code": "processing",
                    "diagnostics": f"Failed to update appointment: {appointment_id}"
                }]
            }, indent=2)

        # Get updated appointment
        updated = await db.get_appointment_by_id(appointment_id)

        # Enrich with provider info
        if updated.get('doctorID'):
            provider = await db.get_provider_info(updated['doctorID'])
            updated['providerInfo'] = provider

        await db.disconnect()

        # Convert to FHIR
        fhir_appointment = appointment_to_fhir(updated)
        return json.dumps(fhir_appointment, indent=2, default=str)

    except Exception as e:
        logger.error(f"Error updating appointment: {str(e)}", exc_info=True)
        return json.dumps({
            "resourceType": "OperationOutcome",
            "issue": [{
                "severity": "error",
                "code": "exception",
                "diagnostics": str(e)
            }]
        }, indent=2)