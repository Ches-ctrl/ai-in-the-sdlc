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
const connectionIndicator = document.getElementById('connectionIndicator');
const connectionText = document.getElementById('connectionText');
const nightModeToggle = document.getElementById('nightModeToggle');
const streamEventsToggle = document.getElementById('streamEventsToggle');
const eventSection = document.querySelector('.event-section');

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
let connectionCheckInterval = null;

// Configuration
const API_ENDPOINT = "https://37db756b0032.ngrok-free.app";

// Event listeners
startBtn.addEventListener('click', startWatching);
stopBtn.addEventListener('click', stopWatching);
clearLogsBtn.addEventListener('click', clearLogs);
nightModeToggle.addEventListener('change', toggleNightMode);
streamEventsToggle.addEventListener('change', toggleStreamEvents);
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

folderSelect.addEventListener('change', async () => {
    selectedFile = folderSelect.value || null;
    startBtn.disabled = !selectedFile;
    if (selectedFile) {
        addLogEntry('log', `Folder selected: ${selectedFile}`);
        // Auto-start watching when a folder is selected
        if (!isWatching) {
            addLogEntry('log', 'Auto-starting watch...');
            await startWatching();
        }
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

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    stopConnectionChecking();
});

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
        <span>> ${escapeHtml(message)}</span>
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

// Details toggle function
function toggleDetails() {
    const detailsContent = document.getElementById('detailsContent');
    const toggleButton = document.querySelector('.details-toggle');
    
    if (detailsContent.classList.contains('open')) {
        detailsContent.classList.remove('open');
        toggleButton.textContent = 'details ▼';
    } else {
        detailsContent.classList.add('open');
        toggleButton.textContent = 'details ▲';
    }
}

// Make function available globally
window.toggleDetails = toggleDetails;

// Connection status functions
async function checkConnectionStatus() {
    try {
        const response = await fetch(`${API_ENDPOINT}/health`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json'
            },
            timeout: 5000 // 5 second timeout
        });
        
        if (response.status === 200) {
            const isRunning = true;
            updateConnectionStatus(isRunning);
        } else {
            updateConnectionStatus(false);
        }
    } catch (error) {
        updateConnectionStatus(false);
        console.log('Connection check failed:', error.message);
    }
}

function updateConnectionStatus(isConnected) {
    if (isConnected) {
        connectionIndicator.classList.add('connected');
        connectionText.textContent = 'Connected';
    } else {
        connectionIndicator.classList.remove('connected');
        connectionText.textContent = 'Disconnected';
    }
}

function startConnectionChecking() {
    console.log('Starting connection checking');
    // Initial check
    checkConnectionStatus();
    
    // Clear existing interval if any
    if (connectionCheckInterval) {
        clearInterval(connectionCheckInterval);
    }
    
    // Check every 10 seconds
    connectionCheckInterval = setInterval(checkConnectionStatus, 10000);
}

function stopConnectionChecking() {
    if (connectionCheckInterval) {
        clearInterval(connectionCheckInterval);
        connectionCheckInterval = null;
    }
}

// Initialize UI state
updateStatus('Stopped');
populateProjectFolders();
startConnectionChecking();

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

// Commit Details Sidebar Functionality
const commitSidebar = document.getElementById('commitSidebar');
const sidebarContent = document.getElementById('sidebarContent');

// Dynamic commit data storage
let commitData = {};

