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
      className={`p-1.5 text-surface-500 hover:text-accent-600 hover:bg-surface-100 rounded-lg transition-colors ${className}`}
      title="Copy to clipboard"
    >
      {copied ? <Check size={14} className="text-accent-600" /> : <Copy size={14} />}
    </button>
  )
}

function CodeBlock({ code, language, title }) {
  return (
    <div className="bg-white border border-surface-200 rounded-xl overflow-hidden shadow-sm">
      {title && (
        <div className="px-4 py-2.5 bg-surface-50 border-b border-surface-200 flex items-center justify-between">
          <span className="text-sm font-semibold text-surface-700">{title}</span>
          <CopyButton text={code} />
        </div>
      )}
      <pre className="p-4 overflow-x-auto text-sm font-mono bg-surface-50 text-surface-800">
        <code className={`language-${language}`}>{code}</code>
      </pre>
    </div>
  )
}

function ExploreSection({ title, icon: Icon, children, defaultOpen = true }) {
  const [isOpen, setIsOpen] = useState(defaultOpen)
  
  return (
    <div className="bg-white border border-surface-200 rounded-xl overflow-hidden shadow-sm mb-4">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-6 py-4 flex items-center justify-between hover:bg-surface-50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="p-1.5 bg-accent-50 rounded-lg">
            <Icon size={18} className="text-accent-600" />
          </div>
          <h2 className="text-lg font-semibold text-surface-900">{title}</h2>
        </div>
        <ChevronRight 
          size={20} 
          className={`text-surface-400 transition-transform ${isOpen ? 'rotate-90' : ''}`} 
        />
      </button>
      {isOpen && (
        <div className="px-6 py-5 border-t border-surface-100 bg-surface-50/50">
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
        <div className="flex items-center gap-4 mb-4">
          <div className="p-3 bg-gradient-to-br from-accent-500 to-accent-600 rounded-xl shadow-sm">
            <Sparkles size={24} className="text-white" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-surface-900">AI Exploration</h1>
            <p className="text-surface-600 mt-1.5 text-sm">
              Explore repositories, entry points, files, and flows like an AI agent
            </p>
          </div>
        </div>
        {org && (
          <div className="flex items-center gap-2 text-sm text-surface-600 bg-white px-4 py-2 rounded-lg border border-surface-200 w-fit">
            <Building2 size={14} className="text-accent-600" />
            <span className="font-medium">{org.name}</span>
            <ChevronRight size={14} className="text-surface-400" />
            <span className="font-mono text-xs">{orgId}</span>
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
              className="w-full bg-white border border-surface-200 rounded-lg pl-10 pr-4 py-2.5 text-sm focus:outline-none focus:border-accent-500 focus:ring-2 focus:ring-accent-500/20 text-surface-900 placeholder:text-surface-400"
            />
          </div>
          
          {reposLoading && (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="animate-spin text-accent-400" size={24} />
            </div>
          )}
          
          {repos && repos.length === 0 && (
            <p className="text-center py-8 text-surface-500 text-sm">No repositories found</p>
          )}
          
          {repos && repos.length > 0 && (
            <div className="space-y-2">
              {repos.map((repo) => (
                <button
                  key={repo.id}
                  onClick={() => setSelectedRepoId(repo.id)}
                  className={`w-full text-left p-4 rounded-lg border transition-all ${
                    selectedRepoId === repo.id
                      ? 'bg-accent-50 border-accent-500 shadow-sm'
                      : 'bg-white border-surface-200 hover:border-accent-300 hover:shadow-sm'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="font-semibold">{repo.name}</h3>
                        <span className="text-xs px-2.5 py-1 bg-surface-100 text-surface-700 rounded-md font-medium border border-surface-200">
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
              className="w-full bg-white border border-surface-200 rounded-lg pl-10 pr-4 py-2.5 text-sm focus:outline-none focus:border-accent-500 focus:ring-2 focus:ring-accent-500/20 text-surface-900 placeholder:text-surface-400"
                />
              </div>
              
              {entryPointsLoading && (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="animate-spin text-accent-400" size={24} />
                </div>
              )}
              
              {entryPoints && entryPoints.length === 0 && (
                <p className="text-center py-8 text-surface-500 text-sm">No entry points found</p>
              )}
              
              {entryPoints && entryPoints.length > 0 && (
                <div className="space-y-2">
                  {entryPoints.map((ep) => (
                    <label
                      key={ep.id}
                      className={`flex items-start gap-3 p-4 rounded-lg border cursor-pointer transition-all ${
                        selectedEntryPointIds.includes(ep.id)
                          ? 'bg-accent-50 border-accent-500 shadow-sm'
                          : 'bg-white border-surface-200 hover:border-accent-300 hover:shadow-sm'
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
                          <span className="text-xs px-2.5 py-1 bg-accent-100 text-accent-700 rounded-md font-medium">
                            {ep.entry_point_type}
                          </span>
                          <span className="text-xs px-2.5 py-1 bg-surface-100 text-surface-700 rounded-md font-medium border border-surface-200">
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
                    <div key={flow.entry_point_id} className="bg-white rounded-xl p-6 border border-surface-200 shadow-sm">
                      <h3 className="text-xl font-bold text-surface-900 mb-3">{flow.flow_name}</h3>
                      <p className="text-sm text-surface-600 mb-5 leading-relaxed">{flow.technical_summary}</p>
                      
                      {flow.file_paths && flow.file_paths.length > 0 && (
                        <div className="mb-4">
                          <h4 className="text-sm font-medium text-surface-300 mb-2">
                            Files Involved ({flow.file_paths.length})
                          </h4>
                          <div className="flex flex-wrap gap-2">
                            {flow.file_paths.map((path, idx) => (
                              <span
                                key={idx}
                                className="px-2.5 py-1 bg-surface-100 rounded-md text-xs font-mono text-surface-700 border border-surface-200"
                              >
                                {path}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                      
                      <div className="space-y-4">
                        {flow.steps.map((step) => (
                          <div key={step.step_number} className="bg-surface-50 rounded-xl p-5 border border-surface-200">
                            <div className="flex items-start gap-4 mb-3">
                              <div className="flex-shrink-0 w-9 h-9 rounded-full bg-gradient-to-br from-accent-500 to-accent-600 text-white flex items-center justify-center text-sm font-bold shadow-sm">
                                {step.step_number}
                              </div>
                              <div className="flex-1">
                                <h4 className="font-bold text-surface-900 mb-2 text-base">{step.title}</h4>
                                <p className="text-sm text-surface-600 mb-4 leading-relaxed">{step.description}</p>
                                
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
              className="w-full bg-white border border-surface-200 rounded-lg pl-10 pr-4 py-2.5 text-sm focus:outline-none focus:border-accent-500 focus:ring-2 focus:ring-accent-500/20 text-surface-900 placeholder:text-surface-400"
                />
              </div>
              
              {filesLoading && (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="animate-spin text-accent-400" size={24} />
                </div>
              )}
              
              {files && files.length === 0 && (
                <p className="text-center py-8 text-surface-500 text-sm">No files found</p>
              )}
              
              {files && files.length > 0 && (
                <div className="space-y-2 max-h-96 overflow-y-auto">
                  {files.map((file) => (
                    <button
                      key={file.id}
                      onClick={() => setSelectedFileId(file.id)}
                      className={`w-full text-left p-3 rounded-lg border transition-all ${
                        selectedFileId === file.id
                          ? 'bg-accent-50 border-accent-500 shadow-sm'
                          : 'bg-white border-surface-200 hover:border-accent-300 hover:shadow-sm'
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
