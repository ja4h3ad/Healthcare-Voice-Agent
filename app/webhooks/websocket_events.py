# app/webhooks/websocket_events.py
"""
WebSocket handler - bridges Vonage Voice and Deepgram Voice Agent
"""

import asyncio
import json
import logging
import base64
from fastapi import WebSocket, WebSocketDisconnect

from app.services.deepgram_flux import DeepgramVoiceAgent
from app.services.appointment_agent import AppointmentAgent

logger = logging.getLogger(__name__)

# In-memory cache for call contexts
call_contexts = {}


async def handle_voice_websocket(websocket: WebSocket, call_id: str):
    """
    Handle WebSocket connection for a voice call
    Bridges audio between Vonage and Deepgram Voice Agent

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

    # Initialize Deepgram Voice Agent
    agent = DeepgramVoiceAgent(
        system_prompt=context['system_prompt'],
        functions=context['functions'],
        function_handler=AppointmentAgent.execute_function,
        voice="aura-asteria-en"  # Choose your preferred voice
    )

    try:
        # Connect to Deepgram Voice Agent
        await agent.connect()
        logger.info(f"Deepgram Voice Agent connected for call {call_id}")

        # Track if call is active
        call_active = True

        async def vonage_to_deepgram():
            """Forward audio from Vonage to Deepgram"""
            nonlocal call_active
            try:
                async for message in websocket.iter_text():
                    if not call_active:
                        break

                    try:
                        data = json.loads(message)
                        event = data.get('event')

                        if event == 'media':
                            # Extract and decode audio
                            audio_b64 = data.get('media', {}).get('payload', '')
                            if audio_b64:
                                audio_bytes = base64.b64decode(audio_b64)
                                await agent.send_audio(audio_bytes)

                        elif event == 'start':
                            logger.info(f"Call started: {call_id}")
                            stream_sid = data.get('start', {}).get('streamSid')
                            logger.debug(f"Stream SID: {stream_sid}")

                        elif event == 'stop':
                            logger.info(f"Call stopped: {call_id}")
                            call_active = False
                            break

                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON from Vonage: {message}")

            except WebSocketDisconnect:
                logger.info(f"Vonage WebSocket disconnected for {call_id}")
                call_active = False
            except Exception as e:
                logger.error(f"Error in vonage_to_deepgram: {str(e)}")
                call_active = False

        async def deepgram_to_vonage():
            """Forward audio and handle events from Deepgram to Vonage"""
            nonlocal call_active
            try:
                async for message in agent.receive_messages():
                    if not call_active:
                        break

                    if message.get('type') == 'audio':
                        # Send audio back to Vonage
                        audio_b64 = base64.b64encode(message['data']).decode('utf-8')
                        await websocket.send_json({
                            'event': 'media',
                            'media': {
                                'payload': audio_b64
                            }
                        })

                    elif message.get('type') == 'UserStartedSpeaking':
                        logger.debug("User started speaking")

                    elif message.get('type') == 'AgentStartedSpeaking':
                        logger.debug("Agent started speaking")

                    elif message.get('type') == 'AgentAudioDone':
                        logger.debug("Agent finished speaking")

                    elif message.get('type') == 'ConversationText':
                        # Log transcript for debugging
                        role = message.get('role')
                        content = message.get('content')
                        logger.info(f"Transcript [{role}]: {content}")

            except Exception as e:
                logger.error(f"Error in deepgram_to_vonage: {str(e)}")
                call_active = False

        # Run both streams concurrently
        await asyncio.gather(
            vonage_to_deepgram(),
            deepgram_to_vonage(),
            return_exceptions=True
        )

    except Exception as e:
        logger.error(f"WebSocket error for call {call_id}: {str(e)}")

    finally:
        # Cleanup
        await agent.disconnect()

        # Close Vonage WebSocket if still open
        try:
            await websocket.close()
        except:
            pass

        # Remove context from cache
        if call_id in call_contexts:
            del call_contexts[call_id]

        logger.info(f"WebSocket closed for call {call_id}")