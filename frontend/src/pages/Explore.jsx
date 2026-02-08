import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { 
  Search, Loader2, FileCode, Route, GitBranch, Database, 
  ChevronRight, Copy, Check, Code, FileText, Sparkles,
  Building2, ArrowRight, ExternalLink
} from 'lucide-react'
import { api } from '../api'

function CopyButton({ text, className = '' }) {
  const [copied, setCopied] = useState(false)
  
  const handleCopy = async () => {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  
  return (
    <button
      onClick={handleCopy}
      className={`p-1.5 text-surface-400 hover:text-accent-400 hover:bg-surface-800 rounded transition-colors ${className}`}
      title="Copy to clipboard"
    >
      {copied ? <Check size={14} /> : <Copy size={14} />}
    </button>
  )
}

function CodeBlock({ code, language, title }) {
  return (
    <div className="bg-surface-900 border border-surface-800 rounded-lg overflow-hidden">
      {title && (
        <div className="px-4 py-2 bg-surface-800 border-b border-surface-700 flex items-center justify-between">
          <span className="text-sm font-medium text-surface-300">{title}</span>
          <CopyButton text={code} />
        </div>
      )}
      <pre className="p-4 overflow-x-auto text-sm font-mono">
        <code className={`language-${language}`}>{code}</code>
      </pre>
    </div>
  )
}

function ExploreSection({ title, icon: Icon, children, defaultOpen = true }) {
  const [isOpen, setIsOpen] = useState(defaultOpen)
  
  return (
    <div className="bg-surface-900 border border-surface-800 rounded-xl overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-6 py-4 flex items-center justify-between hover:bg-surface-800 transition-colors"
      >
        <div className="flex items-center gap-3">
          <Icon size={20} className="text-accent-400" />
          <h2 className="text-lg font-semibold">{title}</h2>
        </div>
        <ChevronRight 
          size={20} 
          className={`text-surface-500 transition-transform ${isOpen ? 'rotate-90' : ''}`} 
        />
      </button>
      {isOpen && (
        <div className="px-6 py-4 border-t border-surface-800">
          {children}
        </div>
      )}
    </div>
  )
}

export default function Explore() {
  const { orgId } = useParams()
  const [selectedRepoId, setSelectedRepoId] = useState(null)
  const [repoSearch, setRepoSearch] = useState('')
  const [entryPointSearch, setEntryPointSearch] = useState('')
  const [fileSearch, setFileSearch] = useState('')
  const [selectedEntryPointIds, setSelectedEntryPointIds] = useState([])
  const [selectedFileId, setSelectedFileId] = useState(null)
  
  // Fetch org
  const { data: org } = useQuery({
    queryKey: ['org', orgId],
    queryFn: () => api.getOrg(orgId),
    enabled: !!orgId,
  })
  
  // Fetch repos
  const { data: repos, isLoading: reposLoading } = useQuery({
    queryKey: ['orgRepos', orgId, repoSearch],
    queryFn: () => api.listReposForOrg(orgId, { search: repoSearch || undefined }),
    enabled: !!orgId,
  })
  
  // Fetch entry points
  const { data: entryPoints, isLoading: entryPointsLoading } = useQuery({
    queryKey: ['entryPoints', orgId, selectedRepoId, entryPointSearch],
    queryFn: () => api.listEntryPointsForRepo(orgId, selectedRepoId, { search: entryPointSearch || undefined }),
    enabled: !!orgId && !!selectedRepoId,
  })
  
  // Fetch files
  const { data: files, isLoading: filesLoading } = useQuery({
    queryKey: ['files', orgId, selectedRepoId, fileSearch],
    queryFn: () => api.listFilesForRepo(orgId, selectedRepoId, { search: fileSearch || undefined }),
    enabled: !!orgId && !!selectedRepoId,
  })
  
  // Fetch flows
  const { data: flows, isLoading: flowsLoading } = useQuery({
    queryKey: ['flows', orgId, selectedRepoId, selectedEntryPointIds],
    queryFn: () => api.getFlowsForEntryPoints(orgId, selectedRepoId, selectedEntryPointIds),
    enabled: !!orgId && !!selectedRepoId && selectedEntryPointIds.length > 0,
  })
  
  // Fetch file detail
  const { data: fileDetail, isLoading: fileDetailLoading } = useQuery({
    queryKey: ['fileDetail', orgId, selectedRepoId, selectedFileId],
    queryFn: () => api.getFileDetail(orgId, selectedRepoId, selectedFileId),
    enabled: !!orgId && !!selectedRepoId && !!selectedFileId,
  })
  
  const toggleEntryPoint = (epId) => {
    setSelectedEntryPointIds(prev => 
      prev.includes(epId) 
        ? prev.filter(id => id !== epId)
        : [...prev, epId]
    )
  }
  
  return (
    <div className="p-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 bg-accent-500/10 rounded-lg">
            <Sparkles size={24} className="text-accent-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">AI Exploration</h1>
            <p className="text-surface-400 mt-1">
              Explore repositories, entry points, files, and flows like an AI agent
            </p>
          </div>
        </div>
        {org && (
          <div className="flex items-center gap-2 text-sm text-surface-500">
            <Building2 size={14} />
            <span>{org.name}</span>
            <ChevronRight size={14} />
            <span className="font-mono">{orgId}</span>
          </div>
        )}
      </div>
      
      {/* Repositories Section */}
      <ExploreSection title="Repositories" icon={Database} defaultOpen={true}>
        <div className="space-y-4">
          <div className="relative">
            <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-400" />
            <input
              type="text"
              value={repoSearch}
              onChange={(e) => setRepoSearch(e.target.value)}
              placeholder="Search repos by name or description (supports regex)..."
              className="w-full bg-surface-800 border border-surface-700 rounded-lg pl-10 pr-4 py-2.5 text-sm focus:outline-none focus:border-accent-500"
            />
          </div>
          
          {reposLoading && (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="animate-spin text-accent-400" size={24} />
            </div>
          )}
          
          {repos && repos.length === 0 && (
            <p className="text-center py-8 text-surface-500">No repositories found</p>
          )}
          
          {repos && repos.length > 0 && (
            <div className="space-y-2">
              {repos.map((repo) => (
                <button
                  key={repo.id}
                  onClick={() => setSelectedRepoId(repo.id)}
                  className={`w-full text-left p-4 rounded-lg border transition-colors ${
                    selectedRepoId === repo.id
                      ? 'bg-accent-500/10 border-accent-500/50'
                      : 'bg-surface-800 border-surface-700 hover:border-surface-600'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="font-semibold">{repo.name}</h3>
                        <span className="text-xs px-2 py-0.5 bg-surface-700 rounded">
                          {repo.status}
                        </span>
                      </div>
                      {repo.description && (
                        <p className="text-sm text-surface-400 mb-2">{repo.description}</p>
                      )}
                      <div className="flex items-center gap-4 text-xs text-surface-500">
                        <span>{repo.total_files} files</span>
                        {repo.languages && repo.languages.length > 0 && (
                          <span>{repo.languages.join(', ')}</span>
                        )}
                      </div>
                    </div>
                    <ChevronRight size={16} className="text-surface-600 ml-2" />
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </ExploreSection>
      
      {selectedRepoId && (
        <>
          {/* Entry Points Section */}
          <ExploreSection title="Entry Points" icon={Route} defaultOpen={true}>
            <div className="space-y-4">
              <div className="relative">
                <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-400" />
                <input
                  type="text"
                  value={entryPointSearch}
                  onChange={(e) => setEntryPointSearch(e.target.value)}
                  placeholder="Search entry points (supports regex)..."
                  className="w-full bg-surface-800 border border-surface-700 rounded-lg pl-10 pr-4 py-2.5 text-sm focus:outline-none focus:border-accent-500"
                />
              </div>
              
              {entryPointsLoading && (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="animate-spin text-accent-400" size={24} />
                </div>
              )}
              
              {entryPoints && entryPoints.length === 0 && (
                <p className="text-center py-8 text-surface-500">No entry points found</p>
              )}
              
              {entryPoints && entryPoints.length > 0 && (
                <div className="space-y-2">
                  {entryPoints.map((ep) => (
                    <label
                      key={ep.id}
                      className={`flex items-start gap-3 p-4 rounded-lg border cursor-pointer transition-colors ${
                        selectedEntryPointIds.includes(ep.id)
                          ? 'bg-accent-500/10 border-accent-500/50'
                          : 'bg-surface-800 border-surface-700 hover:border-surface-600'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={selectedEntryPointIds.includes(ep.id)}
                        onChange={() => toggleEntryPoint(ep.id)}
                        className="mt-1"
                      />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <h3 className="font-semibold">{ep.name}</h3>
                          <span className="text-xs px-2 py-0.5 bg-accent-600/20 text-accent-400 rounded">
                            {ep.entry_point_type}
                          </span>
                          <span className="text-xs px-2 py-0.5 bg-surface-700 rounded">
                            {ep.framework}
                          </span>
                        </div>
                        {ep.description && (
                          <p className="text-sm text-surface-400 mb-2">{ep.description}</p>
                        )}
                        <div className="flex items-center gap-4 text-xs text-surface-500">
                          <span>Confidence: {(ep.ai_confidence * 100).toFixed(0)}%</span>
                          {ep.metadata?.path && (
                            <span className="font-mono">{ep.metadata.path}</span>
                          )}
                        </div>
                      </div>
                    </label>
                  ))}
                </div>
              )}
            </div>
          </ExploreSection>
          
          {/* Flows Section */}
          {selectedEntryPointIds.length > 0 && (
            <ExploreSection title="Entry Point Flows" icon={GitBranch} defaultOpen={true}>
              {flowsLoading && (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="animate-spin text-accent-400" size={24} />
                </div>
              )}
              
              {flows && flows.length === 0 && (
                <p className="text-center py-8 text-surface-500">
                  No flows found for selected entry points. Generate flows from the Entry Points tab.
                </p>
              )}
              
              {flows && flows.length > 0 && (
                <div className="space-y-6">
                  {flows.map((flow) => (
                    <div key={flow.entry_point_id} className="bg-surface-800 rounded-lg p-5">
                      <h3 className="text-lg font-semibold mb-3">{flow.flow_name}</h3>
                      <p className="text-sm text-surface-400 mb-4">{flow.technical_summary}</p>
                      
                      {flow.file_paths && flow.file_paths.length > 0 && (
                        <div className="mb-4">
                          <h4 className="text-sm font-medium text-surface-300 mb-2">
                            Files Involved ({flow.file_paths.length})
                          </h4>
                          <div className="flex flex-wrap gap-2">
                            {flow.file_paths.map((path, idx) => (
                              <span
                                key={idx}
                                className="px-2 py-1 bg-surface-900 rounded text-xs font-mono text-surface-300"
                              >
                                {path}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                      
                      <div className="space-y-4">
                        {flow.steps.map((step) => (
                          <div key={step.step_number} className="bg-surface-900 rounded-lg p-4">
                            <div className="flex items-start gap-3 mb-2">
                              <div className="flex-shrink-0 w-8 h-8 rounded-full bg-accent-600/20 text-accent-400 flex items-center justify-center text-sm font-semibold">
                                {step.step_number}
                              </div>
                              <div className="flex-1">
                                <h4 className="font-semibold mb-1">{step.title}</h4>
                                <p className="text-sm text-surface-400 mb-3">{step.description}</p>
                                
                                {step.important_code_snippets && step.important_code_snippets.length > 0 && (
                                  <div className="space-y-2">
                                    {step.important_code_snippets.map((snippet, idx) => (
                                      <CodeBlock
                                        key={idx}
                                        code={snippet.code}
                                        language={snippet.file_path.split('.').pop()}
                                        title={`${snippet.symbol_name} - ${snippet.file_path}`}
                                      />
                                    ))}
                                  </div>
                                )}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </ExploreSection>
          )}
          
          {/* Files Section */}
          <ExploreSection title="Files" icon={FileCode} defaultOpen={false}>
            <div className="space-y-4">
              <div className="relative">
                <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-400" />
                <input
                  type="text"
                  value={fileSearch}
                  onChange={(e) => setFileSearch(e.target.value)}
                  placeholder="Search files by path (supports regex)..."
                  className="w-full bg-surface-800 border border-surface-700 rounded-lg pl-10 pr-4 py-2.5 text-sm focus:outline-none focus:border-accent-500"
                />
              </div>
              
              {filesLoading && (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="animate-spin text-accent-400" size={24} />
                </div>
              )}
              
              {files && files.length === 0 && (
                <p className="text-center py-8 text-surface-500">No files found</p>
              )}
              
              {files && files.length > 0 && (
                <div className="space-y-2 max-h-96 overflow-y-auto">
                  {files.map((file) => (
                    <button
                      key={file.id}
                      onClick={() => setSelectedFileId(file.id)}
                      className={`w-full text-left p-3 rounded-lg border transition-colors ${
                        selectedFileId === file.id
                          ? 'bg-accent-500/10 border-accent-500/50'
                          : 'bg-surface-800 border-surface-700 hover:border-surface-600'
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <FileCode size={16} className="text-surface-500" />
                        <span className="font-mono text-sm">{file.relative_path}</span>
                        <span className="text-xs text-surface-500 ml-auto">{file.language}</span>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </ExploreSection>
          
          {/* File Detail Section */}
          {selectedFileId && (
            <ExploreSection title="File Content" icon={FileText} defaultOpen={true}>
              {fileDetailLoading && (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="animate-spin text-accent-400" size={24} />
                </div>
              )}
              
              {fileDetail && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-semibold mb-1">{fileDetail.relative_path}</h3>
                      <div className="flex items-center gap-4 text-sm text-surface-500">
                        <span>Language: {fileDetail.language}</span>
                        <span className="font-mono">Hash: {fileDetail.content_hash.slice(0, 8)}...</span>
                      </div>
                    </div>
                    <CopyButton text={fileDetail.content || ''} />
                  </div>
                  
                  {fileDetail.content && (
                    <CodeBlock
                      code={fileDetail.content}
                      language={fileDetail.language}
                      title="File Content"
                    />
                  )}
                </div>
              )}
            </ExploreSection>
          )}
        </>
      )}
    </div>
  )
}
