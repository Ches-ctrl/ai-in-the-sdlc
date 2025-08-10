# Git Watcher Desktop App

A desktop application built with Electron that automatically executes git commands when files change in a watched folder.

## Features

- **Folder Selection**: Choose any folder to watch for changes
- **File Monitoring**: Automatically detects changes in .jsonl files
- **Session Management**: Handles conversation sessions with start/end lifecycle
- **WebSocket Communication**: Real-time communication with backend services
- **Git Automation**: Executes git commands automatically based on file changes
- **Event Streaming**: Live display of all operations and command outputs
- **Status Indicators**: Visual feedback for Started, Processing, and Done states

## Installation

1. Clone or download this project
2. Install dependencies:
   ```bash
   npm install
   ```

## Usage

### Development Mode
```bash
npm run dev
```

### Production Mode
```bash
npm start
```

### Building for Distribution
```bash
npm run build
```

## How It Works

1. **Select Folder**: Click "Select Folder" to choose a directory containing .jsonl files
2. **Start Watching**: Click "Start Watching" to begin monitoring the selected folder
3. **Automatic Processing**: The app will:
   - Monitor .jsonl files for new content
   - Parse conversation data (user/assistant messages)
   - Send session start/end requests to the configured API endpoint
   - Execute git commands via WebSocket communication
   - Display real-time logs and status updates

## Configuration

The app is configured to work with the API endpoint:
```
https://4634e217c2b6.ngrok-free.app
```

To change this, modify the `API_ENDPOINT` constant in `main.js`.

## File Structure

```
git-watcher-app/
├── main.js          # Electron main process
├── preload.js       # Secure IPC bridge
├── index.html       # UI interface
├── renderer.js      # UI logic and interactions
├── package.json     # Project configuration
└── README.md        # This file
```

## API Integration

The app integrates with a backend service that provides:
- Session management endpoints (`/session/start`, `/session/end`)
- WebSocket endpoint for command execution (`/ws/execute`)

## Status Indicators

- **Stopped** (Gray): App is idle, not watching any folder
- **Started** (Orange): File watching is active
- **Processing** (Blue, pulsing): Session is being processed
- **Done** (Green): Session completed successfully
- **Error** (Red): An error occurred during processing

## Event Stream

The event stream displays:
- File watching status
- Session lifecycle events
- WebSocket messages
- Command execution outputs
- Error messages

## Requirements

- Node.js 16 or higher
- Electron 28 or higher
- Access to the configured API endpoint
- Git installed on the system (for command execution)

## Troubleshooting

1. **No .jsonl files found**: Ensure the selected folder contains .jsonl files
2. **API connection errors**: Check network connectivity and API endpoint availability
3. **WebSocket connection issues**: Verify the WebSocket endpoint is accessible
4. **Git command failures**: Ensure git is installed and the working directory is a git repository

## Development

To modify the app:
1. Edit `main.js` for backend logic and file watching
2. Edit `index.html` and `renderer.js` for UI changes
3. Use `npm run dev` to run with developer tools enabled

## License

MIT License

