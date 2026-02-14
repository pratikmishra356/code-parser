import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Plus, Trash2, Loader2, CheckCircle, XCircle, Clock, Play, Database, Search, Building2, ArrowLeft, ChevronDown, ChevronUp, BookOpen, Zap, GitBranch } from 'lucide-react'
import { api } from '../api'

const statusConfig = {
  pending: { icon: Clock, color: 'text-yellow-600', bg: 'bg-yellow-50 border-yellow-200' },
  parsing: { icon: Play, color: 'text-blue-600', bg: 'bg-blue-50 border-blue-200' },
  completed: { icon: CheckCircle, color: 'text-green-600', bg: 'bg-green-50 border-green-200' },
  failed: { icon: XCircle, color: 'text-red-600', bg: 'bg-red-50 border-red-200' },
}

function StatusBadge({ status }) {
  const config = statusConfig[status] || statusConfig.pending
  const Icon = config.icon
  
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold border ${config.color} ${config.bg}`}>
      <Icon size={12} />
      {status}
    </span>
  )
}

function AddRepoModal({ isOpen, onClose, orgId }) {
  const [path, setPath] = useState('')
  const [name, setName] = useState('')
  const queryClient = useQueryClient()
  
  const mutation = useMutation({
    mutationFn: () => api.createRepo(path, name || undefined, orgId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['repos'] })
      queryClient.invalidateQueries({ queryKey: ['orgRepos'] })
      onClose()
      setPath('')
      setName('')
    },
  })
  
  if (!isOpen) return null
  
  return (
    <div className="fixed inset-0 bg-black/30 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-white border border-surface-200 rounded-2xl p-6 w-full max-w-md shadow-xl">
        <h2 className="text-xl font-bold text-surface-900 mb-5">Add Repository</h2>
        
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-semibold text-surface-700 mb-2">
              Repository Path
            </label>
            <input
              type="text"
              value={path}
              onChange={(e) => setPath(e.target.value)}
              placeholder="/path/to/my-project"
              className="w-full bg-white border border-surface-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-accent-500 focus:ring-2 focus:ring-accent-500/20 text-surface-900 placeholder:text-surface-400"
              autoFocus
            />
          </div>
          
          <div>
            <label className="block text-sm font-semibold text-surface-700 mb-2">
              Name (optional)
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="my-project"
              className="w-full bg-white border border-surface-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-accent-500 focus:ring-2 focus:ring-accent-500/20 text-surface-900 placeholder:text-surface-400"
            />
          </div>
          
          {mutation.error && (
            <p className="text-red-600 text-sm bg-red-50 border border-red-200 rounded-lg p-2.5">{mutation.error.message}</p>
          )}
        </div>
        
        <div className="flex justify-end gap-3 mt-6">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-surface-600 hover:text-surface-900 font-medium transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={() => mutation.mutate()}
            disabled={!path || mutation.isPending}
            className="px-5 py-2.5 bg-accent-500 hover:bg-accent-600 disabled:opacity-50 rounded-lg text-sm font-semibold text-white transition-all shadow-sm hover:shadow-md flex items-center gap-2"
          >
            {mutation.isPending && <Loader2 size={14} className="animate-spin" />}
            Add Repository
          </button>
        </div>
      </div>
    </div>
  )
}

function RepoCard({ repo, orgId, onDelete }) {
  const basePath = orgId ? `/orgs/${orgId}/repos/${repo.id}` : `/repos/${repo.id}`
  
  return (
    <div className="bg-white border border-surface-200 rounded-xl p-5 hover:border-accent-300 hover:shadow-md transition-all">
      <div className="flex items-start justify-between">
        <Link to={basePath} className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-2">
            <h3 className="text-lg font-bold text-surface-900 hover:text-accent-600 transition-colors truncate">
              {repo.name}
            </h3>
            <StatusBadge status={repo.status} />
          </div>
          
          {/* Repo description */}
          {repo.description && (
            <p className="text-sm text-surface-600 mb-2 line-clamp-2">
              {repo.description}
            </p>
          )}
          
          <p className="text-sm text-surface-500 font-mono truncate">{repo.root_path}</p>
          
          {repo.status === 'parsing' && (
            <div className="mt-3">
              <div className="flex items-center justify-between text-xs text-surface-600 mb-1.5 font-medium">
                <span>Parsing progress</span>
                <span>{repo.parsed_files} / {repo.total_files} files</span>
              </div>
              <div className="h-2 bg-surface-100 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-gradient-to-r from-accent-500 to-accent-600 transition-all duration-300 rounded-full"
                  style={{ width: `${repo.progress_percentage || 0}%` }}
                />
              </div>
            </div>
          )}
          
          {repo.status === 'completed' && (
            <div className="mt-2">
              <p className="text-sm text-surface-600 font-medium">
                {repo.total_files} files parsed
              </p>
              {repo.languages && repo.languages.length > 0 && (
                <div className="flex flex-wrap gap-2 mt-2">
                  {repo.languages.map((lang) => (
                    <span 
                      key={lang} 
                      className="px-2.5 py-1 bg-accent-100 text-accent-700 rounded-md text-xs font-semibold"
                    >
                      {lang}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}
          
          {repo.status === 'failed' && repo.error_message && (
            <p className="mt-2 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg p-2 truncate">
              {repo.error_message}
            </p>
          )}
        </Link>
        
        <button
          onClick={() => onDelete(repo.id)}
          className="p-2 text-surface-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors ml-2"
          title="Delete repository"
        >
          <Trash2 size={18} />
        </button>
      </div>
    </div>
  )
}

function SetupInstructions({ orgId }) {
  const [isExpanded, setIsExpanded] = useState(true)
  
  return (
    <div className="bg-white border border-surface-200 rounded-xl p-6 mb-6 shadow-sm">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between text-left"
      >
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-gradient-to-br from-accent-500 to-accent-600 rounded-lg shadow-sm">
            <BookOpen size={20} className="text-white" />
          </div>
          <div>
            <h3 className="font-bold text-lg text-surface-900">Setup Instructions</h3>
            <p className="text-sm text-surface-600">Get started with code parsing and analysis</p>
          </div>
        </div>
        {isExpanded ? (
          <ChevronUp size={20} className="text-surface-400" />
        ) : (
          <ChevronDown size={20} className="text-surface-400" />
        )}
      </button>
      
      {isExpanded && (
        <div className="mt-6 space-y-6">
          {/* Step 1: Add Repository */}
          <div className="flex gap-4">
            <div className="flex-shrink-0">
              <div className="w-9 h-9 rounded-full bg-gradient-to-br from-accent-500 to-accent-600 flex items-center justify-center text-white font-bold text-sm shadow-sm">
                1
              </div>
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-2">
                <GitBranch size={16} className="text-accent-600" />
                <h4 className="font-bold text-surface-900">Add a Repository</h4>
              </div>
              <p className="text-sm text-surface-700 mb-3 leading-relaxed">
                Click the <strong>"Add Repository"</strong> button above and provide the local file system path to your codebase.
              </p>
              <div className="bg-surface-50 border border-surface-200 rounded-lg p-3 text-sm font-mono text-surface-700">
                Example: <span className="text-accent-600 font-semibold">/Users/username/my-project</span>
              </div>
              <p className="text-xs text-surface-600 mt-2">
                The service will parse all supported files (Python, Java, Kotlin, JavaScript, Rust) and build an AST representation.
              </p>
            </div>
          </div>
          
          {/* Step 2: Detect Entry Points */}
          <div className="flex gap-4">
            <div className="flex-shrink-0">
              <div className="w-9 h-9 rounded-full bg-gradient-to-br from-accent-500 to-accent-600 flex items-center justify-center text-white font-bold text-sm shadow-sm">
                2
              </div>
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-2">
                <Zap size={16} className="text-accent-600" />
                <h4 className="font-bold text-surface-900">Detect Entry Points</h4>
              </div>
              <p className="text-sm text-surface-700 mb-3 leading-relaxed">
                Once parsing is complete, navigate to the repository detail page and click <strong>"Detect Entry Points"</strong>.
              </p>
              <div className="bg-surface-50 border border-surface-200 rounded-lg p-3 text-sm text-surface-700">
                <p className="mb-2 font-semibold">The AI will analyze your codebase to identify:</p>
                <ul className="list-disc list-inside space-y-1 text-surface-600 ml-2">
                  <li><strong>HTTP endpoints</strong> - REST APIs, GraphQL resolvers, web handlers</li>
                  <li><strong>Event handlers</strong> - Kafka consumers, message queue subscribers</li>
                  <li><strong>Scheduled tasks</strong> - Cron jobs, periodic workers</li>
                </ul>
              </div>
              <p className="text-xs text-surface-600 mt-2">
                Entry points are automatically detected using AI analysis of your code structure and framework patterns.
              </p>
            </div>
          </div>
          
          {/* Step 3: Generate Flow */}
          <div className="flex gap-4">
            <div className="flex-shrink-0">
              <div className="w-9 h-9 rounded-full bg-gradient-to-br from-accent-500 to-accent-600 flex items-center justify-center text-white font-bold text-sm shadow-sm">
                3
              </div>
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-2">
                <GitBranch size={16} className="text-accent-600" />
                <h4 className="font-bold text-surface-900">Generate Flow Documentation</h4>
              </div>
              <p className="text-sm text-surface-700 mb-3 leading-relaxed">
                For each detected entry point, click <strong>"Generate Flow"</strong> to create detailed execution flow documentation.
              </p>
              <div className="bg-surface-50 border border-surface-200 rounded-lg p-3 text-sm text-surface-700">
                <p className="mb-2 font-semibold">Flow generation will:</p>
                <ul className="list-disc list-inside space-y-1 text-surface-600 ml-2">
                  <li>Trace the call graph from the entry point</li>
                  <li>Document each step in the execution flow</li>
                  <li>Include code snippets and important log lines</li>
                  <li>Generate a technical summary of the flow</li>
                </ul>
              </div>
              <p className="text-xs text-surface-600 mt-2">
                Flow documentation helps understand how your code executes and makes it easier for AI agents to explore your codebase.
              </p>
            </div>
          </div>
          
          {/* Quick Links */}
          <div className="pt-4 border-t border-surface-200">
            <p className="text-xs text-surface-600 mb-2">💡 <strong>Tip:</strong> Use the "AI Explore" link in the sidebar to search and explore repos, entry points, and flows programmatically.</p>
          </div>
        </div>
      )}
    </div>
  )
}

export default function RepoList() {
  const { orgId } = useParams()
  const [showModal, setShowModal] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const queryClient = useQueryClient()
  
  // Fetch org info if org-scoped
  const { data: org } = useQuery({
    queryKey: ['org', orgId],
    queryFn: () => api.getOrg(orgId),
    enabled: !!orgId,
  })
  
  // Fetch repos - org-scoped with search, or all repos
  const { data: repos, isLoading, error } = useQuery({
    queryKey: orgId ? ['orgRepos', orgId, searchQuery] : ['repos'],
    queryFn: () => orgId 
      ? api.listReposForOrg(orgId, { search: searchQuery || undefined }) 
      : api.listRepos(),
    refetchInterval: 5000,
  })
  
  const deleteMutation = useMutation({
    mutationFn: api.deleteRepo,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['repos'] })
      queryClient.invalidateQueries({ queryKey: ['orgRepos'] })
    },
  })
  
  const handleDelete = (repoId) => {
    if (confirm('Delete this repository and all its data?')) {
      deleteMutation.mutate(repoId)
    }
  }
  
  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          {orgId && (
            <Link 
              to="/" 
              className="inline-flex items-center gap-2 text-surface-400 hover:text-white mb-3 transition-colors text-sm"
            >
              <ArrowLeft size={14} />
              All Organizations
            </Link>
          )}
          <div className="flex items-center gap-3">
            {orgId && org && (
              <div className="p-2 bg-accent-500/10 rounded-lg">
                <Building2 size={20} className="text-accent-400" />
              </div>
            )}
            <div>
              <h1 className="text-3xl font-bold text-surface-900">
                {org ? org.name : 'All Repositories'}
              </h1>
              <p className="text-surface-600 mt-1.5 text-sm">
                {org?.description || (orgId ? 'Repositories in this organization' : 'Manage and explore parsed codebases')}
              </p>
            </div>
          </div>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-2 px-5 py-2.5 bg-accent-500 hover:bg-accent-600 rounded-lg font-semibold text-white transition-all shadow-sm hover:shadow-md"
        >
          <Plus size={18} />
          Add Repository
        </button>
      </div>
      
      {/* Setup Instructions (only for org-scoped view) */}
      {orgId && <SetupInstructions orgId={orgId} />}
      
      {/* Search bar (only for org-scoped view) */}
      {orgId && (
        <div className="relative mb-6">
          <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search repos by name or description (supports regex)..."
              className="w-full bg-white border border-surface-200 rounded-lg pl-10 pr-4 py-2.5 text-sm focus:outline-none focus:border-accent-500 focus:ring-2 focus:ring-accent-500/20 transition-colors text-surface-900 placeholder:text-surface-400"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-500 hover:text-white text-xs"
            >
              Clear
            </button>
          )}
        </div>
      )}
      
      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="animate-spin text-accent-400" size={32} />
        </div>
      )}
      
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-red-700 mb-6">
          {error.message}
        </div>
      )}
      
      {repos && repos.length === 0 && (
        <div className="text-center py-16 bg-white rounded-2xl border border-surface-200">
          <div className="p-4 bg-accent-50 rounded-full w-fit mx-auto mb-4">
            <Database size={40} className="text-accent-600" />
          </div>
          <p className="text-surface-600 font-medium">{searchQuery ? 'No repositories match your search.' : 'No repositories yet. Add one to get started.'}</p>
        </div>
      )}
      
      {repos && repos.length > 0 && (
        <div className="grid gap-4">
          {repos.map((repo) => (
            <RepoCard 
              key={repo.id} 
              repo={repo} 
              orgId={orgId}
              onDelete={handleDelete}
            />
          ))}
        </div>
      )}
      
      <AddRepoModal isOpen={showModal} onClose={() => setShowModal(false)} orgId={orgId} />
    </div>
  )
}
