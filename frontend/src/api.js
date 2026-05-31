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
export const getClaudeReview = (id) => api.get(`/listings/${id}/claude-review`).then(r => r.data)
export const triggerClaudeReview = (id) => api.post(`/listings/${id}/claude-review`).then(r => r.data)

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

// ── Inventory (sell-side) ──────────────────────────────────
export const getInventory = (params = {}) => api.get('/inventory', { params }).then(r => r.data)
export const getInventoryItem = (id) => api.get(`/inventory/${id}`).then(r => r.data)
export const createInventoryItem = (data) => api.post('/inventory', data).then(r => r.data)
export const updateInventoryItem = (id, data) => api.patch(`/inventory/${id}`, data).then(r => r.data)
export const deleteInventoryItem = (id) => api.delete(`/inventory/${id}`).then(r => r.data)
export const uploadInventoryPhotos = (id, files) => {
  const form = new FormData()
  for (const f of files) form.append('files', f)
  return api.post(`/inventory/${id}/photos`, form).then(r => r.data)
}
export const deleteInventoryPhoto = (photoId) => api.delete(`/inventory/photos/${photoId}`).then(r => r.data)
export const reorderInventoryPhotos = (photoIds) => api.post('/inventory/photos/reorder', { photo_ids: photoIds }).then(r => r.data)
export const promoteListingToInventory = (listingId) => api.post(`/listings/${listingId}/promote-to-inventory`).then(r => r.data)
export const sendListingOutreach = (listingId) => api.post(`/listings/${listingId}/send-outreach`).then(r => r.data)
export const runFullPipeline = (listingId) => api.post(`/listings/${listingId}/full-pipeline`).then(r => r.data)

export const inventoryPhotoUrl = (photo) => `${BASE}${photo.url}`

export const triggerPriceSuggestion = (id) => api.post(`/inventory/${id}/price-suggestion`).then(r => r.data)
export const getPriceSuggestion = (id) => api.get(`/inventory/${id}/price-suggestion`).then(r => r.data)

export const analyzePhoto = (file, mode) => {
  const form = new FormData()
  form.append('file', file)
  return api.post('/analyze-photo', form, { params: { mode } }).then(r => r.data)
}

// ── Sell listings ─────────────────────────────────────────────
export const getSellListings = (itemId) => api.get(`/inventory/${itemId}/sell-listings`).then(r => r.data)
export const createSellListing = (itemId, data) => api.post(`/inventory/${itemId}/sell-listings`, data).then(r => r.data)
export const updateSellListing = (id, data) => api.patch(`/sell-listings/${id}`, data).then(r => r.data)
export const markSellListingSold = (id, data) => api.post(`/sell-listings/${id}/mark-sold`, data).then(r => r.data)
export const removeSellListing = (id) => api.post(`/sell-listings/${id}/remove`).then(r => r.data)

// ── Sell analytics ─────────────────────────────────────────
export const getSellDashboard = () => api.get('/sell/dashboard').then(r => r.data)
export const getSellProfit = (params = {}) => api.get('/sell/profit', { params }).then(r => r.data)

export default api
