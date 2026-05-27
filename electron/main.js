'use strict'

/**
 * Platapicker — Electron main process
 *
 * Lifecycle:
 *  1. Show loading splash window
 *  2. Find Python and spawn the FastAPI backend
 *  3. Poll until the backend is ready
 *  4. Open the main dashboard window; close the splash
 *  5. On quit, send SIGTERM to the backend process
 */

const { app, BrowserWindow, Menu, shell, dialog, ipcMain, clipboard } = require('electron')
const { spawn } = require('child_process')
const path  = require('path')
const http  = require('http')
const fs    = require('fs')

const BACKEND_PORT = 8000
const BACKEND_URL  = `http://127.0.0.1:${BACKEND_PORT}`
const IS_PACKAGED  = app.isPackaged

let mainWindow    = null
let loadingWindow = null
let backendProcess = null

// ── Path helpers ─────────────────────────────────────────────────────── //

/** Project root — different when packaged vs. dev */
function getResourcesPath() {
  return IS_PACKAGED ? process.resourcesPath : path.join(__dirname, '..')
}

/**
 * Where Platapicker stores its mutable data on this Mac.
 * e.g. ~/Library/Application Support/Platapicker
 */
function getDataDir() {
  return app.getPath('userData')
}

/**
 * Find the best Python 3 binary.
 * Priority:
 *   1. PLATAPICKER_PYTHON env var (user override)
 *   2. Bundled venv inside the .app (packaged only)
 *   3. Local project .venv (dev)
 *   4. Homebrew python3
 *   5. /usr/bin/python3 (system)
 */
function findPython() {
  if (process.env.PLATAPICKER_PYTHON) return process.env.PLATAPICKER_PYTHON

  const candidates = []

  if (IS_PACKAGED) {
    candidates.push(path.join(process.resourcesPath, '.venv', 'bin', 'python3'))
    candidates.push(path.join(process.resourcesPath, '.venv', 'bin', 'python'))
  } else {
    candidates.push(path.join(__dirname, '..', '.venv', 'bin', 'python3'))
    candidates.push(path.join(__dirname, '..', '.venv', 'bin', 'python'))
  }

  // Managed venv in user data dir (created by first-run setup)
  candidates.push(path.join(getDataDir(), 'venv', 'bin', 'python3'))

  // System / Homebrew
  const homebrew = process.arch === 'arm64'
    ? '/opt/homebrew/bin/python3'
    : '/usr/local/bin/python3'
  candidates.push(homebrew, '/usr/bin/python3', 'python3')

  for (const c of candidates) {
    if (!c.includes('/') || fs.existsSync(c)) return c
  }
  return 'python3'
}

// ── Backend ──────────────────────────────────────────────────────────── //

