/**
 * Preload script — runs in the renderer before the page loads.
 * contextIsolation is on, so we only expose what we explicitly bridge.
 */
const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('platapicker', {
  version: process.env.npm_package_version || '1.0.0',
  platform: process.platform,
  copyToClipboard: (text) => ipcRenderer.invoke('clipboard-write', text),
  openExternal: (url) => ipcRenderer.invoke('open-external', url),
})
