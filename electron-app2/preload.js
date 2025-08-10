const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld('electronAPI', {
  selectFile: () => ipcRenderer.invoke('select-file'),
  startWatching: (filePath) => ipcRenderer.invoke('start-watching', filePath),
  stopWatching: () => ipcRenderer.invoke('stop-watching'),
  onUpdate: (callback) => ipcRenderer.on('update', callback),
  listProjectFolders: () => ipcRenderer.invoke('list-project-folders'),
  // flushWait: (messageId) => ipcRenderer.invoke('flush-wait', messageId)
});

