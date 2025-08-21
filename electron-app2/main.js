const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const fs = require('fs');
const chokidar = require('chokidar');
const WebSocket = require('ws');
const axios = require('axios');
const { spawn } = require('child_process');

// Keep a global reference of the window object
let mainWindow;

// Configuration
const API_ENDPOINT = "https://c98be102e98d.ngrok-free.app";

// Authentication token storage
let authToken = null;

function createWindow() {
  // Create the browser window
  mainWindow = new BrowserWindow({
    width: 800,
    height: 600,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    },
    icon: path.join(__dirname, 'assets', 'icon.png'), // Optional icon
    title: 'Git Watcher'
  });

  // Load the index.html file
  mainWindow.loadFile('index.html');

  // Open DevTools in development
  if (process.argv.includes('--dev')) {
    mainWindow.webContents.openDevTools();
  }

  // Emitted when the window is closed
  mainWindow.on('closed', function () {
    mainWindow = null;
  });
}

// This method will be called when Electron has finished initialization
app.whenReady().then(createWindow);

// Quit when all windows are closed
app.on('window-all-closed', function () {
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', function () {
  if (mainWindow === null) createWindow();
});

// Provide list of project folders under current user's ~/.claude/projects
ipcMain.handle('list-project-folders', async () => {
  try {
    const homeDir = app.getPath('home');
    const baseDir = path.join(homeDir, '.claude', 'projects');

    if (!fs.existsSync(baseDir)) {
      throw new Error(`Base directory does not exist: ${baseDir}`);
    }

    const entries = fs.readdirSync(baseDir, { withFileTypes: true });
    const folders = entries
      .filter((entry) => entry.isDirectory())
      .map((entry) => path.join(baseDir, entry.name));

    return { success: true, baseDir, folders };
  } catch (error) {
    return { success: false, error: error.message };
  }
});

// Authentication handlers
ipcMain.handle('set-auth-token', async (event, token) => {
  authToken = token;
  return { success: true };
});

ipcMain.handle('clear-auth-token', async () => {
  authToken = null;
  return { success: true };
});

// Helper function to get authenticated headers
function getAuthHeaders() {
  const headers = {
    'Content-Type': 'application/json'
  };
  
  if (authToken) {
    headers['Authorization'] = `Bearer ${authToken}`;
  }
  
  return headers;
}

// Helpers
function getNormalizedLines(content) {
  const lines = content.split(/\r?\n/);
  if (lines.length && lines[lines.length - 1] === '') {
    lines.pop();
  }
  return lines;
}

// File watcher state
let fileWatcher = null;
let sessionStarted = false;
let sessionId = '';
let currentCwd = '';
// Enhanced watcher/session state
let activeConversationFilePath = null; // Only process this file while a session is active
let lastActivityCounter = 0;           // Incremented for each processed line
let changeCycleCounter = 0;            // Incremented for each change event
let watchFolderPath = '';
// Pending assistant response debounce by message id
const pendingAssistantResponses = {}; // { [messageId: string]: { timer: NodeJS.Timeout, content: string, cwd: string, sourcePath: string, startedAt: number } }

function scheduleAssistantFinalize(messageId) {
  const pending = pendingAssistantResponses[messageId];
  if (!pending) return;
  if (pending.timer) {
    clearTimeout(pending.timer);
  }
  // Notify renderer that we are waiting for potential continuation
  sendToRenderer('waiting', { messageId, seconds: 10 });
  pending.timer = setTimeout(() => finalizeAssistant(messageId, 'timeout'), 10_000);
}

function finalizeAssistant(messageId, reason = 'timeout') {
  const pending = pendingAssistantResponses[messageId];
  if (!pending) return;
  if (pending.timer) {
    clearTimeout(pending.timer);
  }
  try {
    const finalOut = pending.content || '';
    if (finalOut) {
      sendEndConvo(sessionId, finalOut, currentCwd);
    }
  } finally {
    delete pendingAssistantResponses[messageId];
    // Reset session after sending end convo
    sessionStarted = false;
    activeConversationFilePath = null;
    sendToRenderer('waiting-cleared', { messageId, reason });
  }
}

function updateCWD(selectedFile) {
  // Find all files in selectedFile
  const files = fs.readdirSync(selectedFile);
  for (const file of files) {
      if (file.endsWith('.jsonl')) {
        const filePath = path.join(selectedFile, file);
        const content = fs.readFileSync(filePath, 'utf8');

        // Read first line of file
        const firstLine = content.split('\n')[0];

        // load json line
        const jsonLine = JSON.parse(firstLine);
        let detectedCwd = jsonLine.cwd || null;

        if (detectedCwd) {
          // Send CWD to renderer process via IPC
          sendToRenderer('cwd-updated', { cwd: detectedCwd });
          return detectedCwd;
        }
      }
  }
  return null;
}

