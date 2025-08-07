# Git Service API

A simplified FastAPI service for executing git commands via WebSocket.

## Installation

```bash
pip install -r requirements.txt
```

## Running the Service

```bash
python app.py
```

The API will be available at `http://localhost:8000`

## Endpoints

### 1. Health Check
**GET** `/health`

Response:
```json
{
  "running": true
}
```

### 2. Status
**GET** `/status`

Response:
```json
{
  "status": "running",
  "git_commit_hash": "abc123..."
}
```

### 3. Git Status
**GET** `/git/status`

Response:
```json
{
  "stdout": "On branch main...",
  "stderr": "",
  "return_code": 0,
  "git_commit_hash": "abc123..."
}
```

### 4. Raw Logs
**POST** `/logs/raw`

Send:
```json
{
  "data": {
    "timestamp": "2025-01-05T10:00:00Z",
    "level": "info", 
    "message": "Log entry"
  }
}
```

### 5. WebSocket Command Execution
**WebSocket** `/ws/execute`

Connect to the WebSocket and send commands:

Send:
```json
{
  "command": "git status"
}
```

Receive:
```json
{
  "command": "git status",
  "stdout": "On branch main...",
  "stderr": "",
  "return_code": 0
}
```

## Features

- **Simple**: No session management required
- **Direct**: Send commands directly via WebSocket
- **Real-time**: Get immediate command execution results
- **Clean**: Minimal API surface with clear responses

## Example Usage

```python
import asyncio
import websockets
import json

async def execute_command():
    async with websockets.connect("ws://localhost:8000/ws/execute") as websocket:
        # Send command
        await websocket.send(json.dumps({"command": "git status"}))
        
        # Get result
        response = await websocket.recv()
        result = json.loads(response)
        print(f"Output: {result['stdout']}")

asyncio.run(execute_command())
```

## Interactive API Documentation

Visit `http://localhost:8000/docs` for the interactive Swagger UI documentation.