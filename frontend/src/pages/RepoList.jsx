import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Plus, Trash2, Loader2, CheckCircle, XCircle, Clock, Play, Database, Search, Building2, ArrowLeft } from 'lucide-react'
import { api } from '../api'

const statusConfig = {
  pending: { icon: Clock, color: 'text-yellow-400', bg: 'bg-yellow-400/10' },
  parsing: { icon: Play, color: 'text-blue-400', bg: 'bg-blue-400/10' },
  completed: { icon: CheckCircle, color: 'text-green-400', bg: 'bg-green-400/10' },
  failed: { icon: XCircle, color: 'text-red-400', bg: 'bg-red-400/10' },
}

function StatusBadge({ status }) {
  const config = statusConfig[status] || statusConfig.pending
  const Icon = config.icon
  
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${config.color} ${config.bg}`}>
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
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-surface-900 border border-surface-700 rounded-xl p-6 w-full max-w-md">
        <h2 className="text-xl font-semibold mb-4">Add Repository</h2>
        
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-surface-300 mb-1">
              Repository Path
            </label>
            <input
              type="text"
              value={path}
              onChange={(e) => setPath(e.target.value)}
              placeholder="/path/to/my-project"
              className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent-500"
              autoFocus
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-surface-300 mb-1">
              Name (optional)
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="my-project"
              className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent-500"
            />
          </div>
          
          {mutation.error && (
            <p className="text-red-400 text-sm">{mutation.error.message}</p>
          )}
        </div>
        
        <div className="flex justify-end gap-3 mt-6">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-surface-300 hover:text-white transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={() => mutation.mutate()}
            disabled={!path || mutation.isPending}
            className="px-4 py-2 bg-accent-500 hover:bg-accent-600 disabled:opacity-50 rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
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
    <div className="bg-surface-900 border border-surface-800 rounded-xl p-5 hover:border-surface-700 transition-colors">
      <div className="flex items-start justify-between">
        <Link to={basePath} className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-2">
            <h3 className="text-lg font-semibold hover:text-accent-400 transition-colors truncate">
              {repo.name}
            </h3>
            <StatusBadge status={repo.status} />
          </div>
          
          {/* Repo description */}
          {repo.description && (
            <p className="text-sm text-surface-300 mb-2 line-clamp-2">
              {repo.description}
            </p>
          )}
          
          <p className="text-sm text-surface-500 font-mono truncate">{repo.root_path}</p>
          
          {repo.status === 'parsing' && (
            <div className="mt-3">
              <div className="flex items-center justify-between text-xs text-surface-400 mb-1">
                <span>Parsing progress</span>
                <span>{repo.parsed_files} / {repo.total_files} files</span>
              </div>
              <div className="h-1.5 bg-surface-800 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-accent-500 transition-all duration-300"
                  style={{ width: `${repo.progress_percentage || 0}%` }}
                />
              </div>
            </div>
          )}
          
          {repo.status === 'completed' && (
            <div className="mt-2">
              <p className="text-sm text-surface-400">
                {repo.total_files} files parsed
              </p>
              {repo.languages && repo.languages.length > 0 && (
                <div className="flex flex-wrap gap-2 mt-2">
                  {repo.languages.map((lang) => (
                    <span 
                      key={lang} 
                      className="px-2 py-0.5 bg-accent-600/20 text-accent-400 rounded-full text-xs font-medium"
                    >
                      {lang}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}
          
          {repo.status === 'failed' && repo.error_message && (
            <p className="mt-2 text-sm text-red-400 truncate">
              {repo.error_message}
            </p>
          )}
        </Link>
        
        <button
          onClick={() => onDelete(repo.id)}
          className="p-2 text-surface-400 hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-colors ml-2"
          title="Delete repository"
        >
          <Trash2 size={18} />
        </button>
      </div>
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
              <h1 className="text-2xl font-bold">
                {org ? org.name : 'All Repositories'}
              </h1>
              <p className="text-surface-400 mt-1">
                {org?.description || (orgId ? 'Repositories in this organization' : 'Manage and explore parsed codebases')}
              </p>
            </div>
          </div>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-accent-500 hover:bg-accent-600 rounded-lg font-medium transition-colors"
        >
          <Plus size={18} />
          Add Repository
        </button>
      </div>
      
      {/* Search bar (only for org-scoped view) */}
      {orgId && (
        <div className="relative mb-6">
          <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search repos by name or description (supports regex)..."
            className="w-full bg-surface-900 border border-surface-800 rounded-lg pl-10 pr-4 py-2.5 text-sm focus:outline-none focus:border-accent-500 transition-colors"
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
        <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-4 text-red-400">
          {error.message}
        </div>
      )}
      
      {repos && repos.length === 0 && (
        <div className="text-center py-12 text-surface-400">
          <Database size={48} className="mx-auto mb-4 opacity-50" />
          <p>{searchQuery ? 'No repositories match your search.' : 'No repositories yet. Add one to get started.'}</p>
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
