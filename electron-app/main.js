const { app, BrowserWindow, nativeTheme, ipcMain, dialog } = require('electron');
const path = require('path');
const fs = require('fs');

let mainWindow;
const isDev = process.env.NODE_ENV !== 'production';

function createWindow() {
  // Set dock icon for macOS after app is ready
  if (process.platform === 'darwin') {
    const icnsPath = path.join(__dirname, 'assets/icons/icon.icns');
    const pngPath = path.join(__dirname, 'assets/icons/icon.png');
    
    try {
      if (fs.existsSync(icnsPath)) {
        app.dock.setIcon(icnsPath);
      } else if (fs.existsSync(pngPath)) {
        app.dock.setIcon(pngPath);
      }
    } catch (error) {
      console.warn('Could not set dock icon:', error.message);
      // Fallback to PNG
      try {
        if (fs.existsSync(pngPath)) {
          app.dock.setIcon(pngPath);
        }
      } catch (fallbackError) {
        console.warn('PNG fallback also failed:', fallbackError.message);
      }
    }
  }
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    titleBarStyle: 'hiddenInset',
    trafficLightPosition: { x: 20, y: 20 },
    backgroundColor: '#0a0a0a',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    },
    icon: fs.existsSync(path.join(__dirname, 'assets/icons/icon.png')) 
      ? path.join(__dirname, 'assets/icons/icon.png')
      : undefined
  });

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, 'dist/index.html'));
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  nativeTheme.themeSource = 'dark';
}

ipcMain.handle('dialog:openDirectory', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory']
  });
  return result;
});

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (mainWindow === null) {
    createWindow();
  }
});