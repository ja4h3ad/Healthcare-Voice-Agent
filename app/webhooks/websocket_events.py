# app/webhooks/websocket_events.py
"""
WebSocket handler - bridges Vonage Voice and Deepgram Flux
"""

import asyncio
import json
import logging
import base64
from fastapi import WebSocket, WebSocketDisconnect

from app.services.deepgram_flux import DeepgramFluxClient
from app.services.appointment_agent import AppointmentReminderAgent

logger = logging.getLogger(__name__)

# In-memory cache for call contexts (use Redis in production)
call_contexts = {}


async def handle_voice_websocket(websocket: WebSocket, call_id: str):
    """
    Handle WebSocket connection for a voice call
    Bridges audio between Vonage and Deepgram Flux

    Args:
        websocket: FastAPI WebSocket connection (from Vonage)
        call_id: Unique identifier for this call
    """
    await websocket.accept()
    logger.info(f"WebSocket connected for call {call_id}")

    # Get context for this call
    context = call_contexts.get(call_id)
    if not context or not context.get('success'):
        logger.error(f"No valid context found for call {call_id}")
        await websocket.close(code=1008, reason="No call context")
        return

    # Initialize Deepgram Flux
    flux_client = DeepgramFluxClient(
        system_prompt=context['system_prompt'],
        agent_config={'functions': context['functions']}
    )

    try:
        # Connect to Deepgram Flux
        await flux_client.connect()
        logger.info(f"Flux connected for call {call_id}")

        # Create concurrent tasks for bidirectional streaming
        async def vonage_to_flux():
            """Forward audio from Vonage to Flux"""
            try:
                async for message in websocket.iter_text():
                    # Vonage sends JSON messages with audio data
                    data = json.loads(message)

                    if data.get('event') == 'media':
                        # Extract audio payload (base64 encoded)
                        audio_b64 = data.get('media', {}).get('payload', '')
                        if audio_b64:
                            audio_bytes = base64.b64decode(audio_b64)
                            await flux_client.send_audio(audio_bytes)

                    elif data.get('event') == 'start':
                        logger.info(f"Call started: {call_id}")

                    elif data.get('event') == 'stop':
                        logger.info(f"Call stopped: {call_id}")
                        break

            except WebSocketDisconnect:
                logger.info(f"Vonage WebSocket disconnected for {call_id}")
            except Exception as e:
                logger.error(f"Error in vonage_to_flux: {str(e)}")

        async def flux_to_vonage():
            """Forward audio and handle events from Flux to Vonage"""
            try:
                async for message in flux_client.receive_messages():
                    if message['type'] == 'audio':
                        # Send audio back to Vonage
                        audio_b64 = base64.b64encode(message['data']).decode('utf-8')
                        await websocket.send_json({
                            'event': 'media',
                            'media': {
                                'payload': audio_b64
                            }
                        })

                    elif message['type'] == 'FunctionCall':
                        # Handle function call from Flux
                        function_name = message.get('function')
                        arguments = message.get('arguments', {})
                        function_id = message.get('function_call_id')

                        logger.info(f"Function called: {function_name}")

                        # Execute the function
                        result = await AppointmentReminderAgent.execute_function(
                            function_name,
                            arguments
                        )

                        # Send result back to Flux
                        await flux_client.send_function_result(function_id, result)

                    elif message['type'] == 'UserStartedSpeaking':
                        logger.debug("User started speaking")

                    elif message['type'] == 'AgentStartedSpeaking':
                        logger.debug("Agent started speaking")

            except Exception as e:
                logger.error(f"Error in flux_to_vonage: {str(e)}")

        # Run both streams concurrently
        await asyncio.gather(
            vonage_to_flux(),
            flux_to_vonage()
        )

    except Exception as e:
        logger.error(f"WebSocket error for call {call_id}: {str(e)}")

    finally:
        # Cleanup
        await flux_client.disconnect()
        await websocket.close()

        # Remove context from cache
        if call_id in call_contexts:
            del call_contexts[call_id]

        logger.info(f"WebSocket closed for call {call_id}")