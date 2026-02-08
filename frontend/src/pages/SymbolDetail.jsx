import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { 
  ArrowLeft, ArrowUpRight, ArrowDownRight, Loader2, 
  Box, FunctionSquare, ChevronRight 
} from 'lucide-react'
import { api } from '../api'

function GraphSection({ title, icon: Icon, nodes, repoId, repoBasePath, color }) {
  if (!nodes || nodes.length === 0) {
    return (
      <div className="bg-surface-900 border border-surface-800 rounded-xl p-6">
        <div className="flex items-center gap-2 mb-4">
          <Icon size={20} className={color} />
          <h3 className="font-semibold">{title}</h3>
        </div>
        <p className="text-surface-500 text-sm">No {title.toLowerCase()} found</p>
      </div>
    )
  }
  
  // Group by depth
  const byDepth = nodes.reduce((acc, node) => {
    const depth = node.depth || 1
    if (!acc[depth]) acc[depth] = []
    acc[depth].push(node)
    return acc
  }, {})
  
  return (
    <div className="bg-surface-900 border border-surface-800 rounded-xl p-6">
      <div className="flex items-center gap-2 mb-4">
        <Icon size={20} className={color} />
        <h3 className="font-semibold">{title}</h3>
        <span className="text-xs text-surface-500 bg-surface-800 px-2 py-0.5 rounded-full">
          {nodes.length}
        </span>
      </div>
      
      <div className="space-y-4">
        {Object.entries(byDepth).map(([depth, depthNodes]) => (
          <div key={depth}>
            <p className="text-xs text-surface-500 mb-2">
              Depth {depth}
            </p>
            <div className="space-y-1 pl-3 border-l-2 border-surface-700">
              {depthNodes.map((node, idx) => (
                <Link
                  key={`${node.id}-${idx}`}
                  to={node.id ? `${repoBasePath}/symbols/${node.id}` : '#'}
                  className={`flex items-center gap-2 p-2 rounded hover:bg-surface-800 transition-colors ${
                    !node.id ? 'opacity-60 cursor-default' : ''
                  }`}
                >
                  {node.kind === 'function' || node.kind === 'method' ? (
                    <FunctionSquare size={14} className="text-purple-400" />
                  ) : (
                    <Box size={14} className="text-yellow-400" />
                  )}
                  <span className="font-mono text-sm truncate flex-1">
                    {node.qualified_name || node.name}
                  </span>
                  <span className="text-xs text-surface-500 px-1.5 py-0.5 bg-surface-800 rounded">
                    {node.reference_type}
                  </span>
                  {node.id && <ChevronRight size={14} className="text-surface-600" />}
                </Link>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function SymbolDetail() {
  const { repoId, symbolId, orgId } = useParams()
  const repoBasePath = orgId ? `/orgs/${orgId}/repos/${repoId}` : `/repos/${repoId}`
  
  const { data: symbol, isLoading } = useQuery({
    queryKey: ['symbol', repoId, symbolId],
    queryFn: () => api.getSymbol(repoId, symbolId),
  })
  
  const { data: upstream } = useQuery({
    queryKey: ['upstream', repoId, symbolId],
    queryFn: () => api.getUpstream(repoId, symbolId),
  })
  
  const { data: downstream } = useQuery({
    queryKey: ['downstream', repoId, symbolId],
    queryFn: () => api.getDownstream(repoId, symbolId),
  })
  
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="animate-spin text-accent-400" size={32} />
      </div>
    )
  }
  
  if (!symbol) {
    return (
      <div className="p-8">
        <p className="text-surface-400">Symbol not found</p>
      </div>
    )
  }
  
  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <Link 
          to={repoBasePath}
          className="inline-flex items-center gap-2 text-surface-400 hover:text-white mb-4 transition-colors"
        >
          <ArrowLeft size={16} />
          Back to repository
        </Link>
        
        <div className="flex items-center gap-3 mb-2">
          <h1 className="text-2xl font-bold">{symbol.name}</h1>
          <span className="text-sm text-surface-400 px-2 py-1 bg-surface-800 rounded">
            {symbol.kind}
          </span>
        </div>
        <p className="text-surface-400 font-mono text-sm">{symbol.qualified_name}</p>
      </div>
      
      {/* Signature */}
      {symbol.signature && (
        <div className="mb-8">
          <h2 className="text-sm font-medium text-surface-400 mb-2">Signature</h2>
          <pre className="code-block">
            <code>{symbol.signature}</code>
          </pre>
        </div>
      )}
      
      {/* Source Code */}
      <div className="mb-8">
        <h2 className="text-sm font-medium text-surface-400 mb-2">Source Code</h2>
        <pre className="code-block max-h-96 overflow-auto">
          <code>{symbol.source_code}</code>
        </pre>
      </div>
      
      {/* Call Graph */}
      <div className="grid md:grid-cols-2 gap-6">
        <GraphSection
          title="Upstream (Callers)"
          icon={ArrowUpRight}
          nodes={upstream?.nodes}
          repoId={repoId}
          repoBasePath={repoBasePath}
          color="text-green-400"
        />
        <GraphSection
          title="Downstream (Callees)"
          icon={ArrowDownRight}
          nodes={downstream?.nodes}
          repoId={repoId}
          repoBasePath={repoBasePath}
          color="text-blue-400"
        />
      </div>
    </div>
  )
}

