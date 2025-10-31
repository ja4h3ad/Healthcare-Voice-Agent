# app/mcp/tools/patient_tools.py
"""
Patient tools that return FHIR-like responses
"""

import json
import logging
from typing import Optional

from app.database.database import Database
from app.mcp.schemas import patient_to_fhir

logger = logging.getLogger(__name__)


async def get_patient_by_phone_tool(phone: str) -> str:
    """
    Look up patient by phone and return FHIR R4 Patient resource

    Args:
        phone: Patient's mobile number

    Returns:
        JSON string of FHIR Patient resource or OperationOutcome
    """
    try:
        db = Database()
        await db.connect()

        patient_info, _ = await db.get_patient_info(mobile_number=phone)

        await db.disconnect()

        if not patient_info:
            return json.dumps({
                "resourceType": "OperationOutcome",
                "issue": [{
                    "severity": "error",
                    "code": "not-found",
                    "diagnostics": f"No patient found with phone number: {phone}"
                }]
            }, indent=2)

        # Convert to FHIR format
        fhir_patient = patient_to_fhir(patient_info)
        return json.dumps(fhir_patient, indent=2, default=str)

    except Exception as e:
        logger.error(f"Error looking up patient: {str(e)}", exc_info=True)
        return json.dumps({
            "resourceType": "OperationOutcome",
            "issue": [{
                "severity": "error",
                "code": "exception",
                "diagnostics": str(e)
            }]
        }, indent=2)


async def get_patient_by_id_tool(patient_id: str) -> str:
    """
    Get patient by ID and return FHIR R4 Patient resource

    Args:
        patient_id: Patient's MongoDB _id

    Returns:
        JSON string of FHIR Patient resource or OperationOutcome
    """
    try:
        db = Database()
        await db.connect()

        patient_info = await db.get_patient_by_id(patient_id)

        await db.disconnect()

        if not patient_info:
            return json.dumps({
                "resourceType": "OperationOutcome",
                "issue": [{
                    "severity": "error",
                    "code": "not-found",
                    "diagnostics": f"No patient found with ID: {patient_id}"
                }]
            }, indent=2)

        # Convert to FHIR format
        fhir_patient = patient_to_fhir(patient_info)
        return json.dumps(fhir_patient, indent=2, default=str)

    except Exception as e:
        logger.error(f"Error getting patient: {str(e)}", exc_info=True)
        return json.dumps({
            "resourceType": "OperationOutcome",
            "issue": [{
                "severity": "error",
                "code": "exception",
                "diagnostics": str(e)
            }]
        }, indent=2)