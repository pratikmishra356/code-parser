import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useMutation } from '@tanstack/react-query'
import { 
  Search, ArrowDown, ArrowUp, FileCode, Box, Braces, 
  FunctionSquare, Loader2, AlertCircle, ExternalLink,
  ChevronDown, ChevronRight, Copy, Check
} from 'lucide-react'
import { api } from '../api'

const kindConfig = {
  function: { icon: FunctionSquare, color: 'text-purple-400', bg: 'bg-purple-500/20' },
  method: { icon: FunctionSquare, color: 'text-purple-400', bg: 'bg-purple-500/20' },
  class: { icon: Box, color: 'text-yellow-400', bg: 'bg-yellow-500/20' },
  interface: { icon: Braces, color: 'text-cyan-400', bg: 'bg-cyan-500/20' },
  import: { icon: FileCode, color: 'text-green-400', bg: 'bg-green-500/20' },
}

function KindBadge({ kind }) {
  const config = kindConfig[kind] || { icon: Box, color: 'text-surface-400', bg: 'bg-surface-700' }
  const Icon = config.icon
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium ${config.bg} ${config.color}`}>
      <Icon size={12} />
      {kind}
    </span>
  )
}

function CodeBlock({ code, language }) {
  const [copied, setCopied] = useState(false)
  
  const handleCopy = () => {
    navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  
  return (
    <div className="relative group">
      <button
        onClick={handleCopy}
        className="absolute top-2 right-2 p-1.5 rounded bg-surface-700 opacity-0 group-hover:opacity-100 transition-opacity"
      >
        {copied ? <Check size={14} className="text-green-400" /> : <Copy size={14} />}
      </button>
      <pre className="bg-surface-950 border border-surface-800 rounded-lg p-4 overflow-x-auto text-sm">
        <code className="text-surface-200">{code}</code>
      </pre>
    </div>
  )
}

function SymbolCard({ symbol, direction, isExpanded, onToggle }) {
  const isExternal = symbol.is_external
  
  return (
    <div className={`border rounded-lg overflow-hidden ${isExternal ? 'border-surface-700 bg-surface-900/50' : 'border-surface-800 bg-surface-900'}`}>
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-3 p-4 hover:bg-surface-800/50 transition-colors text-left"
      >
        {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium">{symbol.name}</span>
            {symbol.kind && <KindBadge kind={symbol.kind} />}
            {isExternal && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-amber-500/20 text-amber-400">
                <ExternalLink size={10} />
                external
              </span>
            )}
            {symbol.reference_type && (
              <span className="text-xs text-surface-500 px-1.5 py-0.5 bg-surface-800 rounded">
                {symbol.reference_type}
              </span>
            )}
          </div>
          <p className="text-sm text-surface-500 font-mono truncate mt-1">
            {symbol.qualified_name}
          </p>
        </div>
        
        {direction && (
          <span className={`flex items-center gap-1 text-xs ${direction === 'upstream' ? 'text-blue-400' : 'text-orange-400'}`}>
            {direction === 'upstream' ? <ArrowUp size={12} /> : <ArrowDown size={12} />}
            depth {symbol.depth}
          </span>
        )}
      </button>
      
      {isExpanded && symbol.source_code && (
        <div className="border-t border-surface-800 p-4">
          {symbol.signature && (
            <div className="mb-3">
              <span className="text-xs text-surface-500 uppercase tracking-wider">Signature</span>
              <p className="font-mono text-sm text-accent-400 mt-1">{symbol.signature}</p>
            </div>
          )}
          <div>
            <span className="text-xs text-surface-500 uppercase tracking-wider">Source Code</span>
            <div className="mt-2">
              <CodeBlock code={symbol.source_code} />
            </div>
          </div>
        </div>
      )}
      
      {isExpanded && !symbol.source_code && isExternal && (
        <div className="border-t border-surface-800 p-4 text-center text-surface-500 text-sm">
          External reference - source code not available in this repository
        </div>
      )}
    </div>
  )
}

export default function SymbolLookup() {
  const { repoId, orgId } = useParams()
  const [pathName, setPathName] = useState('')
  const [symbolName, setSymbolName] = useState('')
  const [depth, setDepth] = useState(1)
  const [expandedSymbols, setExpandedSymbols] = useState(new Set(['main']))
  
  const { data: repo } = useQuery({
    queryKey: ['repo', repoId],
    queryFn: () => api.getRepo(repoId),
  })
  
  const lookupMutation = useMutation({
    mutationFn: () => api.getSymbolDetails(repoId, pathName, symbolName, depth),
    onSuccess: () => {
      setExpandedSymbols(new Set(['main']))
    },
  })
  
  const handleSubmit = (e) => {
    e.preventDefault()
    if (pathName.trim() && symbolName.trim()) {
      lookupMutation.mutate()
    }
  }
  
  const toggleExpanded = (id) => {
    setExpandedSymbols(prev => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }
  
  const result = lookupMutation.data
  
  return (
    <div className="p-8 max-w-5xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold">Symbol Lookup</h1>
        <p className="text-surface-400 mt-1">
          Find symbol details by package path and name • {repo?.name || 'Loading...'}
        </p>
      </div>
      
      {/* Search Form */}
      <form onSubmit={handleSubmit} className="mb-8 bg-surface-900 border border-surface-800 rounded-xl p-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block text-sm font-medium text-surface-300 mb-2">
              Package/Class Path
            </label>
            <input
              type="text"
              value={pathName}
              onChange={(e) => setPathName(e.target.value)}
              placeholder="com.toasttab.service.MyService"
              className="w-full bg-surface-950 border border-surface-700 rounded-lg px-4 py-2.5 text-sm font-mono focus:outline-none focus:border-accent-500 transition-colors"
            />
            <p className="text-xs text-surface-500 mt-1">
              From stacktrace: the class path before the method name
            </p>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-surface-300 mb-2">
              Symbol Name
            </label>
            <input
              type="text"
              value={symbolName}
              onChange={(e) => setSymbolName(e.target.value)}
              placeholder="myMethod"
              className="w-full bg-surface-950 border border-surface-700 rounded-lg px-4 py-2.5 text-sm font-mono focus:outline-none focus:border-accent-500 transition-colors"
            />
            <p className="text-xs text-surface-500 mt-1">
              Method, class, or function name
            </p>
          </div>
        </div>
        
        <div className="flex items-end gap-4">
          <div className="w-32">
            <label className="block text-sm font-medium text-surface-300 mb-2">
              Context Depth
            </label>
            <select
              value={depth}
              onChange={(e) => setDepth(Number(e.target.value))}
              className="w-full bg-surface-950 border border-surface-700 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-accent-500"
            >
              <option value={0}>0 (symbol only)</option>
              <option value={1}>1</option>
              <option value={2}>2</option>
              <option value={3}>3</option>
              <option value={5}>5</option>
            </select>
          </div>
          
          <button
            type="submit"
            disabled={lookupMutation.isPending || !pathName.trim() || !symbolName.trim()}
            className="flex items-center gap-2 px-6 py-2.5 bg-accent-600 hover:bg-accent-500 disabled:bg-surface-700 disabled:text-surface-500 rounded-lg font-medium transition-colors"
          >
            {lookupMutation.isPending ? (
              <Loader2 className="animate-spin" size={18} />
            ) : (
              <Search size={18} />
            )}
            Lookup
          </button>
        </div>
      </form>
      
      {/* Error */}
      {lookupMutation.isError && (
        <div className="mb-6 flex items-center gap-3 p-4 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400">
          <AlertCircle size={20} />
          <span>{lookupMutation.error.message}</span>
        </div>
      )}
      
      {/* Results */}
      {result && (
        <div className="space-y-6">
          {/* Match count indicator */}
          {result.total_matches > 1 && (
            <div className="flex items-center gap-2 p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg text-amber-400">
              <AlertCircle size={18} />
              <span>Found {result.total_matches} matches - same symbol exists in multiple locations</span>
            </div>
          )}
          
          {/* All Matches */}
          {result.matches.map((match, matchIdx) => (
            <div key={match.symbol.id || matchIdx} className="space-y-4">
              {/* Match header when multiple */}
              {result.total_matches > 1 && (
                <div className="flex items-center gap-2 text-sm text-surface-400 border-b border-surface-800 pb-2">
                  <span className="font-medium">Match {matchIdx + 1} of {result.total_matches}</span>
                  <span className="text-surface-600">•</span>
                  <span className="font-mono">{match.symbol.relative_path}</span>
                </div>
              )}
              
              {/* Main Symbol */}
              <div>
                <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
                  <FileCode size={18} className="text-accent-400" />
                  Symbol Found
                </h2>
                <div className="border border-accent-500/30 bg-accent-500/5 rounded-xl overflow-hidden">
                  <div className="p-4 border-b border-surface-800">
                    <div className="flex items-center gap-3 flex-wrap">
                      <span className="text-xl font-semibold">{match.symbol.name}</span>
                      <KindBadge kind={match.symbol.kind} />
                    </div>
                    <p className="font-mono text-sm text-surface-400 mt-2">
                      {match.symbol.qualified_name}
                    </p>
                    {match.symbol.relative_path && (
                      <p className="text-sm text-surface-500 mt-1 flex items-center gap-1">
                        <FileCode size={12} />
                        {match.symbol.relative_path}
                      </p>
                    )}
                  </div>
                  
                  {match.symbol.signature && (
                    <div className="p-4 border-b border-surface-800">
                      <span className="text-xs text-surface-500 uppercase tracking-wider">Signature</span>
                      <p className="font-mono text-sm text-accent-400 mt-2 whitespace-pre-wrap">{match.symbol.signature}</p>
                    </div>
                  )}
                  
                  {match.symbol.source_code && (
                    <div className="p-4">
                      <span className="text-xs text-surface-500 uppercase tracking-wider">Source Code</span>
                      <div className="mt-2">
                        <CodeBlock code={match.symbol.source_code} />
                      </div>
                    </div>
                  )}
                </div>
              </div>
              
              {/* Upstream */}
              {match.upstream && match.upstream.length > 0 && (
                <div>
                  <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
                    <ArrowUp size={18} className="text-blue-400" />
                    Upstream ({match.upstream.length})
                    <span className="text-sm font-normal text-surface-500">— what calls this symbol</span>
                  </h2>
                  <div className="space-y-2">
                    {match.upstream.map((sym, idx) => (
                      <SymbolCard
                        key={sym.id || `${matchIdx}-up-${idx}`}
                        symbol={sym}
                        direction="upstream"
                        isExpanded={expandedSymbols.has(sym.id || `${matchIdx}-up-${idx}`)}
                        onToggle={() => toggleExpanded(sym.id || `${matchIdx}-up-${idx}`)}
                      />
                    ))}
                  </div>
                </div>
              )}
              
              {/* Downstream */}
              {match.downstream && match.downstream.length > 0 && (
                <div>
                  <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
                    <ArrowDown size={18} className="text-orange-400" />
                    Downstream ({match.downstream.length})
                    <span className="text-sm font-normal text-surface-500">— what this symbol calls</span>
                  </h2>
                  <div className="space-y-2">
                    {match.downstream.map((sym, idx) => (
                      <SymbolCard
                        key={sym.id || `${matchIdx}-down-${idx}`}
                        symbol={sym}
                        direction="downstream"
                        isExpanded={expandedSymbols.has(sym.id || `${matchIdx}-down-${idx}`)}
                        onToggle={() => toggleExpanded(sym.id || `${matchIdx}-down-${idx}`)}
                      />
                    ))}
                  </div>
                </div>
              )}
              
              {/* No context */}
              {depth > 0 && match.upstream?.length === 0 && match.downstream?.length === 0 && (
                <div className="text-center py-8 text-surface-500">
                  No upstream or downstream references found at depth {depth}
                </div>
              )}
              
              {/* Separator between matches */}
              {result.total_matches > 1 && matchIdx < result.total_matches - 1 && (
                <hr className="border-surface-700 my-8" />
              )}
            </div>
          ))}
        </div>
      )}
      
      {/* Empty state */}
      {!result && !lookupMutation.isPending && !lookupMutation.isError && (
        <div className="text-center py-16 text-surface-500">
          <Search size={48} className="mx-auto mb-4 opacity-30" />
          <p className="text-lg">Enter a package path and symbol name to lookup</p>
          <p className="text-sm mt-2">
            Example: <code className="text-accent-400">com.toasttab.service.ccfraud.resources.RiskAssessmentResource</code> + <code className="text-accent-400">riskAssessment</code>
          </p>
        </div>
      )}
    </div>
  )
}

