# app/mcp/tools/appointment_tools.py
"""
Appointment management tools matching MongoDB schema
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional
import pytz
from bson import ObjectId

from app.database.database import Database

logger = logging.getLogger(__name__)


# app/mcp/tools/appointment_tools.py

async def get_upcoming_appointments_tool(patient_id: str, days_ahead: int = 30) -> str:
    """
    Get upcoming appointments for a patient
    """
    try:
        db = Database()
        await db.connect()

        # Use the new method to get patient by ID
        patient = await db.get_patient_by_id(patient_id)

        if not patient:
            await db.disconnect()
            return json.dumps({
                "status": "not_found",
                "message": f"No patient found with ID: {patient_id}"
            }, indent=2)

        # Now use get_patient_info with account_number or mobile_number
        patient_info, appointments = await db.get_patient_info(
            account_number=patient.get('accountNumber'),
            mobile_number=patient.get('mobileNumber')
        )

        if not appointments:
            await db.disconnect()
            return json.dumps({
                "status": "success",
                "count": 0,
                "appointments": []
            }, indent=2)

            # Filter for upcoming appointments within date range
        now = datetime.now(pytz.UTC)
        end_date = now + timedelta(days=days_ahead)

        upcoming_appointments = []
        for appt in appointments:
            appt_datetime = appt.get('appointmentDateTime')

            # Ensure datetime is timezone-aware
            if appt_datetime and not appt_datetime.tzinfo:
                appt_datetime = appt_datetime.replace(tzinfo=pytz.UTC)

            # Filter: future appointments within range, not cancelled
            if (appt_datetime and
                    appt_datetime >= now and
                    appt_datetime <= end_date and
                    appt.get('status') != 'cancelled'):

                appt['_id'] = str(appt['_id'])

                # Get provider info
                if appt.get('doctorID'):
                    provider = await db.get_provider_info(appt['doctorID'])
                    appt['providerInfo'] = provider

                upcoming_appointments.append(appt)

        # Sort by date
        upcoming_appointments.sort(key=lambda x: x.get('appointmentDateTime', datetime.min))

        await db.disconnect()

        response = {
            "status": "success",
            "count": len(upcoming_appointments),
            "appointments": upcoming_appointments
        }

        return json.dumps(response, indent=2, default=str)

    except Exception as e:
        logger.error(f"Error getting appointments: {str(e)}", exc_info=True)
        return json.dumps({
            "status": "error",
            "message": str(e)
        }, indent=2)


async def get_appointment_details_tool(appointment_id: str) -> str:
    """
    Get full details of a specific appointment

    Args:
        appointment_id: Appointment MongoDB _id

    Returns:
        JSON string with appointment details
    """
    try:
        db = Database()
        await db.connect()

        # Use your existing method
        appointment = await db.get_appointment_by_id(appointment_id)

        if not appointment:
            await db.disconnect()
            return json.dumps({
                "status": "not_found",
                "message": f"No appointment found with ID: {appointment_id}"
            }, indent=2)

        # Convert ObjectId to string
        appointment['_id'] = str(appointment['_id'])

        # Get patient info using direct db access
        patient_info = await db.db.patients.find_one({"_id": ObjectId(appointment['patientID'])})
        if patient_info:
            patient_info['_id'] = str(patient_info['_id'])
            appointment['patientInfo'] = patient_info

        # Get provider info
        if appointment.get('doctorID'):
            provider = await db.get_provider_info(appointment['doctorID'])
            appointment['providerInfo'] = provider

        await db.disconnect()

        response = {
            "status": "success",
            "appointment": appointment
        }

        return json.dumps(response, indent=2, default=str)

    except Exception as e:
        logger.error(f"Error getting appointment details: {str(e)}", exc_info=True)
        return json.dumps({
            "status": "error",
            "message": str(e)
        }, indent=2)


async def update_appointment_tool(appointment_id: str, update_data: dict) -> str:
    """
    Update an appointment

    Args:
        appointment_id: Appointment ID
        update_data: Dictionary with fields to update

    Returns:
        JSON string with updated appointment
    """
    try:
        db = Database()
        await db.connect()

        # Parse datetime if provided as string
        if 'appointmentDateTime' in update_data and isinstance(update_data['appointmentDateTime'], str):
            try:
                update_data['appointmentDateTime'] = datetime.strptime(
                    update_data['appointmentDateTime'],
                    "%Y-%m-%d %H:%M:%S"
                ).replace(tzinfo=pytz.UTC)
            except ValueError:
                # Try ISO format
                update_data['appointmentDateTime'] = datetime.fromisoformat(
                    update_data['appointmentDateTime'].replace('Z', '+00:00')
                )

        # Use your existing update method
        success = await db.update_appointment(appointment_id, update_data)

        if not success:
            await db.disconnect()
            return json.dumps({
                "status": "error",
                "message": f"Failed to update appointment: {appointment_id}"
            }, indent=2)

        # Get updated appointment
        updated_appointment = await db.get_appointment_by_id(appointment_id)
        updated_appointment['_id'] = str(updated_appointment['_id'])

        await db.disconnect()

        response = {
            "status": "success",
            "message": "Appointment updated successfully",
            "appointment": updated_appointment
        }

        return json.dumps(response, indent=2, default=str)

    except Exception as e:
        logger.error(f"Error updating appointment: {str(e)}", exc_info=True)
        return json.dumps({
            "status": "error",
            "message": str(e)
        }, indent=2)
