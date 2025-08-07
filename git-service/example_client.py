#!/usr/bin/env python3
"""
Example client to test the Git Service API endpoints
"""

import requests
import json
import asyncio
import websockets

# API Base URL
BASE_URL = "http://localhost:8000"

def test_session_endpoints():
    """Test the session start and end endpoints"""
    print("🚀 Testing Session Endpoints...")
    
    # Start session
    start_response = requests.post(
        f"{BASE_URL}/session/start",
        json={"user_prompt": "Fix the authentication bug"}
    )
    print("📝 Session Start Response:")
    print(json.dumps(start_response.json(), indent=2, default=str))
    
    session_id = start_response.json()["session_id"]
    print(f"Session ID: {session_id}")
    
    # End session
    end_response = requests.post(
        f"{BASE_URL}/session/end",
        json={
            "session_id": session_id,
            "final_output": "Authentication bug has been fixed successfully",
            "status": "success",
            "metadata": {
                "tool_calls": 8,
                "todos_completed": 5,
                "files_modified": ["auth.py", "login.py"]
            }
        }
    )
    print("\n✅ Session End Response:")
    print(json.dumps(end_response.json(), indent=2, default=str))

    return session_id

async def test_websocket(session_id: str):
    """Test the WebSocket command execution - client receives and executes commands"""
    print("\n🔌 Testing WebSocket Command Execution...")
    
    try:
        async with websockets.connect("ws://localhost:8000/ws/execute") as websocket:
            print("✅ Connected to WebSocket server")
            print("🎧 Listening for commands from server...")
            
            # send message to server
            await websocket.send(json.dumps({
                "session_id": session_id,
                "message": "done"
            }))

            # receive message from server
            message = await websocket.recv()
            print(f"🎧 Received message from server: {message}")
            
    except Exception as e:
        print(f"❌ WebSocket error: {e}")

if __name__ == "__main__":
    print("🧪 Git Service API Test Client")
    print("=" * 40)
    
    # Test HTTP endpoints
    try:
        session_id = test_session_endpoints()
    except Exception as e:
        print(f"❌ HTTP endpoint error: {e}")
    
    # Test WebSocket
    try:
        asyncio.run(test_websocket(session_id))
    except Exception as e:
        print(f"❌ WebSocket test error: {e}")
    
    print("\n✨ Testing completed!")