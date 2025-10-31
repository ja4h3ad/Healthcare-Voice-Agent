"""
Vonage Healthcare Voice Agent with Deepgram Flux AI

Handles:
- SMS-triggered outbound calls
- Appointment reminders via conversational AI
- WebSocket audio streaming for ASR and TTS
"""

import os
from urllib.parse import urljoin
import logging

# FastAPI and pydantic
from fastapi import FastAPI, Request, WebSocket, Depends
from fastapi.responses import JSONResponse
import uvicorn
from typing import Optional, Dict, Any
from dotenv import load_dotenv

from vonage import Vonage, Auth

# Import custom modules
from app.webhooks.websocket_events import handle_voice_websocket, call_contexts
from app.services.appointment_agent import AppointmentAgent
from app.services.voice import make_call
from app.branded_calling.first_orion import get_auth_token, send_push_notification
from app.telemetry.call_tracker import call_tracker
from app.models.events.sms_events import InboundSMSEvent

# Configure global logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

# Load environment variables for local development
load_dotenv()

# VCR automatically injects these environment variables:
VONAGE_APPLICATION_ID = os.environ.get("VCR_API_APPLICATION_ID")
VONAGE_PRIVATE_KEY = os.environ.get("VONAGE_APPLICATION_PRIVATE_KEY")
VONAGE_NUMBER = os.environ.get("VONAGE_NUMBER")
WEBHOOK_BASE_URL = os.environ.get("VCR_INSTANCE_PUBLIC_URL") or os.environ.get("WEBHOOK_BASE_URL")
FIRST_ORION_API_KEY = os.environ.get("FIRST_ORION_API_KEY")
FIRST_ORION_API_PASSWORD = os.environ.get("FIRST_ORION_API_PASSWORD")
VCR_PORT = os.environ.get("VCR_PORT", "3000")

logger.info(f"Starting application with webhook base URL: {WEBHOOK_BASE_URL}")

# Initialize Vonage client with application-based authentication
# VCR provides the private key as a string in VCR_PRIVATE_KEY
if VONAGE_PRIVATE_KEY:
    # If it's a file path, read it; otherwise use it directly as a string
    if os.path.isfile(VONAGE_PRIVATE_KEY):
        auth = Auth(application_id=VONAGE_APPLICATION_ID, private_key=VONAGE_PRIVATE_KEY)
    else:
        # VCR provides the key content directly
        auth = Auth(application_id=VONAGE_APPLICATION_ID, private_key=VONAGE_PRIVATE_KEY)
else:
    raise ValueError("No private key found in environment variables")

vonage = Vonage(auth)

# Initialize FastAPI application
app = FastAPI(
    title="Healthcare Voice Agent",
    version="1.0.0",
    description="Branded calling with Conversational AI Voice Agent"
)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_webhook_url(endpoint):
    """
    Construct full webhook URL from base URL and endpoint

    Args:
        endpoint (str): The webhook endpoint path

    Returns:
        str: Complete webhook URL
    """
    return urljoin(WEBHOOK_BASE_URL, endpoint)


# ============================================================================
# Websocket Test - temporary
# ============================================================================

@app.post("/test/setup-call/{call_id}")
async def setup_test_call(call_id: str, phone_number: str):
    """
    Setup a test call context without actually making a Vonage call
    For testing WebSocket + Deepgram integration
    """
    from app.services.appointment_agent import AppointmentAgent
    from app.webhooks.websocket_events import call_contexts

    # Gather context
    context = await AppointmentAgent.get_call_context(phone_number)

    if not context['success']:
        return JSONResponse(content={
            "status": "error",
            "message": context.get('error')
        }, status_code=404)

    # Store context
    call_contexts[call_id] = context

    return JSONResponse(content={
        "status": "success",
        "message": f"Test call context created for {call_id}",
        "context": {
            "patient_name": context.get('patient_name'),
            "appointments": len(context.get('appointments', []))
        }
    })



# ============================================================================
# WEBHOOK ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "ok",
        "app": "Vonage Branded Calling",
        "version": "2.0.0"
    }

@app.get('/_/health')
async def health():
    return 'OK'


@app.websocket("/ws/voice/{call_id}")
async def websocket_endpoint(websocket: WebSocket, call_id: str):
    """
    WebSocket endpoint for voice calls
    """
    await handle_voice_websocket(websocket, call_id)



@app.post("/webhooks/sms/inbound")
async def inbound_sms(sms: InboundSMSEvent):
    """
    Handle inbound SMS and trigger outbound appointment reminder call
    """
    from_number = sms.from_

    logger.info(f"Received inbound SMS from: {from_number}")
    logger.info(f"Message text: {sms.text}")

    # Gather context for the call
    context = await AppointmentAgent.get_call_context(from_number)

    if not context['success']:
        return JSONResponse(content={
            "status": "error",
            "message": context.get('error', 'Failed to gather patient info')
        }, status_code=404)

    # Generate unique call ID (correlation_id)
    correlation_id = call_tracker.start_auth_flow(from_number)

    # Store context for WebSocket handler (keyed by correlation_id, not phone number)
    call_contexts[correlation_id] = context

    # Initiate the call with proper signature
    call_uuid = make_call(from_number, correlation_id)

    if call_uuid:
        return JSONResponse(content={
            "status": "success",
            "message": f"Appointment reminder call initiated to {from_number}",
            "call_uuid": call_uuid,
            "correlation_id": correlation_id
        })

    return JSONResponse(content={
        "status": "error",
        "message": "Failed to initiate call"
    }, status_code=500)



@app.post("/webhooks/voice/event")
async def event_webhook(request: Request):
    """
    Handle call events including Advanced Machine Detection results
    """
    data = await request.json()
    status = data.get('status')
    conversation_uuid = data.get("conversation_uuid", "unknown")

    logger.info(f'Event webhook: status={status}, conversation={conversation_uuid}')

    # Record this event in our call tracker
    call_tracker.record_vonage_event(conversation_uuid, data)

    # Default response for other event types
    return JSONResponse(content={'status': 'success'}, status_code=200)

# ============================================================================
# APPLICATION STARTUP
# ============================================================================

if __name__ == "__main__":
    # Run the FastAPI application
    # VCR will handle this when deployed, but this allows local testing
    port = int(VCR_PORT)
    logger.info(f"Starting server on port {port}")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )