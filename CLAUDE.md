# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a hackathon project exploring AI integration in the Software Development Lifecycle (SDLC). The project consists of two main components:

1. **Electron App** (`/electron-app`): A Git observability desktop application built with React, TypeScript, Tailwind CSS, and shadcn/ui.
2. **Git Service** (`/git-service`): A FastAPI backend service for executing git commands via WebSocket.

## Development Commands

### Electron App
```bash
cd electron-app
npm install              # Install dependencies
npm start                # Start development (runs Vite + Electron)
npm run dev              # Start Vite development server only
npm run build            # Build for production
npm run dist             # Build and package application
npm run dist:mac         # Build Mac-specific package
```

### Git Service
```bash
cd git-service
pip install -r requirements.txt  # Install dependencies
python app.py                    # Start FastAPI server on localhost:8000
```

### Testing
Currently, no test framework is configured. The project uses placeholder test commands:
- Electron app: `npm test` (exits with error)
- Git service: Uses pytest via uv (`uv run python -m pytest {files}`)

## Architecture

### Electron App Structure
- **Frontend**: React 19 + TypeScript with Vite for bundling
- **Styling**: Tailwind CSS with shadcn/ui components
- **Main Process**: `main.js` handles Electron window management
- **Renderer**: `src/App.tsx` contains the main UI with multiple views:
  - Repository overview
  - Commit history listing
  - Commit detail analysis
  - AI-powered commit analysis
  - Chat interface for repository assistance

### Git Service Structure
- **API Framework**: FastAPI with Pydantic models
- **Database**: MongoDB integration via `repository/mongo_client.py`
- **Core Modules**:
  - `src/git_examine.py`: Git repository analysis
  - `src/commit_execute.py`: Git command execution
  - `src/prompt_examine.py`: AI prompt analysis
  - `src/models.py`: Pydantic data models
- **WebSocket**: Real-time command execution at `/ws/execute`

### Key Features
- Git repository observability interface
- Real-time commit analysis and visualization
- AI-powered code analysis with suggested fixes
- WebSocket-based command execution
- Session management for AI interactions
- Dark theme UI with modern design

### Data Flow
1. Electron app connects to Git service via WebSocket
2. Users can browse commit history and trigger AI analysis
3. AI analysis results include issue identification and fix suggestions
4. Chat interface allows natural language queries about the repository

## File Structure Notes
- UI components are in `electron-app/src/components/`
- Git service endpoints are defined in `app.py`
- Database models and session management in `src/models.py`
- Untracked Python files include enhanced classifier and hunk analysis tools

## Dependencies
- **Electron App**: React 19, Electron 37, Vite 7, TypeScript 5, Tailwind 3
- **Git Service**: FastAPI, MongoDB, OpenAI integration, WebSocket support