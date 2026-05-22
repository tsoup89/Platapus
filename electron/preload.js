/**
 * Preload script — runs in the renderer before the page loads.
 * contextIsolation is on, so we only expose what we explicitly bridge.
 * For now the dashboard is a plain web app that talks to the backend
 * via HTTP, so no IPC bridging is needed.
 */
const { contextBridge } = require('electron')

contextBridge.exposeInMainWorld('platapicker', {
  version: process.env.npm_package_version || '1.0.0',
  platform: process.platform,
})
