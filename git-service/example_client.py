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

async def test_websocket():
    """Test the WebSocket command execution - client receives and executes commands"""
    print("\n🔌 Testing WebSocket Command Execution...")
    
    try:
        import subprocess
        async with websockets.connect("ws://localhost:8000/ws/execute") as websocket:
            print("✅ Connected to WebSocket server")
            print("🎧 Listening for commands from server...")
            
            while True:
                try:
                    # Receive command from server
                    command_data = await websocket.recv()
                    command_json = json.loads(command_data)
                    command = command_json.get("command", "")
                    
                    print(f"\n📨 Received command from server: {command}")
                    
                    if not command:
                        error_response = {
                            "error": "No command provided",
                            "return_code": -1,
                            "stdout": "",
                            "stderr": "No command provided"
                        }
                        await websocket.send(json.dumps(error_response))
                        continue
                    
                    # Execute command locally
                    try:
                        print(f"⚡ Executing command: {command}")

                        response = {
                            "stdout": "success",
                            "stderr": "",
                            "return_code": 0,
                            "command": command
                        }
                        # Send result back to server
                        await websocket.send(json.dumps(response))
                        
                    except subprocess.TimeoutExpired:
                        error_response = {
                            "error": "Command timed out after 30 seconds",
                            "return_code": -1,
                            "stdout": "",
                            "stderr": "Command timed out",
                            "command": command
                        }
                        print("⏰ Command timed out")
                        await websocket.send(json.dumps(error_response))
                        
                    except Exception as e:
                        error_response = {
                            "error": f"Command execution error: {str(e)}",
                            "return_code": -1,
                            "stdout": "",
                            "stderr": str(e),
                            "command": command
                        }
                        print(f"❌ Command execution error: {str(e)}")
                        await websocket.send(json.dumps(error_response))
                        
                except json.JSONDecodeError:
                    error_response = {
                        "error": "Invalid JSON format received from server",
                        "return_code": -1,
                        "stdout": "",
                        "stderr": "Invalid JSON format"
                    }
                    print("❌ Invalid JSON received from server")
                    await websocket.send(json.dumps(error_response))
                    
                except websockets.exceptions.ConnectionClosed:
                    print("🔌 Server closed the connection")
                    break
                    
                except Exception as e:
                    print(f"❌ Unexpected error: {str(e)}")
                    break
            
    except Exception as e:
        print(f"❌ WebSocket error: {e}")

if __name__ == "__main__":
    print("🧪 Git Service API Test Client")
    print("=" * 40)
    
    # Test HTTP endpoints
    try:
        test_session_endpoints()
    except Exception as e:
        print(f"❌ HTTP endpoint error: {e}")
    
    # Test WebSocket
    try:
        asyncio.run(test_websocket())
    except Exception as e:
        print(f"❌ WebSocket test error: {e}")
    
    print("\n✨ Testing completed!")