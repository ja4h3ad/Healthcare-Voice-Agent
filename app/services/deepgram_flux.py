# app/services/deepgram_flux.py
"""
Deepgram Voice Agent API Client
Full conversational AI with STT + LLM + TTS built-in
"""

import asyncio
import json
import logging
import websockets
from typing import Optional, Dict, Any, AsyncIterator, Callable
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_PASSWORD")
# Voice Agent API endpoint (check Deepgram docs for latest)
DEEPGRAM_AGENT_URL = "wss://agent.deepgram.com/agent"


class DeepgramVoiceAgent:
    """
    Client for Deepgram Voice Agent API
    Handles full conversational flow: STT + LLM + TTS
    """

    def __init__(
            self,
            system_prompt: str,
            functions: list,
            function_handler: Callable,
            voice: str = "aura-asteria-en"
    ):
        """
        Initialize Voice Agent

        Args:
            system_prompt: Instructions for the AI
            functions: List of function definitions
            function_handler: Async function to execute when agent calls a function
            voice: Deepgram TTS voice model
        """
        self.system_prompt = system_prompt
        self.functions = functions
        self.function_handler = function_handler
        self.voice = voice
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.is_connected = False

    async def connect(self):
        """
        Establish WebSocket connection to Deepgram Voice Agent
        """
        try:
            # Build connection URL with API key
            url = f"{DEEPGRAM_AGENT_URL}?token={DEEPGRAM_API_KEY}"

            self.websocket = await websockets.connect(url)
            self.is_connected = True
            logger.info("Connected to Deepgram Voice Agent")

            # Send configuration for Voice Agent API
            config = {
                "type": "SettingsConfiguration",
                "audio": {
                    "input": {
                        "encoding": "linear16",
                        "sample_rate": 16000
                    },
                    "output": {
                        "encoding": "linear16",
                        "sample_rate": 16000,
                        "container": "none"  # Raw audio
                    }
                },
                "agent": {
                    "listen": {
                        "model": "nova-2"  # Deepgram STT model
                    },
                    "think": {
                        "provider": {
                            "type": "anthropic"
                        },
                        "model": "claude-3-5-sonnet-20241022",
                        "instructions": self.system_prompt,
                        "functions": self.functions
                    },
                    "speak": {
                        "model": self.voice
                    }
                }
            }

            await self.websocket.send(json.dumps(config))
            logger.info("Voice Agent configured")

        except Exception as e:
            logger.error(f"Failed to connect to Deepgram: {str(e)}")
            self.is_connected = False
            raise

    async def disconnect(self):
        """Close WebSocket connection"""
        if self.websocket:
            await self.websocket.close()
            self.is_connected = False
            logger.info("Disconnected from Deepgram Voice Agent")

    async def send_audio(self, audio_data: bytes):
        """
        Send audio from user to Voice Agent

        Args:
            audio_data: Raw audio bytes (linear16, 16kHz)
        """
        if not self.is_connected or not self.websocket:
            logger.warning("Cannot send audio - not connected")
            return

        try:
            await self.websocket.send(audio_data)
        except Exception as e:
            logger.error(f"Error sending audio: {str(e)}")

    async def receive_messages(self) -> AsyncIterator[Dict[str, Any]]:
        """
        Receive messages from Voice Agent
        Yields audio output and function calls
        """
        if not self.is_connected or not self.websocket:
            logger.warning("Cannot receive - not connected")
            return

        try:
            async for message in self.websocket:
                if isinstance(message, bytes):
                    # Audio output from agent (TTS)
                    yield {
                        "type": "audio",
                        "data": message
                    }
                else:
                    # JSON events (function calls, turn events, etc.)
                    try:
                        parsed = json.loads(message)
                        msg_type = parsed.get("type")

                        logger.debug(f"Received event: {msg_type}")

                        # Handle function calls
                        if msg_type == "FunctionCallRequest":
                            function_name = parsed.get("function_name")
                            function_id = parsed.get("function_call_id")
                            input_data = parsed.get("input", {})

                            logger.info(f"Function call: {function_name}")

                            # Execute the function
                            result = await self.function_handler(function_name, input_data)

                            # Send result back to agent
                            await self.send_function_result(function_id, result)

                        # Yield all events for logging/monitoring
                        yield parsed

                    except json.JSONDecodeError:
                        logger.warning(f"Received non-JSON text: {message}")

        except websockets.exceptions.ConnectionClosed:
            logger.info("Voice Agent connection closed")
            self.is_connected = False
        except Exception as e:
            logger.error(f"Error receiving from Voice Agent: {str(e)}")

    async def send_function_result(self, function_call_id: str, result: Any):
        """
        Send function execution result back to Voice Agent

        Args:
            function_call_id: ID from the function call request
            result: Result data to send back
        """
        if not self.is_connected or not self.websocket:
            logger.warning("Cannot send function result - not connected")
            return

        message = {
            "type": "FunctionCallResponse",
            "function_call_id": function_call_id,
            "output": result
        }

        try:
            await self.websocket.send(json.dumps(message))
            logger.info(f"Sent function result for {function_call_id}")
        except Exception as e:
            logger.error(f"Error sending function result: {str(e)}")