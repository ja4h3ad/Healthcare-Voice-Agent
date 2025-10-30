# app/mcp/tools/patient_tools.py
"""
Patient lookup tools matching  MongoDB schema
"""

import json
import logging
from typing import Optional

from app.database.database import Database

logger = logging.getLogger(__name__)

async def get_patient_by_phone_tool(mobile_number: str) -> str:
    """
    Look up patient by mobile number

    Args:
        mobile_number: Patient's mobile phone number

    Returns:
        JSON string with patient info and appointments
    """

    # query mongo
    try:
        db=Database()
        await db.connect()

        patient_info, appointments = await db.get_patient_info(mobile_number=mobile_number)
        await db.disconnect()

        if not patient_info:
            return json.dumps({
                "status":  "not found",
                "message": f"No patient found with mobile number {mobile_number}"
            }, indent=2)
        # convert ObjectId to string
        patient_info['_id'] = str(patient_info['_id'])

        # add provider detail to patient info
        enriched_appointments = []
        for appt in appointments:
            appt['_id'] = str(appt['_id'])

            # get provider info
            if appt.get('doctorID'):
                db_temp = Database()
                await db_temp.connect()
                provider = await db_temp.get_provider_info(appt['doctorID'])
                await db_temp.disconnect()
                appt['providerInfo'] = provider

            enriched_appointments.append(appt)

        response = {
            "status": "ok",
            "patient": patient_info,
            "appointments": enriched_appointments
        }

        return json.dumps(response, indent=2, default=str)

    except Exception as e:
        logger.error(f"Error looking up patient by phone:  {str(e)}", exc_info=True)
        return json.dumps({
            "status": "error",
            "message": str(e)
        }, indent=2)


async def get_patient_by_account_tool(account_number: str) -> str:
    """
    Look up patient by account number

    Args:
        account_number: Patient's account number

    Returns:
        JSON string with patient info and appointments
    """
    try:
        db = Database()
        await db.connect()

        # Use your existing method
        patient_info, appointments = await db.get_patient_info(account_number=account_number)

        await db.disconnect()

        if not patient_info:
            return json.dumps({
                "status": "not_found",
                "message": f"No patient found with account number: {account_number}"
            }, indent=2)

        # Convert ObjectId to string
        patient_info['_id'] = str(patient_info['_id'])

        # Enrich appointments with provider info
        enriched_appointments = []
        for appt in appointments:
            appt['_id'] = str(appt['_id'])

            # Get provider info
            if appt.get('doctorID'):
                db_temp = Database()
                await db_temp.connect()
                provider = await db_temp.get_provider_info(appt['doctorID'])
                await db_temp.disconnect()
                appt['providerInfo'] = provider

            enriched_appointments.append(appt)

        response = {
            "status": "success",
            "patient": patient_info,
            "appointments": enriched_appointments
        }

        return json.dumps(response, indent=2, default=str)

    except Exception as e:
        logger.error(f"Error looking up patient by account: {str(e)}", exc_info=True)
        return json.dumps({
            "status": "error",
            "message": str(e)
        }, indent=2)