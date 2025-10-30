# app/mcp/tools/provider_tools.py
"""
Provider(physician, physician assistant) lookup tool
"""

import logging
import json
from app.database.database import Database

logger = logging.getLogger(__name__)

async def get_provider_info_tool(provider_id: str) -> str:
    """
    Get provider information

    Args:
        provider_id: Provider's ID (doctorID)

    Returns:
        JSON string with provider info
    """
    try:
        db = Database()
        await db.connect()

        provider = await db.get_provider_info(provider_id)
        await db.disconnect()

        if not provider or provider['firstName'] == 'Unknown':
            return json.dumps({
                "status": "not_found",
                "message": f"No provider found with ID: {provider_id}"
            }, indent=2)

        response = {
            "status": "success",
            "provider": provider
        }

        return json.dumps(response, indent=2, default=str)

    except Exception as e:
        logger.error(f"Error getting provider info: {str(e)}", exc_info=True)
        return json.dumps({
            "status": "error",
            "message": str(e)
        }, indent=2)