function startBackend() {
  const python    = findPython()
  const resources = getResourcesPath()
  const runScript = path.join(resources, 'run.py')
  const dataDir   = getDataDir()

  // Ensure data dir exists
  fs.mkdirSync(dataDir, { recursive: true })

  const frontendDist = IS_PACKAGED
    ? path.join(process.resourcesPath, 'frontend', 'dist')
    : path.join(resources, 'frontend', 'dist')

  const env = {
    ...process.env,
    PLATAPICKER_DATA_DIR : dataDir,
    DATABASE_URL         : `sqlite:///${path.join(dataDir, 'platapicker.db')}`,
    FRONTEND_DIST        : frontendDist,
    APP_HOST             : '127.0.0.1',
    APP_PORT             : String(BACKEND_PORT),
    // Suppress Python stdout buffering so logs flow immediately
    PYTHONUNBUFFERED     : '1',
  }

  console.log(`[electron] Python: ${python}`)
  console.log(`[electron] run.py: ${runScript}`)
  console.log(`[electron] data:   ${dataDir}`)

  backendProcess = spawn(python, [runScript], {
    cwd  : resources,
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
  })

  backendProcess.stdout.on('data', (d) =>
    process.stdout.write(`[backend] ${d}`)
  )
  backendProcess.stderr.on('data', (d) =>
    process.stderr.write(`[backend] ${d}`)
  )
  backendProcess.on('exit', (code, signal) => {
    console.log(`[backend] exited  code=${code} signal=${signal}`)
  })
  backendProcess.on('error', (err) => {
    console.error(`[backend] spawn error: ${err.message}`)
    showBackendError(
      `Could not start Python.\n\n` +
      `Tried: ${python}\n\n` +
      `Make sure Python 3.11+ is installed and the project .venv is set up:\n` +
      `  python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
    )
  })
}

function stopBackend() {
  if (backendProcess) {
    backendProcess.kill('SIGTERM')
    backendProcess = null
  }
}

/**
 * Poll the backend health endpoint until it responds or we give up.
 * Resolves when the backend is ready, rejects after maxRetries.
 */
function waitForBackend(maxRetries = 50, intervalMs = 400) {
  return new Promise((resolve, reject) => {
    let attempts = 0

    const check = () => {
      attempts++
      const req = http.get(`${BACKEND_URL}/api/overview`, (res) => {
        res.resume() // drain the response
        if (res.statusCode < 500) {
          resolve()
        } else {
          retry()
        }
      })
      req.on('error', retry)
      req.setTimeout(800, () => { req.destroy(); retry() })
    }

    const retry = () => {
      if (attempts < maxRetries) {
        setTimeout(check, intervalMs)
      } else {
        reject(new Error('Backend did not become ready in time'))
      }
    }

    check()
  })
}

// ── Windows ──────────────────────────────────────────────────────────── //

function getIconPath() {
  return path.join(getResourcesPath(), 'assets', 'icon.png')
}

function createLoadingWindow() {
  loadingWindow = new BrowserWindow({
    width          : 400,
    height         : 280,
    frame          : false,
    resizable      : false,
    center         : true,
    backgroundColor: '#0f1117',
    icon           : getIconPath(),
    webPreferences : { contextIsolation: true },
  })
  loadingWindow.loadFile(path.join(__dirname, 'loading.html'))
}

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width         : 1280,
    height        : 820,
    minWidth      : 960,
    minHeight     : 600,
    titleBarStyle : 'hiddenInset',   // native Mac traffic-lights, no title bar
    backgroundColor: '#0f1117',
    icon          : getIconPath(),
    show          : false,           // reveal only after content loads
    webPreferences: {
      preload          : path.join(__dirname, 'preload.js'),
      contextIsolation : true,
      nodeIntegration  : false,
    },
  })

  mainWindow.loadURL(BACKEND_URL)

  mainWindow.once('ready-to-show', () => {
    if (loadingWindow && !loadingWindow.isDestroyed()) {
      loadingWindow.close()
      loadingWindow = null
    }
    mainWindow.show()
    mainWindow.focus()
  })

  // Open external links (marketplace listings, Discord) in the default browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (!url.startsWith('http://127.0.0.1') && !url.startsWith('http://localhost')) {
      shell.openExternal(url)
    }
    return { action: 'deny' }
  })

  mainWindow.on('closed', () => { mainWindow = null })

  buildMenu()
}

function showBackendError(message) {
  // Update loading window if it's still open
  if (loadingWindow && !loadingWindow.isDestroyed()) {
    loadingWindow.webContents
      .executeJavaScript(`window.setStatus(${JSON.stringify(message)}, true)`)
      .catch(() => {})
  }
  // Also show a native dialog
  dialog.showErrorBox('Platapicker — Backend Error', message)
}

// ── Menu ─────────────────────────────────────────────────────────────── //

function buildMenu() {
  const template = [
    {
      label: app.name,
      submenu: [
        { role: 'about' },
        { type: 'separator' },
        {
          label: 'Open Data Folder',
          accelerator: 'CmdOrCtrl+Shift+D',
          click: () => shell.openPath(getDataDir()),
        },
        { type: 'separator' },
        { role: 'services' },
        { type: 'separator' },
        { role: 'hide' },
        { role: 'hideOthers' },
        { role: 'unhide' },
        { type: 'separator' },
        { role: 'quit' },
      ],
    },
    {
      label: 'Edit',
      submenu: [
        { role: 'undo' }, { role: 'redo' },
        { type: 'separator' },
        { role: 'cut' }, { role: 'copy' }, { role: 'paste' },
        { role: 'selectAll' },
      ],
    },
    {
      label: 'View',
      submenu: [
        { role: 'reload' },
        { role: 'forceReload' },
        { role: 'toggleDevTools' },
        { type: 'separator' },
        { role: 'resetZoom' },
        { role: 'zoomIn' },
        { role: 'zoomOut' },
        { type: 'separator' },
        { role: 'togglefullscreen' },
      ],
    },
    {
      label: 'Window',
      submenu: [
        { role: 'minimize' },
        { role: 'zoom' },
        { type: 'separator' },
        { role: 'front' },
        { type: 'separator' },
        { role: 'window' },
      ],
    },
  ]

  Menu.setApplicationMenu(Menu.buildFromTemplate(template))
}

// ── IPC handlers ────────────────────────────────────────────────────── //

ipcMain.handle('clipboard-write', (_event, text) => {
  clipboard.writeText(text)
})

ipcMain.handle('open-external', (_event, url) => {
  shell.openExternal(url)
})

// ── App lifecycle ────────────────────────────────────────────────────── //

app.whenReady().then(async () => {
  if (app.dock) app.dock.setIcon(getIconPath())
  createLoadingWindow()
  startBackend()

  try {
    await waitForBackend()
    createMainWindow()
  } catch (err) {
    console.error('[electron] Backend failed to start:', err.message)
    showBackendError(
      'The Platapicker backend failed to start.\n\n' +
      'Make sure Python 3.11+ is installed and dependencies are set up:\n\n' +
      '  cd ' + getResourcesPath() + '\n' +
      '  python3 -m venv .venv\n' +
      '  source .venv/bin/activate\n' +
      '  pip install -r requirements.txt\n\n' +
      err.message
    )
  }
})

app.on('window-all-closed', () => {
  stopBackend()
  // On macOS it's conventional to quit when all windows are closed
  app.quit()
})

app.on('before-quit', () => {
  stopBackend()
})

app.on('activate', () => {
  // Re-open window when dock icon is clicked and no windows are open
  if (BrowserWindow.getAllWindows().length === 0) {
    createMainWindow()
  }
})
