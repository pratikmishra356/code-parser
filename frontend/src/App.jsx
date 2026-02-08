import { Routes, Route, Link, useLocation } from 'react-router-dom'
import { Code2, Building2, Database, ChevronRight, Sparkles } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { api } from './api'
import OrgList from './pages/OrgList'
import RepoList from './pages/RepoList'
import RepoDetail from './pages/RepoDetail'
import SymbolDetail from './pages/SymbolDetail'
import SymbolLookup from './pages/SymbolLookup'
import Explore from './pages/Explore'

function NavLink({ to, children, icon: Icon }) {
  const location = useLocation()
  const isActive = location.pathname === to || location.pathname.startsWith(to + '/')
  
  return (
    <Link
      to={to}
      className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
        isActive 
          ? 'bg-accent-500/20 text-accent-400' 
          : 'text-surface-200 hover:bg-surface-800'
      }`}
    >
      {Icon && <Icon size={18} />}
      {children}
    </Link>
  )
}

function Breadcrumb() {
  const location = useLocation()
  const segments = location.pathname.split('/').filter(Boolean)
  
  // Build breadcrumb items from URL segments
  const items = []
  
  if (segments[0] === 'orgs' && segments[1]) {
    items.push({ label: 'Organizations', to: '/' })
    // We'll show the org name from context
    if (segments.length >= 2) {
      items.push({ label: 'Repos', to: `/orgs/${segments[1]}`, isOrgLink: true, orgId: segments[1] })
    }
    if (segments[2] === 'repos' && segments[3]) {
      items.push({ label: 'Detail', to: `/orgs/${segments[1]}/repos/${segments[3]}`, isRepoLink: true })
    }
  }
  
  if (items.length === 0) return null
  
  return (
    <div className="flex items-center gap-1 text-sm text-surface-500 px-2 mb-2">
      {items.map((item, i) => (
        <div key={i} className="flex items-center gap-1">
          {i > 0 && <ChevronRight size={12} />}
          <Link to={item.to} className="hover:text-accent-400 transition-colors">
            {item.isOrgLink ? <OrgName orgId={item.orgId} /> : item.label}
          </Link>
        </div>
      ))}
    </div>
  )
}

function OrgName({ orgId }) {
  const { data: org } = useQuery({
    queryKey: ['org', orgId],
    queryFn: () => api.getOrg(orgId),
    staleTime: 60000,
  })
  return <span>{org?.name || orgId?.slice(0, 8) + '...'}</span>
}

function SidebarNav() {
  const location = useLocation()
  const segments = location.pathname.split('/').filter(Boolean)
  const orgId = segments[0] === 'orgs' && segments[1] ? segments[1] : null
  
  return (
    <nav className="flex flex-col gap-1">
      <NavLink to="/" icon={Building2}>Organizations</NavLink>
      <NavLink to="/repos" icon={Database}>All Repositories</NavLink>
      {orgId && <NavLink to={`/orgs/${orgId}/explore`} icon={Sparkles}>AI Explore</NavLink>}
    </nav>
  )
}

export default function App() {
  return (
    <div className="min-h-screen flex">
      {/* Sidebar */}
      <aside className="w-64 bg-surface-900 border-r border-surface-800 p-4 flex flex-col">
        <div className="flex items-center gap-3 px-2 py-4 mb-6">
          <div className="p-2 bg-accent-500/20 rounded-lg">
            <Code2 className="text-accent-400" size={24} />
          </div>
          <div>
            <h1 className="font-semibold text-lg">Code Parser</h1>
            <p className="text-xs text-surface-400">AST Explorer</p>
          </div>
        </div>
        
        <SidebarNav />
        
        <Breadcrumb />
        
        <div className="mt-auto pt-4 border-t border-surface-800">
          <p className="text-xs text-surface-500 px-2">
            Multi-tenant code parsing with AST analysis and call graphs
          </p>
        </div>
      </aside>
      
      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Routes>
          {/* Organization routes */}
          <Route path="/" element={<OrgList />} />
          <Route path="/orgs/:orgId" element={<RepoList />} />
          <Route path="/orgs/:orgId/explore" element={<Explore />} />
          <Route path="/orgs/:orgId/repos/:repoId" element={<RepoDetail />} />
          <Route path="/orgs/:orgId/repos/:repoId/symbols/:symbolId" element={<SymbolDetail />} />
          <Route path="/orgs/:orgId/repos/:repoId/lookup" element={<SymbolLookup />} />
          
          {/* Legacy routes (all repos view) */}
          <Route path="/repos" element={<RepoList />} />
          <Route path="/repos/:repoId" element={<RepoDetail />} />
          <Route path="/repos/:repoId/symbols/:symbolId" element={<SymbolDetail />} />
          <Route path="/repos/:repoId/lookup" element={<SymbolLookup />} />
        </Routes>
      </main>
    </div>
  )
}
