import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Plus, Trash2, Loader2, Building2, ChevronRight, Database } from 'lucide-react'
import { api } from '../api'

function AddOrgModal({ isOpen, onClose }) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const queryClient = useQueryClient()
  
  const mutation = useMutation({
    mutationFn: () => api.createOrg(name, description || undefined),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['orgs'] })
      onClose()
      setName('')
      setDescription('')
    },
  })
  
  if (!isOpen) return null
  
  return (
    <div className="fixed inset-0 bg-black/30 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-white border border-surface-200 rounded-2xl p-6 w-full max-w-md shadow-xl">
        <h2 className="text-xl font-bold text-surface-900 mb-5">Create Organization</h2>
        
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-semibold text-surface-700 mb-2">
              Organization Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="my-team"
              className="w-full bg-white border border-surface-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-accent-500 focus:ring-2 focus:ring-accent-500/20 text-surface-900 placeholder:text-surface-400"
              autoFocus
            />
          </div>
          
          <div>
            <label className="block text-sm font-semibold text-surface-700 mb-2">
              Description (optional)
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Team that manages payment services..."
              rows={3}
              className="w-full bg-white border border-surface-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-accent-500 focus:ring-2 focus:ring-accent-500/20 resize-none text-surface-900 placeholder:text-surface-400"
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
            disabled={!name || mutation.isPending}
            className="px-5 py-2.5 bg-accent-500 hover:bg-accent-600 disabled:opacity-50 rounded-lg text-sm font-semibold text-white transition-all shadow-sm hover:shadow-md flex items-center gap-2"
          >
            {mutation.isPending && <Loader2 size={14} className="animate-spin" />}
            Create Organization
          </button>
        </div>
      </div>
    </div>
  )
}

export default function OrgList() {
  const [showModal, setShowModal] = useState(false)
  const queryClient = useQueryClient()
  
  const { data: orgs, isLoading, error } = useQuery({
    queryKey: ['orgs'],
    queryFn: api.listOrgs,
  })
  
  const deleteMutation = useMutation({
    mutationFn: api.deleteOrg,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['orgs'] }),
  })
  
  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-surface-900 mb-2">Organizations</h1>
          <p className="text-surface-600 text-sm">Manage your organizations and their repositories</p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-2 px-5 py-2.5 bg-accent-500 hover:bg-accent-600 rounded-lg font-semibold text-white transition-all shadow-sm hover:shadow-md"
        >
          <Plus size={18} />
          New Organization
        </button>
      </div>
      
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
      
      {orgs && orgs.length === 0 && (
        <div className="text-center py-16 bg-white rounded-2xl border border-surface-200">
          <div className="p-4 bg-accent-50 rounded-full w-fit mx-auto mb-4">
            <Building2 size={40} className="text-accent-600" />
          </div>
          <p className="text-surface-600 font-medium">No organizations yet. Create one to get started.</p>
        </div>
      )}
      
      {orgs && orgs.length > 0 && (
        <div className="grid gap-4">
          {orgs.map((org) => (
            <Link
              key={org.id}
              to={`/orgs/${org.id}`}
              className="block bg-white border border-surface-200 rounded-xl p-6 hover:border-accent-300 hover:shadow-md transition-all group"
            >
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-4 flex-1 min-w-0">
                  <div className="p-3 bg-gradient-to-br from-accent-500 to-accent-600 rounded-xl shadow-sm">
                    <Building2 size={22} className="text-white" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-lg font-bold text-surface-900 group-hover:text-accent-600 transition-colors">
                        {org.name}
                      </h3>
                    </div>
                    {org.description && (
                      <p className="text-sm text-surface-600 mb-2 line-clamp-2">{org.description}</p>
                    )}
                    <p className="text-xs text-surface-500 font-mono">{org.id}</p>
                  </div>
                </div>
                
                <div className="flex items-center gap-2 ml-4">
                  <button
                    onClick={(e) => {
                      e.preventDefault()
                      e.stopPropagation()
                      if (confirm(`Delete organization "${org.name}" and all its repositories?`)) {
                        deleteMutation.mutate(org.id)
                      }
                    }}
                    className="p-2 text-surface-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                    title="Delete organization"
                  >
                    <Trash2 size={18} />
                  </button>
                  <ChevronRight size={20} className="text-surface-400 group-hover:text-accent-600 transition-colors" />
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
      
      <AddOrgModal isOpen={showModal} onClose={() => setShowModal(false)} />
    </div>
  )
}
