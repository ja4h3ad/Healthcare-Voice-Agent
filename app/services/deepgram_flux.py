# app/services/deepgram_flux.py
"""
Deepgram Voice Agent API Client
Full conversational AI with STT + LLM + TTS built-in
"""

import asyncio
import json
import logging
import websockets
from typing import Optional, Dict, Any, AsyncIterator, Callable, List
import os
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_PASSWORD")
DEEPGRAM_AGENT_URL = "wss://agent.deepgram.com/v1/agent/converse"


class DeepgramVoiceAgent:
    """
    Async client for Deepgram Voice Agent API (STT + LLM + TTS)
    Manages full duplex audio and event flow.
    """

    def __init__(
        self,
        system_prompt: str,
        functions: List[Dict[str, Any]],
        function_handler: Callable[[str, Dict[str, Any]], Any],
        greeting: "Hello, this is Doctor Preston's Office calling.  '",
        voice_model: str = "aura-2-thalia-en",
        llm_model: str = "claude-3-sonnet-20250514",
    ):
        """
        Initialize Voice Agent

        Args:
            system_prompt: Base system prompt or persona for the agent.
            functions: List of function definitions (name, description, parameters).
            function_handler: Async function to execute when the agent calls a function.
            greeting: Optional greeting for the agent to start with.
            voice_model: Deepgram TTS voice model.
            llm_model: LLM model used by the 'think' provider.
        """
        self.system_prompt = system_prompt
        self.functions = functions
        self.function_handler = function_handler
        self.greeting = greeting
        self.voice_model = voice_model
        self.llm_model = llm_model
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.is_connected = False

    # --------------------------------------------------------------------------
    # Connection Lifecycle
    # --------------------------------------------------------------------------



    async def connect(self):
        """Establish WebSocket connection to Deepgram Voice Agent."""
        try:
            headers = {"Authorization": f"Token {DEEPGRAM_API_KEY}"}
            self.websocket = await websockets.connect(
                DEEPGRAM_AGENT_URL,
                extra_headers=headers,
            )
            self.is_connected = True
            logger.info("Connected to Deepgram Voice Agent")

            # app/services/deepgram_flux.py

            config = {
                "type": "Settings",
                "audio": {
                    "input": {
                        "encoding": "linear16",
                        "sample_rate": 16000
                    },
                    "output": {
                        "encoding": "linear16",
                        "sample_rate": 16000,
                        "container": "none"
                    }
                },
                "agent": {
                    "listen": {
                        "provider": {
                            "type": "deepgram",
                            "model": "nova-2"
                        }
                    },
                    "think": {
                        "provider": {
                            "type": "anthropic",
                            "model": self.llm_model
                        },
                        "prompt": self.system_prompt,
                        "functions": self._format_functions()
                    },
                    "speak": {
                        "provider": {
                            "type": "deepgram",
                            "model": self.voice_model
                        }
                    },
                    "greeting": "Hello! This is your medical office calling."  #
                }
            }
            if self.greeting:
                config["agent"]["greeting"] = self.greeting

            logger.info(f"Sending config with {len(self.functions)} functions")
            await self.websocket.send(json.dumps(config))
            logger.info(f"Voice Agent configured with LLM={self.llm_model}, Voice={self.voice_model}")

        except Exception as e:
            logger.error(f"Failed to connect to Deepgram: {str(e)}", exc_info=True)
            self.is_connected = False
            raise


    async def disconnect(self):
        """Close WebSocket connection."""
        if self.websocket:
            await self.websocket.close()
            self.is_connected = False
            logger.info("Disconnected from Deepgram Voice Agent")

    # --------------------------------------------------------------------------
    # Audio Streaming
    # --------------------------------------------------------------------------

    # app/services/deepgram_flux.py

    async def send_audio(self, audio_data: bytes):
        """
        Send raw audio from user (linear16, 16kHz).
        Must be sent as binary WebSocket frame.
        """
        if not self.is_connected or not self.websocket:
            logger.warning("Cannot send audio - not connected")
            return

        try:
            # Send as binary frame (not text/JSON)
            await self.websocket.send(audio_data)  # This sends binary if audio_data is bytes
        except Exception as e:
            logger.error(f"Error sending audio: {str(e)}")
    # --------------------------------------------------------------------------
    # Event Loop and Message Handling
    # --------------------------------------------------------------------------

    # app/services/deepgram_flux.py

    async def receive_messages(self) -> AsyncIterator[Dict[str, Any]]:
        """
        Receive messages from Voice Agent
        """
        if not self.is_connected or not self.websocket:
            logger.warning("Cannot receive - not connected")
            return

        try:
            async for message in self.websocket:
                if isinstance(message, bytes):
                    # Binary audio from Deepgram
                    yield {"type": "audio", "data": message}  # ← This is correct
                else:
                    # JSON messages
                    parsed = json.loads(message)
                    yield parsed  # ← This yields JSON events

        except Exception as e:
            logger.error(f"Error receiving from Voice Agent: {str(e)}")
    # --------------------------------------------------------------------------
    # Function Call Handling
    # --------------------------------------------------------------------------

    async def _handle_function_call(self, message: Dict[str, Any]):
        """Handle an AgentV1FunctionCallRequest message."""
        function_name = message.get("function_name")
        function_id = message.get("function_call_id")
        input_data = message.get("input", {})

        logger.info(f"Function call requested: {function_name}")

        try:
            result = await self.function_handler(function_name, input_data)
            await self.send_function_result(function_id, result)
        except Exception as e:
            logger.error(f"Error executing function '{function_name}': {str(e)}")
            await self.send_function_result(function_id, {"error": str(e)})

    async def send_function_result(self, function_call_id: str, result: Any):
        """
        Send function execution result back to Deepgram.

        Args:
            function_call_id: ID from the AgentV1FunctionCallRequest
            result: Result payload to send back
        """
        if not self.is_connected or not self.websocket:
            logger.warning(" Cannot send function result - not connected")
            return

        message = {
            "type": "AgentV1SendFunctionCallResponse",
            "function_call_id": function_call_id,
            "output": result,
        }

        try:
            await self.websocket.send(json.dumps(message))
            logger.info(f"Sent function result for call {function_call_id}")
        except Exception as e:
            logger.error(f"Error sending function result: {str(e)}")

    # --------------------------------------------------------------------------
    # Helper
    # --------------------------------------------------------------------------

    def _format_functions(self) -> List[Dict[str, Any]]:
        """Format functions for Deepgram Voice Agent API"""
        return [
            {
                "name": f["name"],
                "description": f.get("description", ""),
                "parameters": f.get("parameters", {})
            }
            for f in self.functions
        ]
