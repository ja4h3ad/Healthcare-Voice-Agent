# app/webhooks/sms_events.py
"""
Handle inbound SMS events
"""

from fastapi import Request
from fastapi.responses import JSONResponse
import logging

from app.models.events.sms_events import InboundSMSEvent
from app.services.appointment_reminder import AppointmentReminderAgent
from app.services.voice import make_call

logger = logging.getLogger(__name__)

# Initialize agent
reminder_agent = AppointmentReminderAgent()


async def handle_inbound_sms(sms: InboundSMSEvent) -> JSONResponse:
    """
    Handle inbound SMS and trigger appointment reminder call
    """
    from_number = sms.from_

    logger.info(f"Received SMS from {from_number}: {sms.text}")

    # Gather patient and appointment context
    context = await reminder_agent.handle_sms_trigger(from_number)

    if not context['success']:
        return JSONResponse(content={
            "status": "error",
            "message": context.get('error', 'Failed to gather patient info')
        }, status_code=404)

    # Store context for the call (you'll need this in WebSocket handler)
    # Could use Redis, in-memory cache, or pass via call metadata
    call_context_cache[from_number] = context

    # Initiate call with context
    call_uuid = make_call(
        to_number=from_number,
        context=context
    )

    if call_uuid:
        return JSONResponse(content={
            "status": "success",
            "message": f"Appointment reminder call initiated",
            "call_uuid": call_uuid
        })

    return JSONResponse(content={
        "status": "error",
        "message": "Failed to initiate call"
    }, status_code=500)