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
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-surface-900 border border-surface-700 rounded-xl p-6 w-full max-w-md">
        <h2 className="text-xl font-semibold mb-4">Create Organization</h2>
        
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-surface-300 mb-1">
              Organization Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="my-team"
              className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent-500"
              autoFocus
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-surface-300 mb-1">
              Description (optional)
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Team that manages payment services..."
              rows={3}
              className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent-500 resize-none"
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
            disabled={!name || mutation.isPending}
            className="px-4 py-2 bg-accent-500 hover:bg-accent-600 disabled:opacity-50 rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
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
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold">Organizations</h1>
          <p className="text-surface-400 mt-1">Manage your organizations and their repositories</p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-accent-500 hover:bg-accent-600 rounded-lg font-medium transition-colors"
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
        <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-4 text-red-400">
          {error.message}
        </div>
      )}
      
      {orgs && orgs.length === 0 && (
        <div className="text-center py-12 text-surface-400">
          <Building2 size={48} className="mx-auto mb-4 opacity-50" />
          <p>No organizations yet. Create one to get started.</p>
        </div>
      )}
      
      {orgs && orgs.length > 0 && (
        <div className="grid gap-4">
          {orgs.map((org) => (
            <Link
              key={org.id}
              to={`/orgs/${org.id}`}
              className="block bg-surface-900 border border-surface-800 rounded-xl p-5 hover:border-accent-500/50 transition-colors group"
            >
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-4 flex-1 min-w-0">
                  <div className="p-2.5 bg-accent-500/10 rounded-lg mt-0.5">
                    <Building2 size={22} className="text-accent-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-1">
                      <h3 className="text-lg font-semibold group-hover:text-accent-400 transition-colors">
                        {org.name}
                      </h3>
                    </div>
                    {org.description && (
                      <p className="text-sm text-surface-400 mb-2 line-clamp-2">{org.description}</p>
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
                    className="p-2 text-surface-400 hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-colors"
                    title="Delete organization"
                  >
                    <Trash2 size={18} />
                  </button>
                  <ChevronRight size={20} className="text-surface-600 group-hover:text-accent-400 transition-colors" />
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