ipcMain.handle('start-watching', async (event, filePath) => {
  try {
    if (!filePath) {
      throw new Error('No path provided');
    }
    if (!fs.existsSync(filePath)) {
      throw new Error('Selected path does not exist');
    }
    const stat = fs.statSync(filePath);
    if (!stat.isDirectory()) {
      throw new Error('Selected path is not a directory');
    }

    // Update cwd
    updateCWD(filePath);

    const watchFolder = filePath;
    watchFolderPath = watchFolder;

    // Stop existing watcher if any
    if (fileWatcher) {
      fileWatcher.close();
    }

    // Per-file state map
    const fileStates = {}; // { [filePath: string]: { lastSize: number, processedLineCount: number } }

    // Initialize states for existing .jsonl files in the folder
    let initialFiles = [];
    try {
      const entries = fs.readdirSync(watchFolder, { withFileTypes: true });
      initialFiles = entries
        .filter((e) => e.isFile() && e.name.endsWith('.jsonl'))
        .map((e) => path.join(watchFolder, e.name));

      for (const f of initialFiles) {
        try {
          const s = fs.statSync(f);
          const content = fs.readFileSync(f, 'utf8');
          const lines = getNormalizedLines(content);
          fileStates[f] = { lastSize: s.size, processedLineCount: lines.length };
          const initMsg = `Initial lines present in ${path.basename(f)}: ${lines.length}. Will process only new lines after this.`;
          console.log(initMsg);
          sendToRenderer('log', initMsg);
        } catch (err) {
          const warnMsg = `Could not read initial file content for ${path.basename(f)}: ${err.message}`;
          console.warn(warnMsg);
          sendToRenderer('error', warnMsg);
          fileStates[f] = { lastSize: 0, processedLineCount: 0 };
        }
      }
    } catch (err) {
      sendToRenderer('error', `Error scanning folder: ${err.message}`);
    }

    // Start watching all .jsonl files in the folder
    fileWatcher = chokidar.watch(path.join(watchFolder, '*.jsonl'), {
      persistent: true,
      usePolling: true,
      interval: 250,
      ignoreInitial: true
    });

    // Helper to scan for new files every N cycles
    function scanForNewFiles() {
      try {
        const entries = fs.readdirSync(watchFolder, { withFileTypes: true });
        const jsonlFiles = entries
          .filter((e) => e.isFile() && e.name.endsWith('.jsonl'))
          .map((e) => path.join(watchFolder, e.name));

        for (const f of jsonlFiles) {
          if (!(f in fileStates)) {
            try {
              const s = fs.statSync(f);
              const content = fs.readFileSync(f, 'utf8');
              const lines = getNormalizedLines(content);
              fileStates[f] = { lastSize: s.size, processedLineCount: lines.length };
              const msg = `Discovered new file ${path.basename(f)} (deferred: ${lines.length} existing line(s))`;
              console.log(msg);
              sendToRenderer('log', msg);
            } catch (err) {
              sendToRenderer('error', `Error initializing discovered file ${path.basename(f)}: ${err.message}`);
            }
          }
        }
      } catch (err) {
        sendToRenderer('error', `Error scanning for new files: ${err.message}`);
      }
    }

    // Handle new files appearing after start
    fileWatcher.on('add', (addedPath) => {
      try {
        const s = fs.statSync(addedPath);
        const content = fs.readFileSync(addedPath, 'utf8');
        const lines = getNormalizedLines(content);
        fileStates[addedPath] = { lastSize: s.size, processedLineCount: lines.length };
        const msg = sessionStarted && activeConversationFilePath && addedPath !== activeConversationFilePath
          ? `New file ${path.basename(addedPath)} detected (${lines.length} existing line(s)). Current session active on ${path.basename(activeConversationFilePath)}; deferring processing.`
          : `Now watching new file ${path.basename(addedPath)} with ${lines.length} existing line(s).`;
        console.log(msg);
        sendToRenderer('log', msg);
      } catch (err) {
        sendToRenderer('error', `Error initializing new file ${path.basename(addedPath)}: ${err.message}`);
      }
    });

    fileWatcher.on('change', (changedPath) => {
      try {
        // Count cycles and optionally scan for new files
        changeCycleCounter += 1;

        // If a session is active, only process the active file; ignore others
        if (sessionStarted && activeConversationFilePath && changedPath !== activeConversationFilePath) {
          sendToRenderer('log', `Ignoring change in ${path.basename(changedPath)} due to active session on ${path.basename(activeConversationFilePath)}`);
          if (changeCycleCounter % 3 === 0) {
            scanForNewFiles();
          }
          return;
        }

        const prev = fileStates[changedPath] || { lastSize: 0, processedLineCount: 0 };
        const stats = fs.statSync(changedPath);
        if (stats.size !== prev.lastSize) {
          const content = fs.readFileSync(changedPath, 'utf8');
          const allLines = getNormalizedLines(content);

          // Handle truncation/rotation
          if (allLines.length < prev.processedLineCount || stats.size < prev.lastSize) {
            const resetMsg = `File ${path.basename(changedPath)} truncated or rotated. Resetting processed line count from ${prev.processedLineCount} to ${allLines.length}.`;
            console.log(resetMsg);
            sendToRenderer('log', resetMsg);
            fileStates[changedPath] = { lastSize: stats.size, processedLineCount: allLines.length };
            return;
          }

          const newLinesCount = allLines.length - prev.processedLineCount;
          if (newLinesCount > 0) {
            for (let i = prev.processedLineCount; i < allLines.length; i++) {
              const line = allLines[i];

              if (line && line.trim()) {
                // Bump activity counter for each processed line
                lastActivityCounter += 1;
                processLine(line.trim(), changedPath, newLinesCount);
              }
            }
            const procMsg = `Processed ${newLinesCount} new line(s) in ${path.basename(changedPath)}. Total lines now: ${allLines.length}.`;
            // console.log(procMsg);
            sendToRenderer('log', procMsg);
          }

          fileStates[changedPath] = { lastSize: stats.size, processedLineCount: allLines.length };
        }
        if (changeCycleCounter % 3 === 0) {
          scanForNewFiles();
        }
      } catch (err) {
        sendToRenderer('error', `Error reading file ${path.basename(changedPath)}: ${err.message}`);
      }
    });

    sendToRenderer('status', 'Started');
    sendToRenderer('log', `Watching folder: ${watchFolder} (${initialFiles.length} *.jsonl file(s))`);

    return { success: true, watchFolder, files: initialFiles };
  } catch (error) {
    sendToRenderer('error', error.message);
    return { success: false, error: error.message };
  }
});

