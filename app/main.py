"""
Vonage Cloud Runtime Outbound Calling App with FastAPI

Simplified version focused on:
- Outbound call automation with branded calling
- Advanced Machine Detection (AMD)
- Patient Appointment Management
- FastAPI webhooks for VCR deployment

Built with Vonage SDK v4, FastAPI, and Python 3.12+
Deployed via Vonage Cloud Runtime
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
from first_orion import get_auth_token, send_push_notification
from call_tracker import call_tracker
from fastapi_requests.message import InboundMessage

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
    title="Vonage Branded Calling with IVR Survey",
    version="2.0.0",
    description="Branded calling demo with 3-question survey"
)

# In-memory survey state (VCR instances are ephemeral, so no persistent storage)
survey_responses = {}


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
                    'action': 'record',
                    'eventUrl': [get_webhook_url('recording')],
                    'split': 'conversation',
                    'channels': 2,
                    'format': 'wav'
                }
            ],
            advanced_machine_detection={
                'behavior': 'continue',
                'mode': 'default',
                'beep_timeout': 90
            },
            event_url=[get_webhook_url('event')],
            event_method='POST'
        )

        response = vonage.voice.create_call(call_request)
        logger.info(f"Call created successfully: {response.uuid}")

        # Record the Vonage call creation in our tracker
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

@app.post("/inbound")
async def inbound_sms(sms: InboundMessage):
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


@app.post("/event")
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

    # Handle AMD results
    if status == 'human':
        logger.info("Human detected, starting IVR flow")
        ncco = [
            {
                'action': 'talk',
                'text': '<speak>This is a test of Vonage Branded Calling. I will be asking you three questions about your experience with this call. You can speak to me or use your phone keypad to respond. Say the word "Go" when you are ready.</speak>',
                'language': 'en-US',
                'style': 2,
                'premium': True,
                'bargeIn': True
            },
            {
                'action': 'input',
                'dtmf': {
                    'maxDigits': 1,
                    'timeOut': 10
                },
                'speech': {
                    'language': 'en-US',
                    'context': ['go', 'yes'],
                    'startTimeout': 10,
                    'maxDuration': 5,
                    'endOnSilence': 1.5
                },
                'type': ['dtmf', 'speech'],
                'eventUrl': [get_webhook_url('dtmf_input')],
                'eventMethod': 'POST'
            }
        ]
        return JSONResponse(content=ncco, status_code=200)

    elif status == 'machine':
        sub_state = data.get('sub_state')
        logger.info(f'Machine detected with substate: {sub_state}')

        if sub_state == 'beep_start':
            logger.info('Beep detected, playing voicemail message')
            ncco = [
                {
                    'action': 'talk',
                    'text': '<speak>This is the TTS that will play out if an answering machine beep is detected.</speak>',
                    'language': 'en-US',
                    'style': 2,
                    'premium': True
                }
            ]
            return JSONResponse(content=ncco, status_code=200)
        else:
            logger.info("Call screener detected")
            ncco = [
                {
                    'action': 'talk',
                    'text': '<speak>This is the call screener TTS playout.</speak>',
                    'language': 'en-US',
                    'style': 2,
                    'premium': True
                }
            ]
            return JSONResponse(content=ncco, status_code=200)

    # Default response for other event types
    return JSONResponse(content={'status': 'success'}, status_code=200)


@app.post("/dtmf_input")
async def dtmf_input_webhook(request: Request):
    """
    Handle DTMF and speech input from callers during IVR interactions
    """
    data = await request.json()
    conversation_uuid = data.get('conversation_uuid', 'unknown')

    logger.info(f"Input received for conversation {conversation_uuid}")

    # Track this event
    if hasattr(call_tracker, 'record_vonage_event'):
        call_tracker.record_vonage_event(conversation_uuid, data)

    # Extract input from DTMF or speech
    dtmf_data = data.get('dtmf', {})
    dtmf = dtmf_data.get('digits') if isinstance(dtmf_data, dict) else dtmf_data

    speech_results = data.get('speech', {}).get('results', [])
    speech_text = ''
    if speech_results and isinstance(speech_results, list) and len(speech_results) > 0:
        if isinstance(speech_results[0], dict):
            text_value = speech_results[0].get('text')
            if text_value is not None:
                speech_text = text_value.strip()

    logger.info(f"DTMF: {dtmf}, Speech: {speech_text}")

    # Initialize survey responses for this conversation if needed
    if conversation_uuid not in survey_responses:
        survey_responses[conversation_uuid] = {}

    responses = survey_responses[conversation_uuid]

    # Determine current step
    if 'saw_vonage_caller_id' in responses:
        current_step = 4  # All questions answered
    elif 'saw_vonage_logo' in responses:
        current_step = 3  # Two questions answered
    elif 'device_type' in responses:
        current_step = 2  # One question answered
    else:
        current_step = 1  # No questions answered yet

    # Process user input
    user_input = None
    if dtmf and isinstance(dtmf_data, dict) and dtmf_data.get('digits'):
        user_input = dtmf
    elif speech_text:
        speech_text_lower = speech_text.lower()
        speech_map = {
            "one": "1", "two": "2",
            "yes": "1", "no": "2",
            "iphone": "1", "android": "2",
            "go": "go"
        }
        user_input = speech_map.get(speech_text_lower, speech_text_lower)

    logger.info(f"User input: {user_input}, Current step: {current_step}")

    # Handle step progression
    next_step = current_step

    if user_input == "go" and current_step == 1:
        next_step = 1
    elif user_input and user_input != "go":
        if current_step == 1:
            responses['device_type'] = user_input
            if hasattr(call_tracker, 'record_survey_response'):
                call_tracker.record_survey_response(conversation_uuid, "device_type", user_input)
            next_step = 2
        elif current_step == 2:
            responses['saw_vonage_logo'] = user_input
            if hasattr(call_tracker, 'record_survey_response'):
                call_tracker.record_survey_response(conversation_uuid, "saw_vonage_logo", user_input)
            next_step = 3
        elif current_step == 3:
            responses['saw_vonage_caller_id'] = user_input
            if hasattr(call_tracker, 'record_survey_response'):
                call_tracker.record_survey_response(conversation_uuid, "saw_vonage_caller_id", user_input)
            next_step = 4

    logger.info(f"Next step: {next_step}")

    # Generate NCCO based on next step
    if next_step == 1:
        ncco = [
            {
                'action': 'talk',
                'text': '<speak>What type of device do you have? You can either say, "iPhone", or press or say 1; you can say "Android", or press or say 2.</speak>',
                'language': 'en-US',
                'style': 2,
                'premium': True,
                'bargeIn': True
            },
            {
                'action': 'input',
                'dtmf': {'maxDigits': 1, 'timeOut': 10},
                'speech': {
                    'language': 'en-US',
                    'context': ['1', '2', 'iphone', 'android'],
                    'startTimeout': 10,
                    'maxDuration': 5,
                    'endOnSilence': 0.4
                },
                'type': ['dtmf', 'speech'],
                'eventUrl': [get_webhook_url('dtmf_input')],
                'eventMethod': 'POST'
            }
        ]
    elif next_step == 2:
        ncco = [
            {
                'action': 'talk',
                'text': '<speak>Did you see the Vonage Logo on your handset when I called you? Press or say 1 for yes, press or say 2 for no.</speak>',
                'language': 'en-US',
                'style': 2,
                'premium': True,
                'bargeIn': True
            },
            {
                'action': 'input',
                'dtmf': {'maxDigits': 1, 'timeOut': 10},
                'speech': {
                    'language': 'en-US',
                    'context': ['1', '2', 'yes', 'no'],
                    'startTimeout': 10,
                    'maxDuration': 5,
                    'endOnSilence': 1.5
                },
                'type': ['dtmf', 'speech'],
                'eventUrl': [get_webhook_url('dtmf_input')],
                'eventMethod': 'POST'
            }
        ]
    elif next_step == 3:
        ncco = [
            {
                'action': 'talk',
                'text': '<speak>Did you see the Vonage caller name on your handset when I called you? Press or say 1 for yes, press or say 2 for no.</speak>',
                'language': 'en-US',
                'style': 2,
                'premium': True,
                'bargeIn': True
            },
            {
                'action': 'input',
                'dtmf': {'maxDigits': 1, 'timeOut': 10},
                'speech': {
                    'language': 'en-US',
                    'context': ['1', '2', 'yes', 'no'],
                    'startTimeout': 10,
                    'maxDuration': 5,
                    'endOnSilence': 1.5
                },
                'type': ['dtmf', 'speech'],
                'eventUrl': [get_webhook_url('dtmf_input')],
                'eventMethod': 'POST'
            }
        ]
    elif next_step == 4:
        logger.info(f"Survey completed for conversation {conversation_uuid}")
        ncco = [
            {
                'action': 'talk',
                'text': '<speak>Thank you for your responses. Tim Dentry thanks you for your input. Goodbye!</speak>',
                'language': 'en-US',
                'style': 2,
                'premium': True
            }
        ]

    return JSONResponse(content=ncco, status_code=200)


@app.post("/recording")
async def recording_webhook(request: Request):
    """
    Handle recording completion notifications
    Note: Recording download is optional for demo purposes
    """
    data = await request.json()
    recording_url = data.get('recording_url')
    conversation_uuid = data.get('conversation_uuid', 'unknown')

    logger.info(f"Recording available for conversation {conversation_uuid}")
    logger.info(f"Recording URL: {recording_url}")

    # For demo purposes, we're just logging the URL
    # In production, you might want to download and store these

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