# app/mcp/tools/provider_tools.py
"""
Provider tools that return FHIR-like responses
"""

import json
import logging

from app.database.database import Database
from app.mcp.schemas import provider_to_fhir

logger = logging.getLogger(__name__)


async def get_provider_by_id_tool(provider_id: str) -> str:
    """
    Get provider by ID
    Returns FHIR R4 Practitioner resource

    Args:
        provider_id: Provider's ID

    Returns:
        JSON string of FHIR Practitioner or OperationOutcome
    """
    try:
        db = Database()
        await db.connect()

        provider = await db.get_provider_info(provider_id)

        await db.disconnect()

        if not provider or provider.get('firstName') == 'Unknown':
            return json.dumps({
                "resourceType": "OperationOutcome",
                "issue": [{
                    "severity": "error",
                    "code": "not-found",
                    "diagnostics": f"No provider found with ID: {provider_id}"
                }]
            }, indent=2)

        # Convert to FHIR
        fhir_provider = provider_to_fhir(provider)
        return json.dumps(fhir_provider, indent=2, default=str)

    except Exception as e:
        logger.error(f"Error getting provider: {str(e)}", exc_info=True)
        return json.dumps({
            "resourceType": "OperationOutcome",
            "issue": [{
                "severity": "error",
                "code": "exception",
                "diagnostics": str(e)
            }]
        }, indent=2)