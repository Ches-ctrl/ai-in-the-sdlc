# Git Service API

A minimalistic FastAPI service for managing coding sessions and executing git commands.

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

### 1. Start Session
**POST** `/session/start`

```json
{
  "user_prompt": "Fix the login bug"
}
```

Response:
```json
{
  "session_id": "uuid-here",
  "user_prompt": "Fix the login bug",
  "timestamp": "2024-01-01T12:00:00",
  "git_commit_hash": "abc123..."
}
```

### 2. End Session
**POST** `/session/end`

```json
{
  "session_id": "uuid-here",
  "final_output": "Bug fixed successfully",
  "status": "success",
  "metadata": {
    "tool_calls": 5,
    "todos_completed": 3
  }
}
```

### 3. WebSocket Command Execution
**WebSocket** `/ws/execute`

Send:
```json
{
  "command": "git status"
}
```

Receive:
```json
{
  "stdout": "On branch main...",
  "stderr": "",
  "return_code": 0
}
```

## Interactive API Documentation

Visit `http://localhost:8000/docs` for the interactive Swagger UI documentation.