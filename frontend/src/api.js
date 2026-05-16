import axios from 'axios'

const BASE = import.meta.env.VITE_API_URL || ''

const api = axios.create({ baseURL: `${BASE}/api` })

export const getOverview = () => api.get('/overview').then(r => r.data)
export const getSources = () => api.get('/sources').then(r => r.data)
export const getSourceRuns = (name, limit = 20) => api.get(`/sources/${name}/runs`, { params: { limit } }).then(r => r.data)
export const triggerRun = (source) => api.post(`/sources/${source}/run`).then(r => r.data)
export const runAll = () => api.post('/run-all').then(r => r.data)
export const toggleSource = (name) => api.post(`/sources/${name}/toggle`).then(r => r.data)

export const getWatchlists = () => api.get('/watchlists').then(r => r.data)
export const getWatchlist = (id) => api.get(`/watchlists/${id}`).then(r => r.data)
export const createWatchlist = (data) => api.post('/watchlists', data).then(r => r.data)
export const updateWatchlist = (id, data) => api.put(`/watchlists/${id}`, data).then(r => r.data)
export const deleteWatchlist = (id) => api.delete(`/watchlists/${id}`).then(r => r.data)
export const toggleWatchlist = (id) => api.post(`/watchlists/${id}/toggle`).then(r => r.data)

export const getListings = (params = {}) => api.get('/listings', { params }).then(r => r.data)
export const ignoreListing = (id) => api.post(`/listings/${id}/ignore`).then(r => r.data)
export const unignoreListing = (id) => api.post(`/listings/${id}/unignore`).then(r => r.data)
export const sendDiscord = (id) => api.post(`/listings/${id}/send-discord`).then(r => r.data)
export const getListingRaw = (id) => api.get(`/listings/${id}/raw`).then(r => r.data)

export const getWebhooks = () => api.get('/webhooks').then(r => r.data)
export const createWebhook = (data) => api.post('/webhooks', data).then(r => r.data)
export const deleteWebhook = (id) => api.delete(`/webhooks/${id}`).then(r => r.data)
export const testWebhook = (id) => api.post(`/webhooks/${id}/test`).then(r => r.data)

export const getGCPrices = (params = {}) => api.get('/gamecube/prices', { params }).then(r => r.data)
export const updateGCPrice = (id, data) => api.put(`/gamecube/prices/${id}`, data).then(r => r.data)
export const importGCCSV = (file) => {
  const form = new FormData()
  form.append('file', file)
  return api.post('/gamecube/import', form).then(r => r.data)
}
export const getUnmatched = () => api.get('/gamecube/unmatched').then(r => r.data)

export const getSettings = () => api.get('/settings').then(r => r.data)
export const updateSettings = (data) => api.post('/settings', data).then(r => r.data)

export const clearDuplicates = () => api.post('/maintenance/clear-duplicates').then(r => r.data)
export const resetAlerts = () => api.post('/maintenance/reset-alerts').then(r => r.data)
export const rescoreGamecube = () => api.post('/maintenance/rescore-gamecube').then(r => r.data)

export const getSchedulerStatus = () => api.get('/scheduler/status').then(r => r.data)
export const runAllNow = () => api.post('/scheduler/run-now').then(r => r.data)
export const reschedule = (minutes) => api.post('/scheduler/reschedule', null, { params: { interval_minutes: minutes } }).then(r => r.data)

export const getFBSessionStatus = () => api.get('/facebook/session-status').then(r => r.data)
export const fbDebugScrape = (keyword) => api.post('/facebook/debug-scrape', null, { params: { keyword } }).then(r => r.data)

export const updateSourceConfig = (name, config) => api.post(`/sources/${name}/update-config`, config).then(r => r.data)

export const syncPriceCharting = (maxTitles = 50) => api.post('/gamecube/sync-pricecharting', null, { params: { max_titles: maxTitles } }).then(r => r.data)
export const getSyncStatus = () => api.get('/gamecube/sync-status').then(r => r.data)

export default api