ipcMain.handle('stop-watching', async () => {
  if (fileWatcher) {
    fileWatcher.close();
    fileWatcher = null;
  }
  sessionStarted = false;
  sessionId = '';
  activeConversationFilePath = null;
  sendToRenderer('status', 'Stopped');
  sendToRenderer('log', 'File watching stopped');
  return { success: true };
});

function sendToRenderer(type, data) {
  if (mainWindow && mainWindow.webContents) {
    mainWindow.webContents.send('update', { type, data });
  }
}

function processLine(line, sourcePath, newLinesCount) {
  try {
    const lineData = JSON.parse(line);
    const cwd = lineData.cwd || 'None';
    const messageId = lineData.message?.id || '';
    currentCwd = cwd;

    if (messageId && messageId in pendingAssistantResponses) {
      // remove the message from the pending list
      delete pendingAssistantResponses[messageId];
      sendToRenderer('log', `Removed message ${messageId} from pending list`);
    }
    
    // If a session is active and this line is from a different file, ignore
    if (sessionStarted && activeConversationFilePath && sourcePath && sourcePath !== activeConversationFilePath) {
      return;
    }

    if (lineData.message?.role === "user" && !sessionStarted) {
      // tool resuts are apperantly usermessages, so we ignore them
      if ("toolUseResult" in lineData) {
        return;
      }
      // if we see three messages we skip; Claude sends three messages if it stops the convo
      if (newLinesCount > 2) {
        sendToRenderer('log', `Skipping Fake user message`);
        return;
      }
      const prompt = lineData.message?.content || "Empty Message, ignore";
      sessionStarted = true;
      activeConversationFilePath = sourcePath || null;
      sendStartConvo(prompt, cwd);
    } else if (lineData.message?.role === "assistant") {
      let finalMessage = lineData.message?.content || {};

      // Do not skip when multiple new lines arrive together; still handle debounce by message id
      
      if (Array.isArray(finalMessage) && finalMessage.length === 1) {
        finalMessage = finalMessage[0];
      }
      
      let messageText = '';
      if (typeof finalMessage === 'string') {
        messageText = finalMessage;
      } else if (finalMessage.type === 'text') {
        messageText = finalMessage.text;
      }
      
      if (!messageId) {
        // Fallback to immediate behavior if no id present
        if (messageText) {
          sendEndConvo(sessionId, messageText, currentCwd);
          sessionStarted = false;
          activeConversationFilePath = null;
        }
        return;
      }

      if (!messageText) {
        return;
      }

      if (!pendingAssistantResponses[messageId]) {
        pendingAssistantResponses[messageId] = {
          timer: null,
          content: messageText,
          cwd: currentCwd,
          sourcePath,
          startedAt: Date.now()
        };
        sendToRenderer('log', `Assistant message ${messageId} received. Waiting up to 10s for possible continuation. Click 'Finish now' to proceed.`);
      }
      scheduleAssistantFinalize(messageId);
    }
  } catch (err) {
    sendToRenderer('error', `Error processing line: ${err.message}`);
  }
}