// Fetch recent commits from the API
async function fetchRecentCommits(limit = 20) {
    try {
        const response = await fetch(`${API_ENDPOINT}/commits/recent?limit=${limit}`, {
            method: 'GET',
            headers: {
                'ngrok-skip-browser-warning': 'true',
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const commits = await response.json();
        return commits;
    } catch (error) {
        console.error('Error fetching commits:', error);
        addLogEntry('error', `Failed to fetch commits: ${error.message}`);
        return [];
    }
}

// Transform API commit data to match expected format
function transformCommitData(apiCommits) {
    const transformed = {};
    
    apiCommits.forEach((commit, index) => {
        console.log('Commit:', commit);
        const commitId = `commit_${commit.commit_hash}`;
        
        // Determine status based on metadata or default logic
        let status = 'success'; // Default to success
        if (commit.metadata && commit.metadata.commit_output) {
            // If commit output contains error keywords, mark as failed
            const output = commit.metadata.commit_output.toLowerCase();
            if (output.includes('error') || output.includes('failed') || output.includes('conflict')) {
                status = 'failed';
            }
        }
        
        transformed[commitId] = {
            hash: commit.commit_hash?.substring(0, 12) || 'unknown', // Short hash
            fullHash: commit.commit_hash || 'unknown',
            message: commit.message,
            prompt: commit.prompt,
            author: commit.author || 'Unknown',
            email: commit.email || 'unknown@example.com',
            date: new Date(commit.timestamp).toLocaleString(),
            branch: 'main', // Default branch, could be enhanced
            cwd: commit.cwd,
            status: status,
            files: commit.files_changed.map(file => ({
                path: file,
                status: 'modified' // Default to modified, could be enhanced
            })),
            metadata: commit.metadata
        };
    });
    
    return transformed;
}

// Group commits by prompt
function groupCommitsByPrompt(transformedCommits) {
    const groups = {};
    
    Object.entries(transformedCommits).forEach(([commitId, commit]) => {
        const prompt = commit.prompt || 'Uncategorized';
        
        if (!groups[prompt]) {
            groups[prompt] = [];
        }
        
        groups[prompt].push({
            id: commitId,
            ...commit
        });
    });
    
    return groups;
}

// Render prompt activity section
function renderPromptActivity(commitGroups) {
    const activitySection = document.querySelector('.activity-section');
    
    if (Object.keys(commitGroups).length === 0) {
        activitySection.innerHTML = '<div class="no-commits">No recent commits found.</div>';
        return;
    }
    
    let html = '';
    
    Object.entries(commitGroups).forEach(([prompt, commits]) => {
        html += `
            <div class="prompt-group">
                <div class="prompt-title">"${prompt}"</div>
                <div class="commit-list">
        `;
        
        commits.forEach(commit => {
            const statusClass = commit.status === 'success' ? 'success' : 'error';
            const statusText = commit.status === 'success' ? 'Success' : 'Failed';
            
            html += `
                <div class="commit-item" onclick="showCommitDetails('${commit.id}')">
                    <span class="commit-hash">#${commit.hash}</span>
                    <span class="commit-message">${commit.message}</span>
                    <span class="commit-status ${statusClass}">${statusText}</span>
                </div>
            `;
        });
        
        html += `
                </div>
            </div>
        `;
    });
    
    activitySection.innerHTML = html;
}

// Load and display commits
async function loadRecentCommits() {
    try {
        addLogEntry('info', 'Fetching recent commits...');
        
        const apiCommits = await fetchRecentCommits();
        
        if (apiCommits.length === 0) {
            addLogEntry('warning', 'No commits found');
            return;
        }
        
        // Transform and store commit data
        commitData = transformCommitData(apiCommits);
        
        // Group commits by prompt
        const commitGroups = groupCommitsByPrompt(commitData);
        
        // Render the activity section
        renderPromptActivity(commitGroups);
        
        // addLogEntry('success', `Loaded ${apiCommits.length} commits grouped by ${Object.keys(commitGroups).length} prompts`);
        
    } catch (error) {
        console.error('Error loading commits:', error);
        addLogEntry('error', `Failed to load commits: ${error.message}`);
    }
}

// Auto-refresh interval (30 seconds)
let refreshInterval = null;

// Start auto-refresh
function startAutoRefresh() {
    if (refreshInterval) clearInterval(refreshInterval);
    refreshInterval = setInterval(() => {
        loadRecentCommits();
    }, 30000); // 30 seconds
}

// Stop auto-refresh
function stopAutoRefresh() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
        refreshInterval = null;
    }
}

// Call loadRecentCommits when page loads and start auto-refresh
document.addEventListener('DOMContentLoaded', () => {
    loadRecentCommits();
    startAutoRefresh();
});

// Night Mode Functions
function toggleNightMode() {
    const isDark = nightModeToggle.checked;
    setTheme(isDark ? 'dark' : 'light');
    localStorage.setItem('theme', isDark ? 'dark' : 'light');
}

function setTheme(theme) {
    if (theme === 'dark') {
        document.documentElement.setAttribute('data-theme', 'dark');
        nightModeToggle.checked = true;
    } else {
        document.documentElement.removeAttribute('data-theme');
        nightModeToggle.checked = false;
    }
}

// Stream Events Toggle Functions
function toggleStreamEvents() {
    const showStream = streamEventsToggle.checked;
    setStreamEventsVisibility(showStream);
    localStorage.setItem('showStreamEvents', showStream.toString());
}

function setStreamEventsVisibility(show) {
    if (show) {
        eventSection.classList.remove('hidden');
        streamEventsToggle.checked = true;
    } else {
        eventSection.classList.add('hidden');
        streamEventsToggle.checked = false;
    }
}

function initializeTheme() {
    const savedTheme = localStorage.getItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const theme = savedTheme || (prefersDark ? 'dark' : 'light');
    setTheme(theme);
}

function initializeStreamEvents() {
    const savedStreamEvents = localStorage.getItem('showStreamEvents');
    // Default to showing stream events if no preference is saved
    const showStream = savedStreamEvents !== null ? savedStreamEvents === 'true' : true;
    setStreamEventsVisibility(showStream);
}

function showCommitDetails(commitId) {
    const commit = commitData[commitId];
    if (!commit) return;
    
    const statusClass = commit.status === 'success' ? 'success' : 'error';
    const statusText = commit.status === 'success' ? 'Success' : 'Failed';
    
    const content = `
        <div class="detail-section">
            <h4>Commit Information</h4>
            <div class="detail-item">
                <span class="detail-label">Hash:</span>
                <span class="detail-value monospace">${commit.fullHash || commit.hash}</span>
            </div>
            <div class="detail-item">
                <span class="detail-label">Message:</span>
                <span class="detail-value">${commit.message}</span>
            </div>
            ${commit.prompt ? `
            <div class="detail-item">
                <span class="detail-label">Prompt:</span>
                <span class="detail-value">"${commit.prompt}"</span>
            </div>
            ` : ''}
            <div class="detail-item">
                <span class="detail-label">Status:</span>
                <span class="detail-value ${statusClass}">${statusText}</span>
            </div>
            <div class="detail-item">
                <span class="detail-label">Branch:</span>
                <span class="detail-value monospace">${commit.branch}</span>
            </div>
        </div>
        
        <div class="detail-section">
            <h4>Author Information</h4>
            <div class="detail-item">
                <span class="detail-label">Author:</span>
                <span class="detail-value">${commit.author}</span>
            </div>
            ${commit.email && commit.email !== 'unknown@example.com' ? `
            <div class="detail-item">
                <span class="detail-label">Email:</span>
                <span class="detail-value">${commit.email}</span>
            </div>
            ` : ''}
            <div class="detail-item">
                <span class="detail-label">Date:</span>
                <span class="detail-value">${commit.date}</span>
            </div>
        </div>
        
        <div class="detail-section">
            <h4>Environment</h4>
            <div class="detail-item">
                <span class="detail-label">Working Dir:</span>
                <span class="detail-value monospace">${commit.cwd}</span>
            </div>
        </div>
        
        <div class="detail-section">
            <h4>Changed Files</h4>
            <ul class="file-list">
                ${commit.files.map(file => 
                    `<li class="${file.status}">${file.path}</li>`
                ).join('')}
            </ul>
        </div>
        
        ${commit.metadata && commit.metadata.commit_output ? `
        <div class="detail-section">
            <h4>Commit Output</h4>
            <div class="detail-item">
                <span class="detail-value" style="font-family: monospace; background: #f8f9fa; padding: 8px; border-radius: 4px; display: block; margin-top: 4px; white-space: pre-wrap;">${commit.metadata.commit_output}</span>
            </div>
        </div>
        ` : ''}
        
        ${commit.error ? `
        <div class="detail-section">
            <h4>Error Details</h4>
            <div class="detail-item">
                <span class="detail-value" style="color: #e74c3c; font-family: monospace; background: #fdf2f2; padding: 8px; border-radius: 4px; display: block; margin-top: 4px;">${commit.error}</span>
            </div>
        </div>
        ` : ''}
    `;
    
    sidebarContent.innerHTML = content;
    commitSidebar.classList.add('open');
}

function hideCommitDetails() {
    commitSidebar.classList.remove('open');
}

// Close sidebar when clicking outside
document.addEventListener('click', (e) => {
    if (commitSidebar.classList.contains('open') && 
        !commitSidebar.contains(e.target) && 
        !e.target.closest('.commit-item')) {
        hideCommitDetails();
    }
});

// Initialize theme and stream events on page load
initializeTheme();
initializeStreamEvents();

