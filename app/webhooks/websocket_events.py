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
    """
    await websocket.accept()
    logger.info(f"WebSocket connected for call {call_id}")

    context = call_contexts.get(call_id)
    if not context or not context.get('success'):
        logger.error(f"No valid context found for call {call_id}")
        await websocket.close(code=1008, reason="No call context")
        return

    logger.info(f"Context for {call_id}:")
    logger.info(f"  Patient: {context.get('patient_name')}")
    logger.info(f"  Appointments: {len(context.get('appointments', []))}")
    logger.info(f"  Greeting: {context.get('greeting', 'None')}")

    # Initialize Deepgram Voice Agent
    agent = DeepgramVoiceAgent(
        system_prompt=context['system_prompt'],
        functions=context['functions'],
        function_handler=AppointmentAgent.execute_function,
        greeting=context.get('greeting'),
        voice_model="aura-2-thalia-en",
        llm_model="claude-sonnet-4-20250514"
    )

    try:
        await agent.connect()
        logger.info(f"Deepgram Voice Agent connected for call {call_id}")
    except Exception as e:
        logger.error(f"Failed to connect to Deepgram: {e}")
        await websocket.close(code=1011, reason="Deepgram connection failed")
        return

    call_active = True

    # Audio buffer for pacing output to Vonage
    audio_buffer = bytearray()
    buffer_index = 0

    async def vonage_to_deepgram():
        """Forward audio from Vonage to Deepgram"""
        nonlocal call_active
        logger.info(f"Starting vonage_to_deepgram loop for {call_id}")

        try:
            while call_active:
                try:
                    message = await websocket.receive()

                    if "text" in message:
                        data = json.loads(message["text"])
                        event = data.get('event')

                        if event == 'media':
                            audio_b64 = data.get('media', {}).get('payload', '')
                            if audio_b64:
                                audio_bytes = base64.b64decode(audio_b64)
                                await agent.send_audio(audio_bytes)

                        elif event == 'start':
                            logger.info(f"Call started: {call_id}")

                        elif event == 'stop':
                            logger.info(f"Call stopped: {call_id}")
                            call_active = False
                            break

                        elif event == 'websocket:connected':
                            logger.info("Vonage WebSocket connected")

                    elif "bytes" in message:
                        audio_bytes = message["bytes"]
                        await agent.send_audio(audio_bytes)

                except RuntimeError as e:
                    if "disconnect message has been received" in str(e):
                        logger.info("Vonage disconnected")
                        call_active = False
                        break
                    raise
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {e}")
                except Exception as e:
                    logger.error(f"Error processing message: {e}")

        except Exception as e:
            logger.error(f"Error in vonage_to_deepgram: {e}")
            call_active = False

        logger.info(f"vonage_to_deepgram ended")

    async def deepgram_to_vonage():
        """Forward audio from Deepgram to Vonage with buffering"""
        nonlocal call_active, audio_buffer
        logger.info(f"Starting deepgram_to_vonage loop for {call_id}")
        settings_applied = False

        try:
            async for message in agent.receive_messages():
                if not call_active:
                    break

                msg_type = message.get('type')

                if msg_type == 'SettingsApplied' and not settings_applied:
                    settings_applied = True
                    logger.info("Settings applied, sending initial greeting trigger")
                    await agent.websocket.send(json.dumps({
                        "type": "InjectUserMessage",
                        "content": "hello"
                    }))

                if msg_type == 'audio':
                    # Buffer audio from Deepgram
                    audio_data = message.get('data')
                    if audio_data:
                        audio_buffer.extend(audio_data)

                elif msg_type == 'UserStartedSpeaking':
                    # Barge-in: clear buffer
                    logger.info("User started speaking - clearing audio buffer")
                    audio_buffer.clear()

                elif msg_type not in ['History', 'ConversationText']:
                    logger.info(f"Deepgram event: {msg_type}")
                    if msg_type == 'Error':
                        logger.error(f"Deepgram error: {message}")

        except Exception as e:
            logger.error(f"Error in deepgram_to_vonage: {e}", exc_info=True)
            call_active = False

        logger.info(f"deepgram_to_vonage ended")

    async def stream_to_vonage():
        """Send buffered audio to Vonage at steady rate"""
        nonlocal call_active, audio_buffer, buffer_index
        logger.info("Starting stream_to_vonage timer")

        try:
            while call_active:
                await asyncio.sleep(0.02)  # 20ms timer

                if len(audio_buffer) > buffer_index:
                    # Send 640-byte chunk (20ms of 16kHz linear16 audio)
                    chunk = bytes(audio_buffer[buffer_index:buffer_index + 640])

                    if len(chunk) > 0:
                        await websocket.send_bytes(chunk)
                        buffer_index += 640

                    # Prevent index from growing forever
                    if buffer_index > len(audio_buffer):
                        buffer_index = len(audio_buffer)

        except Exception as e:
            logger.error(f"Error in stream_to_vonage: {e}")
            call_active = False

        logger.info("stream_to_vonage ended")

    # Run all three tasks concurrently
    try:
        logger.info(f"Starting audio bidirectional streaming for {call_id}")
        await asyncio.gather(
            vonage_to_deepgram(),
            deepgram_to_vonage(),
            stream_to_vonage()  # NEW: Timer-based sender
        )
    finally:
        logger.info(f"Cleaning up call {call_id}")
        await agent.disconnect()
        logger.info(f"WebSocket closed for call {call_id}")