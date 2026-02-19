import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useInfiniteQuery } from '@tanstack/react-query'
import { 
  ArrowLeft, Search, FileCode, Box, Braces, FunctionSquare, 
  Import, Loader2, ChevronRight, BarChart3, Crosshair, FolderTree, Zap,
  Route, Sparkles, CheckCircle, AlertCircle, GitBranch, Code, FileText, Clock
} from 'lucide-react'
import { api } from '../api'
import { TreeView, FolderStructureView } from '../components/TreeView'

const kindConfig = {
  function: { icon: FunctionSquare, color: 'text-purple-400', colorOnDark: 'text-purple-300' },
  method: { icon: FunctionSquare, color: 'text-purple-400', colorOnDark: 'text-purple-300' },
  class: { icon: Box, color: 'text-yellow-400', colorOnDark: 'text-yellow-300' },
  module: { icon: FileCode, color: 'text-blue-400', colorOnDark: 'text-blue-300' },
  import: { icon: Import, color: 'text-green-400', colorOnDark: 'text-green-300' },
  interface: { icon: Braces, color: 'text-cyan-400', colorOnDark: 'text-cyan-300' },
  struct: { icon: Box, color: 'text-orange-400', colorOnDark: 'text-orange-300' },
  trait: { icon: Braces, color: 'text-pink-400', colorOnDark: 'text-pink-300' },
  enum: { icon: Braces, color: 'text-amber-400', colorOnDark: 'text-amber-300' },
  impl: { icon: Box, color: 'text-indigo-400', colorOnDark: 'text-indigo-300' },
}

function KindIcon({ kind, onDark }) {
  const config = kindConfig[kind] || { icon: Box, color: 'text-surface-400', colorOnDark: 'text-surface-300' }
  const Icon = config.icon
  const colorClass = onDark ? (config.colorOnDark || config.color) : config.color
  return <Icon size={16} className={colorClass} />
}

const kindOptions = [
  { value: '', label: 'All Kinds' },
  { value: 'function', label: 'Functions' },
  { value: 'method', label: 'Methods' },
  { value: 'class', label: 'Classes' },
  { value: 'import', label: 'Imports' },
  { value: 'interface', label: 'Interfaces' },
  { value: 'struct', label: 'Structs' },
  { value: 'trait', label: 'Traits' },
  { value: 'enum', label: 'Enums' },
]

const PAGE_SIZE = 100

