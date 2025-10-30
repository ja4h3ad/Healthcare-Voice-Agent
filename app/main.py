"""
Vonage Healthcare Voice Agent with Deepgram Flux AI

Handles:
- SMS-triggered outbound calls
- Appointment reminders via conversational AI
- WebSocket audio streaming for ASR and TTS
"""

from vonage import Vonage, Auth
from vonage_voice import CreateCallRequest
from vonage_http_client import AuthenticationError, HttpRequestError
from dotenv import load_dotenv

# FastAPI and pydantic
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn
from typing import Optional, Dict, Any

import os
from urllib.parse import urljoin
import logging

# Import custom modules
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


def make_call(to_number: str, max_retries: int = 3, initial_delay: int = 1) -> Optional[str]:
    """
    Initiate branded outbound call

    Args:
        to_number: Destination phone number
        max_retries: Maximum retry attempts
        initial_delay: Initial delay between retries

    Returns:
        Call UUID if successful, None otherwise
    """
    # Start a new call tracking flow
    correlation_id = call_tracker.start_auth_flow(to_number)

    # First Orion branded calling - get auth token and send push notification
    token, auth_data = get_auth_token(correlation_id)
    if token:
        logger.info(f"Successfully obtained First Orion auth token")
        success, push_data = send_push_notification(
            correlation_id,
            token,
            VONAGE_NUMBER,
            to_number
        )
        if success:
            logger.info(f"Successfully sent First Orion push notification for {to_number}")
        else:
            logger.warning(f"Failed to send First Orion push notification. Call will proceed unbranded.")
    else:
        logger.warning(f"Failed to get First Orion auth token. Call will proceed unbranded.")

    # Create the call
    try:
        call_request = CreateCallRequest(
            to=[{'type': 'phone', 'number': to_number}],
            from_={'type': 'phone', 'number': VONAGE_NUMBER},
            ringing_timer=60,
            ncco=[
                {
                    'action': 'connect',
                    'endpoint': [
                        {
                            'type': 'websocket',
                            'uri': get_webhook_url(f'ws/voice/{correlation_id}'),
                            'content-type': 'audio/l16;rate=16000'
                        }
                    ]
                }
            ],
            event_url=[get_webhook_url('webhooks/voice/event')],
            event_method='POST'
        )

        response = vonage.voice.create_call(call_request)
        logger.info(f"Call created successfully: {response.uuid}")

        call_tracker.record_vonage_call(correlation_id, response)

        return response.uuid

    except (AuthenticationError, HttpRequestError) as e:
        logger.error(f'Error when calling {to_number}: {str(e)}')
        return None


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

@app.post("/webhooks/sms/inbound")
async def inbound_sms(sms: InboundSMSEvent):
    """
    Handle inbound SMS and trigger outbound branded call
    Uses Pydantic model for validation
    """
    from_number = sms.from_

    logger.info(f"Received inbound SMS from: {from_number}")
    logger.info(f"Message text: {sms.text}")

    call_uuid = make_call(from_number)

    if call_uuid:
        return JSONResponse(content={
            "status": "success",
            "message": f"Call initiated to {from_number}",
            "call_uuid": call_uuid
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