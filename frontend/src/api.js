const API_BASE = '/api/v1'

async function fetchJson(url, options = {}) {
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  })
  
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(error.detail || 'Request failed')
  }
  
  if (res.status === 204) return null
  return res.json()
}

export const api = {
  // ============== Organizations ==============
  listOrgs: () => fetchJson(`${API_BASE}/orgs`),
  getOrg: (orgId) => fetchJson(`${API_BASE}/orgs/${orgId}`),
  createOrg: (name, description) => fetchJson(`${API_BASE}/orgs`, {
    method: 'POST',
    body: JSON.stringify({ name, description }),
  }),
  deleteOrg: (orgId) => fetchJson(`${API_BASE}/orgs/${orgId}`, { method: 'DELETE' }),

  // ============== Explore APIs (org-scoped) ==============
  // List repos for an org with optional regex search
  listReposForOrg: (orgId, { search, limit = 100, offset = 0 } = {}) => {
    const params = new URLSearchParams()
    if (search) params.append('search', search)
    params.append('limit', limit)
    params.append('offset', offset)
    return fetchJson(`${API_BASE}/orgs/${orgId}/repos?${params.toString()}`)
  },

  // List entry points for a repo (org-scoped) with optional regex search
  listEntryPointsForRepo: (orgId, repoId, { search, limit = 100, offset = 0 } = {}) => {
    const params = new URLSearchParams()
    if (search) params.append('search', search)
    params.append('limit', limit)
    params.append('offset', offset)
    return fetchJson(`${API_BASE}/orgs/${orgId}/repos/${repoId}/entry-points?${params.toString()}`)
  },

  // Get flows for a list of entry point IDs
  getFlowsForEntryPoints: (orgId, repoId, entryPointIds) =>
    fetchJson(`${API_BASE}/orgs/${orgId}/repos/${repoId}/flows`, {
      method: 'POST',
      body: JSON.stringify({ entry_point_ids: entryPointIds }),
    }),

  // List files for a repo (org-scoped) with optional regex search
  listFilesForRepo: (orgId, repoId, { search, limit = 100, offset = 0 } = {}) => {
    const params = new URLSearchParams()
    if (search) params.append('search', search)
    params.append('limit', limit)
    params.append('offset', offset)
    return fetchJson(`${API_BASE}/orgs/${orgId}/repos/${repoId}/files?${params.toString()}`)
  },

  // Get file detail (org-scoped)
  getFileDetail: (orgId, repoId, fileId) =>
    fetchJson(`${API_BASE}/orgs/${orgId}/repos/${repoId}/files/${fileId}`),

  // ============== Repositories (legacy + new) ==============
  listRepos: () => fetchJson(`${API_BASE}/repos`),
  getRepo: (id) => fetchJson(`${API_BASE}/repos/${id}`),
  createRepo: (path, name, orgId) => fetchJson(`${API_BASE}/repos`, {
    method: 'POST',
    body: JSON.stringify({ path, name, org_id: orgId || undefined }),
  }),
  deleteRepo: (id) => fetchJson(`${API_BASE}/repos/${id}`, { method: 'DELETE' }),
  reparseRepo: (id) => fetchJson(`${API_BASE}/repos/${id}/parse`, { method: 'POST' }),

  // Stats
  getRepoStats: (repoId) => fetchJson(`${API_BASE}/repos/${repoId}/stats`),

  // Files
  listFiles: (repoId, limit = 100, offset = 0) => 
    fetchJson(`${API_BASE}/repos/${repoId}/files?limit=${limit}&offset=${offset}`),

  // Symbols
  listSymbols: (repoId, kind, limit = 100, offset = 0) => {
    let url = `${API_BASE}/repos/${repoId}/symbols?limit=${limit}&offset=${offset}`
    if (kind) url += `&kind=${kind}`
    return fetchJson(url)
  },
  getSymbol: (repoId, symbolId) => 
    fetchJson(`${API_BASE}/repos/${repoId}/symbols/${symbolId}`),
  searchSymbols: (repoId, query) => 
    fetchJson(`${API_BASE}/repos/${repoId}/symbols/search?q=${encodeURIComponent(query)}`),
  getSymbolsInFile: (repoId, fileId) =>
    fetchJson(`${API_BASE}/repos/${repoId}/files/${fileId}/symbols`),

  // Graph
  getDownstream: (repoId, symbolId, maxDepth = 5) =>
    fetchJson(`${API_BASE}/repos/${repoId}/symbols/${symbolId}/downstream?max_depth=${maxDepth}`),
  getUpstream: (repoId, symbolId, maxDepth = 5) =>
    fetchJson(`${API_BASE}/repos/${repoId}/symbols/${symbolId}/upstream?max_depth=${maxDepth}`),
  getContext: (repoId, symbolId) =>
    fetchJson(`${API_BASE}/repos/${repoId}/symbols/${symbolId}/context`),

  // Symbol Details
  getSymbolDetails: (repoId, pathName, symbolName, depth = 0) =>
    fetchJson(`${API_BASE}/repos/${repoId}/symbols/details`, {
      method: 'POST',
      body: JSON.stringify({ path_name: pathName, symbol_name: symbolName, depth }),
    }),

  // Entry Points
  detectEntryPoints: (repoId, forceRedetect = false) =>
    fetchJson(`${API_BASE}/repos/${repoId}/entry-points/detect`, {
      method: 'POST',
      body: JSON.stringify({ force_redetect: forceRedetect }),
    }),
  listEntryPoints: (repoId, entryPointType, framework) => {
    let url = `${API_BASE}/repos/${repoId}/entry-points`
    const params = new URLSearchParams()
    if (entryPointType) params.append('entry_point_type', entryPointType)
    if (framework) params.append('framework', framework)
    if (params.toString()) url += `?${params.toString()}`
    return fetchJson(url)
  },
  getEntryPoint: (repoId, entryPointId) =>
    fetchJson(`${API_BASE}/repos/${repoId}/entry-points/${entryPointId}`),
  listEntryPointCandidates: (repoId) =>
    fetchJson(`${API_BASE}/repos/${repoId}/entry-points/candidates`),

  // Entry Point Flows
  generateFlow: (repoId, entryPointId) =>
    fetchJson(`${API_BASE}/repos/${repoId}/entry-points/${entryPointId}/generate-flow`, {
      method: 'POST',
    }),
  getFlow: (repoId, entryPointId) =>
    fetchJson(`${API_BASE}/repos/${repoId}/entry-points/${entryPointId}/flow`),
}
