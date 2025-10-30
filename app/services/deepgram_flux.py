# app/services/deepgram_flux.py
"""
Deepgram Flux AI Agent Client
Handles WebSocket connection to Deepgram's conversational AI
"""

import asyncio
import json
import logging
import websockets
from typing import Optional, Dict, Any, AsyncIterator
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY")
DEEPGRAM_FLUX_URL = "wss://agent.deepgram.com/agent"  # Check Deepgram docs for actual URL


class DeepgramFluxClient:
    """
    Client for Deepgram Flux conversational AI
    Handles audio streaming and function calling
    """

    def __init__(self, system_prompt: str, agent_config: Optional[Dict[str, Any]] = None):
        """
        Initialize Flux client

        Args:
            system_prompt: Instructions for the AI agent
            agent_config: Optional configuration (voice, language, etc.)
        """
        self.system_prompt = system_prompt
        self.agent_config = agent_config or {}
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.is_connected = False

    async def connect(self):
        """
        Establish WebSocket connection to Deepgram Flux
        """
        try:
            # Build connection URL with API key
            url = f"{DEEPGRAM_FLUX_URL}?token={DEEPGRAM_API_KEY}"

            self.websocket = await websockets.connect(url)
            self.is_connected = True

            # Send initial configuration
            config_message = {
                "type": "Configure",
                "audio": {
                    "input": {
                        "encoding": "linear16",
                        "sample_rate": 16000
                    },
                    "output": {
                        "encoding": "linear16",
                        "sample_rate": 16000
                    }
                },
                "agent": {
                    "listen": {
                        "model": "nova-2"
                    },
                    "speak": {
                        "model": "aura-asteria-en"  # or your preferred voice
                    },
                    "think": {
                        "provider": {
                            "type": "anthropic"  # or "open_ai"
                        },
                        "model": "claude-3-5-sonnet-20241022",
                        "instructions": self.system_prompt,
                        "functions": self.agent_config.get('functions', [])
                    }
                }
            }

            await self.websocket.send(json.dumps(config_message))
            logger.info("Connected to Deepgram Flux")

        except Exception as e:
            logger.error(f"Failed to connect to Deepgram Flux: {str(e)}")
            self.is_connected = False
            raise

    async def disconnect(self):
        """
        Close WebSocket connection
        """
        if self.websocket:
            await self.websocket.close()
            self.is_connected = False
            logger.info("Disconnected from Deepgram Flux")

    async def send_audio(self, audio_data: bytes):
        """
        Send audio data to Flux (from Vonage call)

        Args:
            audio_data: Raw audio bytes (linear16, 16kHz)
        """
        if not self.is_connected or not self.websocket:
            logger.warning("Cannot send audio - not connected")
            return

        try:
            await self.websocket.send(audio_data)
        except Exception as e:
            logger.error(f"Error sending audio to Flux: {str(e)}")

    async def receive_messages(self) -> AsyncIterator[Dict[str, Any]]:
        """
        Receive messages from Flux (audio, function calls, etc.)

        Yields:
            Parsed message dictionaries
        """
        if not self.is_connected or not self.websocket:
            logger.warning("Cannot receive - not connected")
            return

        try:
            async for message in self.websocket:
                if isinstance(message, bytes):
                    # Audio data
                    yield {
                        "type": "audio",
                        "data": message
                    }
                else:
                    # JSON message (function calls, events, etc.)
                    try:
                        parsed = json.loads(message)
                        yield parsed
                    except json.JSONDecodeError:
                        logger.warning(f"Received non-JSON text message: {message}")

        except websockets.exceptions.ConnectionClosed:
            logger.info("Flux connection closed")
            self.is_connected = False
        except Exception as e:
            logger.error(f"Error receiving from Flux: {str(e)}")

    async def send_function_result(self, function_id: str, result: Any):
        """
        Send function execution result back to Flux

        Args:
            function_id: ID of the function call
            result: Result to send back
        """
        if not self.is_connected or not self.websocket:
            logger.warning("Cannot send function result - not connected")
            return

        message = {
            "type": "FunctionCallResult",
            "function_call_id": function_id,
            "result": result
        }

        try:
            await self.websocket.send(json.dumps(message))
            logger.info(f"Sent function result for {function_id}")
        except Exception as e:
            logger.error(f"Error sending function result: {str(e)}")