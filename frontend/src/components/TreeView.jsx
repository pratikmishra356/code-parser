import { useState } from 'react'
import { ChevronRight, ChevronDown, FileCode, Folder, FolderOpen } from 'lucide-react'

export function TreeView({ tree, level = 0, onFileClick }) {
  if (!tree || typeof tree !== 'object') return null

  const entries = Object.entries(tree).sort(([a], [b]) => {
    // Sort: directories first, then files
    const aIsDir = Object.keys(tree[a] || {}).length > 0 && Object.values(tree[a] || {}).every(v => typeof v === 'object')
    const bIsDir = Object.keys(tree[b] || {}).length > 0 && Object.values(tree[b] || {}).every(v => typeof v === 'object')
    
    if (aIsDir && !bIsDir) return -1
    if (!aIsDir && bIsDir) return 1
    return a.localeCompare(b)
  })

  return (
    <div className="font-mono text-sm">
      {entries.map(([name, children]) => {
        const isDirectory = children && typeof children === 'object' && Object.keys(children).length > 0
        const [isOpen, setIsOpen] = useState(level < 2) // Auto-expand first 2 levels
        
        return (
          <div key={name} className="select-none">
            <div
              className={`flex items-center gap-1.5 py-0.5 hover:bg-surface-800/50 rounded px-1 cursor-pointer ${
                level === 0 ? 'font-semibold' : ''
              }`}
              onClick={() => isDirectory && setIsOpen(!isOpen)}
              style={{ paddingLeft: `${level * 16 + 4}px` }}
            >
              {isDirectory ? (
                <>
                  {isOpen ? (
                    <ChevronDown size={14} className="text-surface-500 flex-shrink-0" />
                  ) : (
                    <ChevronRight size={14} className="text-surface-500 flex-shrink-0" />
                  )}
                  {isOpen ? (
                    <FolderOpen size={14} className="text-accent-400 flex-shrink-0" />
                  ) : (
                    <Folder size={14} className="text-accent-400 flex-shrink-0" />
                  )}
                </>
              ) : (
                <>
                  <div className="w-[14px] flex-shrink-0" /> {/* Spacer */}
                  <FileCode size={14} className="text-surface-400 flex-shrink-0" />
                </>
              )}
              <span className={`truncate ${isDirectory ? 'text-accent-300' : 'text-surface-300'}`}>
                {name}
              </span>
            </div>
            
            {isDirectory && isOpen && (
              <TreeView tree={children} level={level + 1} onFileClick={onFileClick} />
            )}
          </div>
        )
      })}
    </div>
  )
}

export function FolderStructureView({ structure }) {
  if (!structure || typeof structure !== 'object') {
    return <p className="text-sm text-surface-500">No folder structure available</p>
  }

  return (
    <div className="bg-surface-900 border border-surface-800 rounded-lg p-4">
      <TreeView tree={structure} />
    </div>
  )
}