export default function RepoDetail() {
  const { repoId, orgId } = useParams()
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedKind, setSelectedKind] = useState('')
  const [activeTab, setActiveTab] = useState('symbols')
  const [detectingEntryPoints, setDetectingEntryPoints] = useState(false)
  const [generatingFlows, setGeneratingFlows] = useState(new Set())
  const [expandedFlows, setExpandedFlows] = useState(new Set())
  
  // Compute base paths for org-aware navigation
  const backLink = orgId ? `/orgs/${orgId}` : '/repos'
  const backLabel = orgId ? 'Back to organization' : 'Back to repositories'
  const repoBasePath = orgId ? `/orgs/${orgId}/repos/${repoId}` : `/repos/${repoId}`
  
  const { data: repo } = useQuery({
    queryKey: ['repo', repoId],
    queryFn: () => api.getRepo(repoId),
  })
  
  const { data: stats } = useQuery({
    queryKey: ['stats', repoId],
    queryFn: () => api.getRepoStats(repoId),
  })
  
  // Infinite query for paginated symbols
  const {
    data: symbolsData,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading: symbolsLoading,
  } = useInfiniteQuery({
    queryKey: ['symbols', repoId, selectedKind],
    queryFn: ({ pageParam = 0 }) => 
      api.listSymbols(repoId, selectedKind || undefined, PAGE_SIZE, pageParam),
    getNextPageParam: (lastPage, allPages) => {
      if (lastPage.length < PAGE_SIZE) return undefined
      return allPages.length * PAGE_SIZE
    },
    enabled: activeTab === 'symbols' && !searchQuery,
  })
  
  const { data: searchResults, isLoading: searchLoading } = useQuery({
    queryKey: ['search', repoId, searchQuery],
    queryFn: () => api.searchSymbols(repoId, searchQuery),
    enabled: searchQuery.length >= 2,
  })
  
  const { data: files } = useQuery({
    queryKey: ['files', repoId],
    queryFn: () => api.listFiles(repoId, 500),
    enabled: activeTab === 'files' || activeTab === 'tree',
  })
  
  const { data: entryPoints, refetch: refetchEntryPoints } = useQuery({
    queryKey: ['entryPoints', repoId],
    queryFn: () => api.listEntryPoints(repoId),
    enabled: activeTab === 'entry-points',
  })
  
  const { data: entryPointCandidates, refetch: refetchCandidates } = useQuery({
    queryKey: ['entryPointCandidates', repoId],
    queryFn: () => api.listEntryPointCandidates(repoId),
    enabled: activeTab === 'entry-points',
  })
  
  const handleGenerateFlow = async (entryPointId) => {
    setGeneratingFlows(prev => new Set(prev).add(entryPointId))
    try {
      await api.generateFlow(repoId, entryPointId)
      // Auto-expand and start polling for the flow
      setExpandedFlows(prev => new Set(prev).add(entryPointId))
      alert('Flow generation started! This may take a few moments. The flow will appear automatically when ready.')
    } catch (error) {
      alert(`Error generating flow: ${error.message}`)
    } finally {
      setTimeout(() => {
        setGeneratingFlows(prev => {
          const next = new Set(prev)
          next.delete(entryPointId)
          return next
        })
      }, 1000)
    }
  }
  
  const toggleFlowExpansion = (entryPointId) => {
    setExpandedFlows(prev => {
      const next = new Set(prev)
      if (next.has(entryPointId)) {
        next.delete(entryPointId)
      } else {
        next.add(entryPointId)
      }
      return next
    })
  }
  
  // Entry Point Item Component (can use hooks)
  function EntryPointItem({ ep, isGenerating, isExpanded, onGenerateFlow, onToggleFlow }) {
    const flowQuery = useQuery({
      queryKey: ['flow', repoId, ep.id],
      queryFn: () => api.getFlow(repoId, ep.id),
      enabled: isExpanded,
      retry: false,
      // Poll for flow if expanded but not found (generation in progress)
      refetchInterval: (query) => {
        // Poll every 3 seconds if flow doesn't exist yet and we're expanded
        if (isExpanded && !query.data && !query.isError) {
          return 3000
        }
        return false
      },
    })
    
    const flow = flowQuery?.data
    
    return (
      <div className="bg-surface-900 border border-surface-800 rounded-lg p-5 hover:border-accent-500/50 transition-colors">
        <div className="flex items-start justify-between mb-3">
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-2">
              <CheckCircle size={18} className="text-green-400" />
              <h3 className="text-lg font-semibold">{ep.name}</h3>
              <span className="px-2 py-1 bg-accent-600/20 text-accent-400 rounded text-xs font-medium">
                {ep.entry_point_type.toUpperCase()}
              </span>
              <span className="px-2 py-1 bg-surface-800 text-surface-300 rounded text-xs font-medium">
                {ep.framework}
              </span>
            </div>
            <p className="text-surface-300 mb-3">{ep.description}</p>
            {ep.metadata && ep.metadata.path && (
              <div className="flex items-center gap-4 text-sm">
                <div className="flex items-center gap-2">
                  <Route size={14} className="text-surface-500" />
                  <span className="font-mono text-accent-400">{ep.metadata.path}</span>
                </div>
                {ep.metadata.method && ep.metadata.method !== 'route' && (
                  <span className="px-2 py-1 bg-surface-800 rounded text-xs">
                    {ep.metadata.method.toUpperCase()}
                  </span>
                )}
                <span className="text-surface-500">
                  Confidence: {(ep.ai_confidence * 100).toFixed(0)}%
                </span>
              </div>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => onGenerateFlow(ep.id)}
              disabled={isGenerating}
              className="flex items-center gap-2 px-3 py-1.5 bg-accent-600 hover:bg-accent-500 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              title="Generate flow documentation"
            >
              {isGenerating ? (
                <>
                  <Loader2 className="animate-spin" size={14} />
                  Generating...
                </>
              ) : (
                <>
                  <GitBranch size={14} />
                  Generate Flow
                </>
              )}
            </button>
            <button
              onClick={() => onToggleFlow(ep.id)}
              className="flex items-center gap-2 px-3 py-1.5 bg-surface-800 hover:bg-surface-700 rounded-lg text-sm font-medium transition-colors"
            >
              <FileText size={14} />
              {isExpanded ? 'Hide Flow' : 'View Flow'}
            </button>
          </div>
        </div>
        {ep.ai_reasoning && (
          <div className="mt-3 pt-3 border-t border-surface-800">
            <p className="text-xs text-surface-500 italic">
              {ep.ai_reasoning}
            </p>
          </div>
        )}
        
        {/* Flow Documentation */}
        {isExpanded && flow && (
          <div className="mt-4 pt-4 border-t border-surface-800">
            <div className="mb-4">
              <h4 className="text-md font-semibold mb-2 flex items-center gap-2">
                <GitBranch size={16} className="text-accent-400" />
                {flow.flow_name}
              </h4>
              <div className="flex items-center gap-4 text-sm text-surface-400 mb-3">
                <span className="flex items-center gap-1">
                  <Clock size={14} />
                  Depth: {flow.max_depth_analyzed} • Iterations: {flow.iterations_completed}
                </span>
                <span className="flex items-center gap-1">
                  <Code size={14} />
                  {flow.symbol_ids_analyzed.length} symbols analyzed
                </span>
              </div>
              
              {/* File Paths */}
              {flow.file_paths && flow.file_paths.length > 0 && (
                <div className="bg-surface-800 rounded-lg p-4 mb-4">
                  <h5 className="text-sm font-medium text-surface-300 mb-2 flex items-center gap-2">
                    <FileCode size={14} />
                    Files Involved ({flow.file_paths.length})
                  </h5>
                  <div className="flex flex-wrap gap-2">
                    {flow.file_paths.map((filePath, idx) => (
                      <span 
                        key={idx}
                        className="px-2 py-1 bg-surface-900 rounded text-xs font-mono text-surface-300"
                        title={filePath}
                      >
                        {filePath}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              
              <div className="bg-surface-800 rounded-lg p-4 mb-4">
                <h5 className="text-sm font-medium text-surface-300 mb-2">Technical Summary</h5>
                <p className="text-sm text-surface-400 whitespace-pre-wrap">{flow.technical_summary}</p>
              </div>
            </div>
            
            {/* Flow Steps */}
            <div className="space-y-3">
              <h5 className="text-sm font-medium text-surface-300 mb-3">Flow Steps</h5>
              {flow.steps.map((step, idx) => (
                <div key={idx} className="bg-surface-800 rounded-lg p-4">
                  <div className="flex items-start gap-3 mb-3">
                    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-accent-600/20 text-accent-400 flex items-center justify-center text-sm font-semibold">
                      {step.step_number}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <h6 className="text-sm font-semibold text-surface-200">{step.title}</h6>
                        {step.file_path && (
                          <span className="px-2 py-0.5 bg-surface-900 rounded text-xs font-mono text-surface-400" title={step.file_path}>
                            <FileCode size={10} className="inline mr-1" />
                            {step.file_path}
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-surface-400 mb-3">{step.description}</p>
                      
                      {/* Log Lines */}
                      {step.important_log_lines && step.important_log_lines.length > 0 && (
                        <div className="mb-3">
                          <div className="text-xs font-medium text-surface-500 mb-1">Important Log Lines:</div>
                          <div className="space-y-1">
                            {step.important_log_lines.map((logLine, logIdx) => (
                              <div key={logIdx} className="font-mono text-xs bg-surface-900 px-2 py-1 rounded text-accent-300">
                                {logLine}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      
                      {/* Code Snippets */}
                      {step.important_code_snippets && step.important_code_snippets.length > 0 && (
                        <div>
                          <div className="text-xs font-medium text-surface-500 mb-2">Important Code Snippets:</div>
                          <div className="space-y-2">
                            {step.important_code_snippets.map((snippet, snippetIdx) => (
                              <div key={snippetIdx} className="bg-surface-900 rounded p-3">
                                <div className="flex items-center gap-2 mb-2 text-xs text-surface-500">
                                  <FileCode size={12} />
                                  <span className="font-mono">{snippet.file_path}</span>
                                  <span className="text-surface-600">•</span>
                                  <span>{snippet.symbol_name}</span>
                                  {snippet.line_range && (
                                    <>
                                      <span className="text-surface-600">•</span>
                                      <span>Lines {snippet.line_range.start}-{snippet.line_range.end}</span>
                                    </>
                                  )}
                                </div>
                                <pre className="text-xs text-surface-300 overflow-x-auto">
                                  <code>{snippet.code}</code>
                                </pre>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
        
        {/* Flow Loading State */}
        {isExpanded && flowQuery?.isLoading && (
          <div className="mt-4 pt-4 border-t border-surface-800">
            <div className="flex items-center gap-2 text-surface-400">
              <Loader2 className="animate-spin" size={16} />
              <span className="text-sm">Loading flow documentation...</span>
            </div>
          </div>
        )}
        
        {/* Flow Error State */}
        {isExpanded && flowQuery?.isError && !flow && (
          <div className="mt-4 pt-4 border-t border-surface-800">
            <div className="bg-yellow-900/20 border border-yellow-800 rounded-lg p-3">
              <div className="flex items-center gap-2 text-yellow-400 text-sm">
                <AlertCircle size={16} />
                <span>Flow documentation not found. Click "Generate Flow" to create it.</span>
              </div>
            </div>
          </div>
        )}
      </div>
    )
  }
  
  const handleDetectEntryPoints = async (forceRedetect = false) => {
    if (!forceRedetect && entryPoints && entryPoints.length > 0) {
      if (!confirm('Entry points already exist. Do you want to re-detect and replace them?')) {
        return
      }
      forceRedetect = true
    }
    
    setDetectingEntryPoints(true)
    try {
      const result = await api.detectEntryPoints(repoId, forceRedetect)
      alert(`Entry point detection completed!\n\nCandidates detected: ${result.candidates_detected}\nEntry points confirmed: ${result.entry_points_confirmed}\nFrameworks: ${result.frameworks_detected.join(', ')}`)
      refetchEntryPoints()
      refetchCandidates()
    } catch (error) {
      alert(`Error detecting entry points: ${error.message}`)
    } finally {
      setDetectingEntryPoints(false)
    }
  }
  
  
  // Flatten paginated symbols
  const symbols = symbolsData?.pages?.flat() || []
  const displaySymbols = searchQuery.length >= 2 ? searchResults : symbols
  const isLoading = searchQuery.length >= 2 ? searchLoading : symbolsLoading
  
  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <Link 
          to={backLink} 
          className="inline-flex items-center gap-2 text-surface-400 hover:text-white mb-4 transition-colors"
        >
          <ArrowLeft size={16} />
          {backLabel}
        </Link>
        
        {repo && (
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-2xl font-bold">{repo.name}</h1>
              {repo.description && (
                <p className="text-surface-300 text-sm mt-1">{repo.description}</p>
              )}
              <p className="text-surface-400 font-mono text-sm mt-1">{repo.root_path}</p>
              <p className="text-surface-500 text-sm mt-2">
                {repo.total_files} files • {repo.status}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={async () => {
                  if (confirm('This will re-parse the repository. Continue?')) {
                    try {
                      await api.reparseRepo(repoId)
                      alert('Re-parsing started! The page will refresh when complete.')
                      setTimeout(() => window.location.reload(), 2000)
                    } catch (error) {
                      alert(`Error: ${error.message}`)
                    }
                  }
                }}
                className="flex items-center gap-2 px-4 py-2 bg-white border-2 border-surface-300 hover:border-surface-500 hover:bg-surface-100 rounded-lg font-semibold text-surface-800 transition-colors text-sm shadow-sm"
              >
                <Zap size={16} />
                Re-parse
              </button>
              <Link
                to={`${repoBasePath}/lookup`}
                className="flex items-center gap-2 px-4 py-2 bg-accent-600 hover:bg-accent-500 text-white rounded-lg font-semibold transition-colors text-sm shadow-sm"
              >
                <Crosshair size={16} />
                Symbol Lookup
              </Link>
            </div>
          </div>
        )}
      </div>
      
      {/* Stats Cards */}
      {stats && (
        <div className="mb-6 grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-surface-900 border border-surface-700 rounded-xl p-4 shadow-sm">
            <div className="flex items-center gap-2 text-surface-300 text-sm mb-1">
              <BarChart3 size={14} className="text-accent-400" />
              Total Symbols
            </div>
            <p className="text-2xl font-bold text-accent-400">{stats.total.toLocaleString()}</p>
          </div>
          
          {Object.entries(stats.by_kind).slice(0, 3).map(([kind, count]) => (
            <div key={kind} className="bg-surface-900 border border-surface-700 rounded-xl p-4 shadow-sm">
              <div className="flex items-center gap-2 text-surface-300 text-sm mb-1">
                <KindIcon kind={kind} onDark />
                {kind.charAt(0).toUpperCase() + kind.slice(1)}s
              </div>
              <p className="text-2xl font-bold text-white">{count.toLocaleString()}</p>
            </div>
          ))}
        </div>
      )}

      {/* Repository Languages */}
      {repo && repo.languages && repo.languages.length > 0 && (
        <div className="mb-6 bg-surface-900 border border-surface-700 rounded-xl p-4 shadow-sm">
          <h3 className="text-sm font-medium text-surface-300 mb-3">Detected Languages</h3>
          <div className="flex flex-wrap gap-2">
            {repo.languages.map((lang) => (
              <span 
                key={lang} 
                className="px-3 py-1.5 bg-accent-500/25 text-accent-300 border border-accent-500/40 rounded-full text-sm font-medium"
              >
                {lang}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Language breakdown */}
      {stats && stats.by_language && Object.keys(stats.by_language).length > 0 && (
        <div className="mb-6 bg-surface-900 border border-surface-700 rounded-xl p-4 shadow-sm">
          <h3 className="text-sm font-medium text-surface-300 mb-3">Symbols by Language</h3>
          <div className="flex flex-wrap gap-3">
            {Object.entries(stats.by_language).map(([lang, count]) => (
              <span key={lang} className="px-3 py-1.5 bg-surface-800 border border-surface-600 rounded-full text-sm text-surface-100">
                <span className="font-medium">{lang}</span>
                <span className="text-surface-400 ml-2">{count.toLocaleString()}</span>
              </span>
            ))}
          </div>
        </div>
      )}
      
      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b border-surface-300">
        <button
          onClick={() => setActiveTab('symbols')}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px ${
            activeTab === 'symbols'
              ? 'border-accent-500 text-accent-600'
              : 'border-transparent text-surface-600 hover:text-surface-900 hover:border-surface-400'
          }`}
        >
          Symbols
        </button>
        <button
          onClick={() => setActiveTab('files')}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px ${
            activeTab === 'files'
              ? 'border-accent-500 text-accent-600'
              : 'border-transparent text-surface-600 hover:text-surface-900 hover:border-surface-400'
          }`}
        >
          Files
        </button>
        <button
          onClick={() => setActiveTab('tree')}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px ${
            activeTab === 'tree'
              ? 'border-accent-500 text-accent-600'
              : 'border-transparent text-surface-600 hover:text-surface-900 hover:border-surface-400'
          }`}
        >
          <span className="flex items-center gap-2">
            <FolderTree size={14} />
            Repository Tree
          </span>
        </button>
        <button
          onClick={() => setActiveTab('entry-points')}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px ${
            activeTab === 'entry-points'
              ? 'border-accent-500 text-accent-600'
              : 'border-transparent text-surface-600 hover:text-surface-900 hover:border-surface-400'
          }`}
        >
          <span className="flex items-center gap-2">
            <Route size={14} />
            Entry Points
            {entryPoints && entryPoints.length > 0 && (
              <span className="px-1.5 py-0.5 bg-accent-600 rounded text-xs">
                {entryPoints.length}
              </span>
            )}
          </span>
        </button>
      </div>
      
      {activeTab === 'symbols' && (
        <>
          {/* Search & Filter */}
          <div className="flex gap-4 mb-6">
            <div className="relative flex-1">
              <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search symbols..."
                className="w-full bg-surface-100 border border-surface-300 rounded-lg pl-10 pr-4 py-2.5 text-sm text-surface-900 placeholder:text-surface-500 focus:outline-none focus:border-accent-500 focus:ring-2 focus:ring-accent-500/20 transition-colors"
              />
            </div>
            
            <select
              value={selectedKind}
              onChange={(e) => setSelectedKind(e.target.value)}
              className="bg-surface-100 border border-surface-300 rounded-lg px-4 py-2.5 text-sm text-surface-900 focus:outline-none focus:border-accent-500 focus:ring-2 focus:ring-accent-500/20"
            >
              {kindOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>
          
          {/* Showing count */}
          {displaySymbols && displaySymbols.length > 0 && (
            <p className="text-sm text-surface-500 mb-4">
              Showing {displaySymbols.length.toLocaleString()} 
              {stats && !searchQuery && ` of ${stats.total.toLocaleString()}`} symbols
            </p>
          )}
          
          {/* Symbols List */}
          {isLoading && (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="animate-spin text-accent-400" size={32} />
            </div>
          )}
          
          {displaySymbols && displaySymbols.length === 0 && (
            <p className="text-center py-12 text-surface-400">No symbols found</p>
          )}
          
          {displaySymbols && displaySymbols.length > 0 && (
            <div className="space-y-1">
              {displaySymbols.map((symbol) => (
                <Link
                  key={symbol.id}
                  to={`${repoBasePath}/symbols/${symbol.id}`}
                  className="flex items-center gap-3 p-3 rounded-lg hover:bg-surface-900 transition-colors group"
                >
                  <KindIcon kind={symbol.kind} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{symbol.name}</span>
                      <span className="text-xs text-surface-200 px-2 py-0.5 bg-surface-700 border border-surface-600 rounded font-medium">
                        {symbol.kind}
                      </span>
                    </div>
                    <p className="text-sm text-surface-500 font-mono truncate">
                      {symbol.qualified_name}
                    </p>
                  </div>
                  <ChevronRight size={16} className="text-surface-600 group-hover:text-surface-400" />
                </Link>
              ))}
              
              {/* Load More Button */}
              {!searchQuery && hasNextPage && (
                <div className="pt-4 text-center">
                  <button
                    onClick={() => fetchNextPage()}
                    disabled={isFetchingNextPage}
                    className="px-6 py-2.5 bg-surface-800 hover:bg-surface-700 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
                  >
                    {isFetchingNextPage ? (
                      <span className="flex items-center gap-2">
                        <Loader2 className="animate-spin" size={16} />
                        Loading...
                      </span>
                    ) : (
                      'Load More'
                    )}
                  </button>
                </div>
              )}
            </div>
          )}
        </>
      )}
      
      {activeTab === 'files' && files && (
        <div className="space-y-4">
          {files.map((file) => (
            <div
              key={file.id}
              className="bg-surface-900 border border-surface-800 rounded-lg p-4"
            >
              <div className="flex items-center gap-3 mb-3">
                <FileCode size={16} className="text-accent-400" />
                <div className="flex-1 min-w-0">
                  <p className="font-mono text-sm text-white truncate">{file.relative_path}</p>
                  <p className="text-xs text-surface-500 mt-1">{file.language}</p>
                </div>
              </div>
              
              {file.folder_structure && (
                <div>
                  <h4 className="text-xs font-medium text-surface-400 mb-2">Folder Structure:</h4>
                  <FolderStructureView structure={file.folder_structure} />
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      
      {activeTab === 'tree' && repo && (
        <div>
          {repo.repo_tree ? (
            <div className="bg-surface-900 border border-surface-800 rounded-lg p-6">
              <h3 className="text-sm font-medium text-surface-400 mb-4 flex items-center gap-2">
                <FolderTree size={16} />
                Complete Repository Structure
              </h3>
              <div className="max-h-[600px] overflow-y-auto">
                <TreeView tree={repo.repo_tree} />
              </div>
            </div>
          ) : (
            <div className="bg-surface-900 border border-surface-800 rounded-lg p-6 text-center">
              <FolderTree size={32} className="mx-auto text-surface-600 mb-3" />
              <p className="text-surface-400 mb-4">
                Repository tree structure not available. This repository was parsed before the tree feature was added.
              </p>
              <button
                onClick={async () => {
                  if (confirm('This will re-parse the repository to generate the tree structure. Continue?')) {
                    try {
                      await api.reparseRepo(repoId)
                      alert('Re-parsing started! The page will refresh when complete.')
                      setTimeout(() => window.location.reload(), 2000)
                    } catch (error) {
                      alert(`Error: ${error.message}`)
                    }
                  }
                }}
                className="px-4 py-2 bg-accent-600 hover:bg-accent-500 rounded-lg text-sm font-medium transition-colors"
              >
                Re-parse Repository
              </button>
            </div>
          )}
        </div>
      )}
      
      {activeTab === 'entry-points' && (
        <div>
          {/* Header with detect button */}
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-lg font-semibold mb-1">Entry Points</h2>
              <p className="text-sm text-surface-400">
                HTTP endpoints, event handlers, and scheduled tasks detected in this repository
              </p>
            </div>
            <button
              onClick={() => handleDetectEntryPoints(entryPoints && entryPoints.length > 0)}
              disabled={detectingEntryPoints}
              className="flex items-center gap-2 px-4 py-2 bg-accent-600 hover:bg-accent-500 rounded-lg font-medium transition-colors text-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {detectingEntryPoints ? (
                <>
                  <Loader2 className="animate-spin" size={16} />
                  Detecting...
                </>
              ) : (
                <>
                  <Sparkles size={16} />
                  {entryPoints && entryPoints.length > 0 ? 'Re-detect Entry Points' : 'Detect Entry Points'}
                </>
              )}
            </button>
          </div>
          
          {/* Entry Points List */}
          {!entryPoints && (
            <div className="bg-surface-900 border border-surface-800 rounded-lg p-12 text-center">
              <Route size={48} className="mx-auto text-surface-600 mb-4" />
              <h3 className="text-lg font-semibold mb-2">No Entry Points Detected</h3>
              <p className="text-surface-400 mb-6">
                Click "Detect Entry Points" to scan this repository for HTTP endpoints, event handlers, and scheduled tasks.
              </p>
              <button
                onClick={() => handleDetectEntryPoints(false)}
                disabled={detectingEntryPoints}
                className="px-6 py-3 bg-accent-600 hover:bg-accent-500 rounded-lg font-medium transition-colors disabled:opacity-50"
              >
                {detectingEntryPoints ? (
                  <span className="flex items-center gap-2">
                    <Loader2 className="animate-spin" size={16} />
                    Detecting...
                  </span>
                ) : (
                  <span className="flex items-center gap-2">
                    <Sparkles size={16} />
                    Detect Entry Points
                  </span>
                )}
              </button>
            </div>
          )}
          
          {entryPoints && entryPoints.length === 0 && (
            <div>
              {/* Show candidates if they exist but no confirmed entry points */}
              {entryPointCandidates && entryPointCandidates.length > 0 ? (
                <div className="space-y-4">
                  <div className="bg-yellow-900/20 border border-yellow-800 rounded-lg p-4 mb-6">
                    <div className="flex items-center gap-2 mb-2">
                      <AlertCircle size={18} className="text-yellow-400" />
                      <h3 className="text-sm font-semibold text-yellow-400">
                        {entryPointCandidates.length} Candidate{entryPointCandidates.length !== 1 ? 's' : ''} Detected
                      </h3>
                    </div>
                    <p className="text-sm text-surface-400">
                      Entry point candidates were detected but not yet confirmed by AI. These are shown below for review.
                    </p>
                  </div>
                  
                  {/* Candidates List */}
                  <div className="space-y-3">
                    {entryPointCandidates.map((candidate) => (
                      <div
                        key={candidate.id}
                        className="bg-surface-900 border border-surface-800 rounded-lg p-5 hover:border-yellow-500/50 transition-colors"
                      >
                        <div className="flex items-start justify-between mb-3">
                          <div className="flex-1">
                            <div className="flex items-center gap-3 mb-2">
                              <AlertCircle size={18} className="text-yellow-400" />
                              <h3 className="text-lg font-semibold">
                                {candidate.detection_pattern || 'Unknown Entry Point'}
                              </h3>
                              <span className="px-2 py-1 bg-accent-600/20 text-accent-400 rounded text-xs font-medium">
                                {candidate.entry_point_type?.toUpperCase() || 'UNKNOWN'}
                              </span>
                              <span className="px-2 py-1 bg-surface-800 text-surface-300 rounded text-xs font-medium">
                                {candidate.framework || 'unknown'}
                              </span>
                            </div>
                            <p className="text-surface-400 mb-2">
                              Symbol ID: <span className="font-mono text-sm">{candidate.symbol_id}</span>
                            </p>
                            {candidate.metadata && Object.keys(candidate.metadata).length > 0 && (
                              <div className="text-sm text-surface-500">
                                <details className="cursor-pointer">
                                  <summary className="hover:text-surface-400">View Metadata</summary>
                                  <pre className="mt-2 p-2 bg-surface-800 rounded text-xs overflow-auto">
                                    {JSON.stringify(candidate.metadata, null, 2)}
                                  </pre>
                                </details>
                              </div>
                            )}
                            {candidate.confidence_score !== null && (
                              <div className="text-sm text-surface-500 mt-2">
                                Confidence Score: {(candidate.confidence_score * 100).toFixed(0)}%
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="bg-surface-900 border border-surface-800 rounded-lg p-12 text-center">
                  <AlertCircle size={48} className="mx-auto text-surface-600 mb-4" />
                  <h3 className="text-lg font-semibold mb-2">No Entry Points Found</h3>
                  <p className="text-surface-400 mb-6">
                    No entry points were detected in this repository. This could mean:
                  </p>
                  <ul className="text-left text-surface-400 mb-6 max-w-md mx-auto space-y-2">
                    <li>• The repository doesn't use supported frameworks</li>
                    <li>• Entry points are defined in a way not yet supported</li>
                    <li>• The code needs to be re-parsed first</li>
                  </ul>
                  <button
                    onClick={() => handleDetectEntryPoints(true)}
                    disabled={detectingEntryPoints}
                    className="px-6 py-3 bg-accent-600 hover:bg-accent-500 rounded-lg font-medium transition-colors disabled:opacity-50"
                  >
                    {detectingEntryPoints ? (
                      <span className="flex items-center gap-2">
                        <Loader2 className="animate-spin" size={16} />
                        Detecting...
                      </span>
                    ) : (
                      'Try Again'
                    )}
                  </button>
                </div>
              )}
            </div>
          )}
          
          {entryPoints && entryPoints.length > 0 && (
            <div className="space-y-4">
              {/* Summary Stats */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <div className="bg-surface-900 border border-surface-800 rounded-lg p-4">
                  <div className="text-surface-400 text-sm mb-1">Total Entry Points</div>
                  <div className="text-2xl font-bold text-accent-400">{entryPoints.length}</div>
                </div>
                <div className="bg-surface-900 border border-surface-800 rounded-lg p-4">
                  <div className="text-surface-400 text-sm mb-1">HTTP Endpoints</div>
                  <div className="text-2xl font-bold">
                    {entryPoints.filter(ep => ep.entry_point_type === 'http').length}
                  </div>
                </div>
                <div className="bg-surface-900 border border-surface-800 rounded-lg p-4">
                  <div className="text-surface-400 text-sm mb-1">Frameworks</div>
                  <div className="text-2xl font-bold">
                    {new Set(entryPoints.map(ep => ep.framework)).size}
                  </div>
                </div>
                <div className="bg-surface-900 border border-surface-800 rounded-lg p-4">
                  <div className="text-surface-400 text-sm mb-1">Avg Confidence</div>
                  <div className="text-2xl font-bold">
                    {(entryPoints.reduce((sum, ep) => sum + ep.ai_confidence, 0) / entryPoints.length).toFixed(2)}
                  </div>
                </div>
              </div>
              
              {/* Entry Points List */}
              <div className="space-y-3">
                {entryPoints.map((ep) => (
                  <EntryPointItem
                    key={ep.id}
                    ep={ep}
                    isGenerating={generatingFlows.has(ep.id)}
                    isExpanded={expandedFlows.has(ep.id)}
                    onGenerateFlow={handleGenerateFlow}
                    onToggleFlow={toggleFlowExpansion}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
      
    </div>
  )
}
