# app/services/voice.py
"""
Vonage Voice API service
Handles outbound call initiation
"""

import logging
from typing import Optional
from vonage import Vonage, Auth
from vonage_voice import CreateCallRequest, Phone, ToPhone
from vonage_http_client import AuthenticationError, HttpRequestError
from dotenv import load_dotenv
import os
load_dotenv()



from app.branded_calling.first_orion import get_auth_token, send_push_notification
from app.telemetry.call_tracker import call_tracker

logger = logging.getLogger(__name__)

# Environment variables
VONAGE_APPLICATION_ID = os.environ.get("VCR_API_APPLICATION_ID")
VONAGE_PRIVATE_KEY = os.environ.get("VONAGE_APPLICATION_PRIVATE_KEY")
VONAGE_NUMBER = os.environ.get("VONAGE_NUMBER")
logger.info(f"Loaded Vonage Number {VONAGE_NUMBER}")
WEBHOOK_BASE_URL = os.environ.get("VCR_INSTANCE_PUBLIC_URL") or os.environ.get("WEBHOOK_BASE_URL")


# Initialize Vonage client
if VONAGE_PRIVATE_KEY:
    if os.path.isfile(VONAGE_PRIVATE_KEY):
        auth = Auth(application_id=VONAGE_APPLICATION_ID, private_key=VONAGE_PRIVATE_KEY)
    else:
        auth = Auth(application_id=VONAGE_APPLICATION_ID, private_key=VONAGE_PRIVATE_KEY)
else:
    raise ValueError("No private key found in environment variables")

vonage = Vonage(auth)


# app/services/voice.py

def get_webhook_url(endpoint: str) -> str:
    """Construct full webhook URL"""
    base_url = WEBHOOK_BASE_URL.rstrip('/')
    endpoint = endpoint.lstrip('/')  # Strip leading slash

    # For WebSocket endpoints, convert https:// to wss://
    if endpoint.startswith('ws/'):
        base_url = base_url.replace('https://', 'wss://').replace('http://', 'ws://')

    full_url = f"{base_url}/{endpoint}"
    logger.debug(f"Webhook URL: {full_url}")
    return full_url

def make_call(to_number: str, correlation_id: str) -> Optional[str]:
    """
    Initiate branded outbound call with WebSocket connection to Deepgram Flux

    Args:
        to_number: Destination phone number
        correlation_id: Unique ID for tracking this call

    Returns:
        Call UUID if successful, None otherwise
    """
    logger.info(f"Initiating call to {to_number} with correlation_id {correlation_id}")


    # First Orion branded calling
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

    # Create the call with WebSocket connection to Flux AI
    try:
        ncco = [
            {
                "action": "connect",
                "from_": VONAGE_NUMBER,
                "endpoint": [
                    {
                        "type": "websocket",
                        "uri": get_webhook_url(f'ws/voice/{correlation_id}'),
                        "content-type": "audio/l16;rate=16000",
                        'headers': {
                            'source': 'flux'
                        }

                    }
                ]
            }
        ]

        call_request = CreateCallRequest(
            ncco=ncco,
            to=[ToPhone(number=to_number)],  # Use ToPhone class
            from_=Phone(number=VONAGE_NUMBER),  # Use Phone class
            ringing_timer=60,
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