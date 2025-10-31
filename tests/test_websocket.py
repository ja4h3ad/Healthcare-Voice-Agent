# test_websocket.py
"""
Test WebSocket connection to simulate Vonage calling our endpoint
"""

import asyncio
import websockets
import json
import base64
import wave


async def test_websocket():
    # Simulate a call_id (correlation_id)
    call_id = "test_call_12345"

    # Connect to your WebSocket endpoint
    uri = f"ws://localhost:3000/ws/voice/{call_id}"

    print(f"Connecting to {uri}...")

    async with websockets.connect(uri) as websocket:
        print("Connected!")

        # Simulate Vonage's "start" event
        start_event = {
            "event": "start",
            "start": {
                "streamSid": "test-stream-123"
            }
        }
        await websocket.send(json.dumps(start_event))
        print("Sent start event")

        # Listen for responses
        async for message in websocket:
            data = json.loads(message)
            print(f"Received: {data.get('event', 'unknown event')}")

            # If we get audio back, we know Deepgram is working
            if data.get('event') == 'media':
                print("✅ Received audio from agent!")
                break


if __name__ == "__main__":
    asyncio.run(test_websocket())