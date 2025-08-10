// DOM elements
const folderSelect = document.getElementById('folderSelect');
const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const statusIndicator = document.getElementById('statusIndicator');
const statusText = document.getElementById('statusText');
const sessionInfo = document.getElementById('sessionInfo');
const eventStream = document.getElementById('eventStream');
const clearLogsBtn = document.getElementById('clearLogsBtn');
const finishNowBtn = document.getElementById('finishNowBtn');

// Auto-scroll handling: stick to bottom unless user scrolls up
let shouldAutoScroll = true;

function isNearBottom(element, threshold = 40) {
  const distanceFromBottom = element.scrollHeight - element.clientHeight - element.scrollTop;
  return distanceFromBottom <= threshold;
}

eventStream.addEventListener('scroll', () => {
  shouldAutoScroll = isNearBottom(eventStream);
});

// State
let isWatching = false;
let selectedFile = null;
let baseProjectsDir = '';

// Event listeners
startBtn.addEventListener('click', startWatching);
stopBtn.addEventListener('click', stopWatching);
clearLogsBtn.addEventListener('click', clearLogs);
// finishNowBtn.addEventListener('click', flushWait);

// Listen for updates from main process
window.electronAPI.onUpdate((event, update) => {
    handleUpdate(update);
});

// Populate folder dropdown with project folders
async function populateProjectFolders() {
    try {
        const result = await window.electronAPI.listProjectFolders();
        if (!result || !result.success) {
            const errMsg = result && result.error ? result.error : 'Unknown error retrieving folders';
            addLogEntry('error', `Unable to load project folders: ${errMsg}`);
            return;
        }

        baseProjectsDir = normalizePath(result.baseDir);
        const folders = (result.folders || []).map(normalizePath).sort();

        // Reset dropdown
        folderSelect.innerHTML = '';
        const placeholder = document.createElement('option');
        placeholder.value = '';
        placeholder.textContent = 'Select a project folder…';
        placeholder.className = 'placeholder';
        folderSelect.appendChild(placeholder);

        // Compute labels by trimming the common base path
        const baseWithSlash = baseProjectsDir.endsWith('/') ? baseProjectsDir : baseProjectsDir + '/';

        // First, trim the base dir from all paths to form initial labels
        const initialLabels = folders.map((folderPath) => (
            folderPath.startsWith(baseWithSlash)
                ? folderPath.slice(baseWithSlash.length)
                : folderPath
        ));

        // Compute common prefix across labels and snap it to the last hyphen boundary
        const rawCommonPrefix = getCommonPrefix(initialLabels);
        const lastHyphenIdx = rawCommonPrefix.lastIndexOf('-');
        const effectivePrefix = lastHyphenIdx >= 0
            ? rawCommonPrefix.slice(0, lastHyphenIdx + 1)
            : rawCommonPrefix;

        // Build options with concise labels
        initialLabels.forEach((label, index) => {
            const option = document.createElement('option');
            option.value = folders[index];

            let trimmed = label.startsWith(effectivePrefix)
                ? label.slice(effectivePrefix.length)
                : label;
            // Clean any leftover leading separators
            trimmed = trimmed.replace(/^[-\/]+/, '');
            option.textContent = trimmed || label;

            folderSelect.appendChild(option);
        });

        startBtn.disabled = true;
    } catch (error) {
        addLogEntry('error', `Error loading folders: ${error.message}`);
    }
}

function normalizePath(p) {
    return p.replace(/\\/g, '/');
}

function getCommonPrefix(strings) {
    if (!Array.isArray(strings) || strings.length === 0) {
        return '';
    }

    let prefix = strings[0] ?? '';
    for (let i = 1; i < strings.length && prefix; i += 1) {
        const current = strings[i] ?? '';
        let j = 0;
        const maxLen = Math.min(prefix.length, current.length);
        while (j < maxLen && prefix.charAt(j) === current.charAt(j)) {
            j += 1;
        }
        prefix = prefix.slice(0, j);
    }
    return prefix;
}

folderSelect.addEventListener('change', () => {
    selectedFile = folderSelect.value || null;
    startBtn.disabled = !selectedFile;
    if (selectedFile) {
        addLogEntry('log', `Folder selected: ${selectedFile}`);
    }
});