async function sendStartConvo(prompt, cwd) {
  try {
    sendToRenderer('status', 'Starting');
    sendToRenderer('log', 'Starting conversation...');

    const cwd_string = cwd.replace(/\\/g, '/');
    const response = await axios.post(`${API_ENDPOINT}/session/start`, {
      user_prompt: prompt,
      cwd: cwd_string
    }, { 
      headers: getAuthHeaders(),
      timeout: 10000 
    });
    
    sessionId = response.data.session_id;
    sendToRenderer('log', `Session started: ${sessionId}`);
  } catch (error) {
    sendToRenderer('error', `Error starting conversation: ${error.message}`);
    sessionStarted = false;
  }
}

async function sendEndConvo(sessionId, finalOut, cwd) {
  try {
    sendToRenderer('log', 'Ending conversation...');
    sendToRenderer('status', 'Processing');
    
    const response = await axios.post(`${API_ENDPOINT}/session/end`, {
      session_id: sessionId,
      final_output: finalOut,
      status: "success",
      cwd: cwd.replace(/\\/g, '/'),
      metadata: {
        tool_calls: 0,
        todos_completed: 0,
        files_modified: []
      }
    }, { 
      headers: getAuthHeaders(),
      timeout: 15000 
    });
    
    if (response.status === 200) {
      sendToRenderer('log', 'Session ended successfully');
      // Start git operations via WebSocket
      startGitOperations(sessionId, cwd);
    } else {
      sendToRenderer('error', `Error ending session: ${response.status}`);
    }
  } catch (error) {
    sendToRenderer('error', `Error ending conversation: ${error.message}`);
  }
}

function startGitOperations(sessionId, cwd) {
  try {
    sendToRenderer('log', 'Starting git operations via WebSocket...');
    
    const apiUrl = new URL(API_ENDPOINT);
    const wsProtocol = apiUrl.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${apiUrl.host}/ws/execute`;
    const ws = new WebSocket(wsUrl);
    
    ws.on('open', () => {
      sendToRenderer('log', 'WebSocket connected');
      
      // First, authenticate with the server
      if (!authToken) {
        sendToRenderer('error', 'No authentication token available for WebSocket');
        ws.close();
        return;
      }
      
      ws.send(JSON.stringify({
        message_type: "authenticate",
        token: authToken
      }));
    });
    
    ws.on('message', (data) => {
      try {
        const message = JSON.parse(data.toString());
        sendToRenderer('websocket', `Received: ${JSON.stringify(message)}`);
        
        // Handle authentication response
        if (message.message_type === "auth_success") {
          sendToRenderer('log', 'WebSocket authenticated successfully');
          // Now send the session finished message
          ws.send(JSON.stringify({
            session_id: sessionId,
            message_type: "session_finished"
          }));
          return;
        }
        
        // Handle authentication error
        if (message.error) {
          sendToRenderer('error', `WebSocket authentication failed: ${message.error}`);
          ws.close();
          return;
        }
        
        if (message.message_type === "session_finished") {
          sendToRenderer('log', `Session ${sessionId} completed successfully`);
          sendToRenderer('status', 'Done');
          ws.close();
          return;
        }
        
        if (message.message_type === "execute_command") {
          const cmd = message.command || "";
          if (!cmd) {
            ws.send(JSON.stringify({
              message_type: "command_executed",
              output: ""
            }));
            return;
          }
          
          sendToRenderer('log', `Executing command: ${cmd}`);
          
          // Execute command
          const child = spawn(cmd, [], {
            cwd: cwd || undefined,
            shell: true,
            stdio: 'pipe'
          });
          
          let output = '';
          child.stdout.on('data', (data) => {
            output += data.toString();
          });
          
          child.stderr.on('data', (data) => {
            output += data.toString();
          });
          
          child.on('close', (code) => {
            sendToRenderer('log', `Command output: ${output}`);
            ws.send(JSON.stringify({
              message_type: "command_executed",
              output: output
            }));
          });
          
          child.on('error', (error) => {
            const errorOutput = `Command execution error: ${error.message}`;
            sendToRenderer('error', errorOutput);
            ws.send(JSON.stringify({
              message_type: "command_executed",
              output: errorOutput
            }));
          });
        }
      } catch (error) {
        sendToRenderer('error', `WebSocket message error: ${error.message}`);
      }
    });
    
    ws.on('error', (error) => {
      sendToRenderer('error', `WebSocket error: ${error.message}`);
    });
    
    ws.on('close', () => {
      sendToRenderer('log', 'WebSocket connection closed');
    });
    
  } catch (error) {
    sendToRenderer('error', `Error starting git operations: ${error.message}`);
  }
}

