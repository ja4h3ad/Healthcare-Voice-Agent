# test_websocket.py - updated with more logging

import asyncio
import websockets
import json


async def test_websocket():
    call_id = "test_call_12345"
    uri = f"ws://localhost:3000/ws/voice/{call_id}"

    print(f"Connecting to {uri}...")

    try:
        async with websockets.connect(uri) as websocket:
            print("Connected!")

            # Simulate Vonage's "start" event
            start_event = {
                "event": "start",
                "start": {
                    "streamSid": "test-stream-123"
                }
            }
            print(f"Sending start event: {start_event}")
            await websocket.send(json.dumps(start_event))
            print("Start event sent")

            # Listen for responses with timeout
            try:
                async with asyncio.timeout(10):  # 10 second timeout
                    async for message in websocket:
                        print(f"📨 Received message")
                        data = json.loads(message)
                        print(f"   Event type: {data.get('event', 'unknown')}")
                        print(f"   Full data: {data}")

                        if data.get('event') == 'media':
                            print("Received audio from agent!")
                            break
            except TimeoutError:
                print("⏱️ Timeout waiting for response")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_websocket())