async function startWatching() {
    if (!selectedFile) {
        addLogEntry('error', 'No folder selected');
        return;
    }

    try {
        startBtn.disabled = true;
        folderSelect.disabled = true;
        
        const result = await window.electronAPI.startWatching(selectedFile);
        
        if (result.success) {
            isWatching = true;
            stopBtn.disabled = false;
            addLogEntry('log', `Started watching: ${result.watchFile}`);
        } else {
            startBtn.disabled = false;
            folderSelect.disabled = false;
            addLogEntry('error', `Failed to start watching: ${result.error}`);
        }
    } catch (error) {
        startBtn.disabled = false;
        folderSelect.disabled = false;
        addLogEntry('error', `Error starting watcher: ${error.message}`);
    }
}

async function stopWatching() {
    try {
        stopBtn.disabled = true;
        
        const result = await window.electronAPI.stopWatching();
        
        if (result.success) {
            isWatching = false;
            startBtn.disabled = false;
            folderSelect.disabled = false;
            addLogEntry('log', 'Stopped watching');
        } else {
            stopBtn.disabled = false;
            addLogEntry('error', 'Failed to stop watching');
        }
    } catch (error) {
        stopBtn.disabled = false;
        addLogEntry('error', `Error stopping watcher: ${error.message}`);
    }
}

function handleUpdate(update) {
    const { type, data } = update;
    
    switch (type) {
        case 'status':
            updateStatus(data);
            break;
        case 'log':
            addLogEntry('log', data);
            break;
        case 'error':
            addLogEntry('error', data);
            break;
        case 'websocket':
            addLogEntry('websocket', data);
            break;
    // case 'waiting':
    //   showFinishButton(data);
    //   break;
    // case 'waiting-cleared':
    //   hideFinishButton();
    //   break;
        default:
            addLogEntry('log', `${type}: ${data}`);
    }
}

function updateStatus(status) {
    statusText.textContent = status;
    statusIndicator.className = 'status-indicator';
    
    switch (status.toLowerCase()) {
        case 'started':
            statusIndicator.classList.add('started');
            break;
        case 'processing':
            statusIndicator.classList.add('processing');
            break;
        case 'done':
            statusIndicator.classList.add('done');
            break;
        case 'stopped':
            statusIndicator.classList.remove('started', 'processing', 'done', 'error');
            break;
        default:
            statusIndicator.classList.add('error');
    }
}

function addLogEntry(type, message) {
    const timestamp = new Date().toLocaleTimeString();
    const logEntry = document.createElement('div');
    logEntry.className = `log-entry ${type}`;
    
    logEntry.innerHTML = `
        <span class="timestamp">[${timestamp}]</span>
        <span>${escapeHtml(message)}</span>
    `;
    
    const wasAtBottom = isNearBottom(eventStream);
    eventStream.appendChild(logEntry);
    if (wasAtBottom) {
        requestAnimationFrame(() => {
            eventStream.scrollTop = eventStream.scrollHeight;
        });
    }
    
    // Limit log entries to prevent memory issues
    const maxEntries = 1000;
    while (eventStream.children.length > maxEntries) {
        eventStream.removeChild(eventStream.firstChild);
    }
}

function clearLogs() {
    eventStream.innerHTML = '';
    addLogEntry('log', 'Logs cleared');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Initialize UI state
updateStatus('Stopped');
populateProjectFolders();

// function showFinishButton(data) {
//   if (!data || !data.messageId) return;
//   finishNowBtn.style.display = 'inline-block';
//   finishNowBtn.dataset.messageId = data.messageId;
// }

// function hideFinishButton() {
//   finishNowBtn.style.display = 'none';
//   delete finishNowBtn.dataset.messageId;
// }

// async function flushWait() {
//   const messageId = finishNowBtn.dataset.messageId;
//   if (!messageId) return;
//   try {
//     finishNowBtn.disabled = true;
//     const result = await window.electronAPI.flushWait(messageId);
//     if (!result || !result.success) {
//       addLogEntry('error', result && result.error ? result.error : 'Failed to flush wait');
//     }
//   } catch (error) {
//     addLogEntry('error', `Error flushing wait: ${error.message}`);
//   } finally {
//     finishNowBtn.disabled = false;
//   }
// }


