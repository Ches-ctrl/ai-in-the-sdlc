# AI in the SDLC

A hackathon project exploring AI integration in the Software Development Lifecycle.

## Structure

- `/electron-app` - Git observability Electron application
- Other folders - Additional hackathon components

## Getting Started

### Electron App

```bash
cd electron-app
npm install
npm start
```

### Backend

```
curl -X POST "https://api.example.com/v1/session/start" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -d '{
    "session_id": "sess_abc123def456",
    "user_prompt": "Help me create a data analysis pipeline for customer behavior",
    "time_stamp": "2025-08-07T11:05:43.000Z",
    "git_commit_info": {
      "hash": "a1b2c3d4e5f6789012345678901234567890abcd",
      "branch": "main",
      "message": "Add session management endpoints",
      "author": "developer@example.com"
    }
  }'
```

```
curl -X POST "https://api.example.com/v1/session/end" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -d '{
    "session_id": "sess_abc123def456",
    "final_output": "Successfully created data analysis pipeline with 3 visualizations and exported results to CSV",
    "status": "success",
    "meta_data": {
      "tool_calls": [
        "code_executor",
        "Google_CreateSpreadsheet",
        "text_to_image"
      ],
      "todos": [
        "Schedule automated pipeline runs",
        "Set up data quality alerts"
      ],
      "execution_time_ms": 15420,
      "tokens_used": 2847,
      "files_generated": [
        "analysis_results.csv",
        "visualization_chart.png"
      ],
      "error_count": 0,
      "warning_count": 1
    }
  }'
```

## Features

- Clean Electron app with React + Tailwind + shadcn/ui
- Git repository observability interface
- Modern dark theme design
