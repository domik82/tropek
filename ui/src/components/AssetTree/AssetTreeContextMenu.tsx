import { useEffect, useRef, useCallback } from 'react'
import {
  Pencil, Settings, FolderPlus, Plus, Link, ArrowUpRight,
  Copy, Trash2, BarChart3, X,
} from 'lucide-react'
import type { TreeMode, ContextMenuState, MenuItemDef } from './types'

const ICON_MAP: Record<string, typeof Pencil> = {
  Pencil, Settings, FolderPlus, Plus, Link, ArrowUpRight,
  Copy, Trash2, BarChart3, X,
}

const GROUP_MENU_ITEMS: MenuItemDef[] = [
  { label: 'Rename', icon: 'Pencil', iconColor: 'text-amber-400', action: 'rename', shortcut: 'F2' },
  { label: 'Edit details\u2026', icon: 'Settings', iconColor: 'text-muted-foreground', action: 'editDetails' },
  { label: 'Add subgroup', icon: 'FolderPlus', iconColor: 'text-orange-400', action: 'addSubgroup', separator: true },
  { label: 'Add asset to group', icon: 'Plus', iconColor: 'text-[#2DD4A0]', action: 'addAssetToGroup', modes: ['navigator', 'assets'] },
  { label: 'Link SLO\u2026', icon: 'Link', iconColor: 'text-purple-400', action: 'linkSlo', modes: ['slo'] },
  { label: 'Move to\u2026 (coming soon)', icon: 'ArrowUpRight', iconColor: 'text-muted-foreground', action: 'moveGroup', separator: true, disabled: true },
  { label: 'Duplicate group (coming soon)', icon: 'Copy', iconColor: 'text-muted-foreground', action: 'duplicateGroup', disabled: true },
  { label: 'Delete group', icon: 'Trash2', iconColor: 'text-red-400', action: 'deleteGroup', separator: true, destructive: true },
]

const ASSET_MENU_ITEMS: MenuItemDef[] = [
  { label: 'View evaluations', icon: 'BarChart3', iconColor: 'text-blue-400', action: 'viewEvaluations' },
  { label: 'Move to group\u2026 (coming soon)', icon: 'ArrowUpRight', iconColor: 'text-muted-foreground', action: 'moveGroup', separator: true, disabled: true },
  { label: 'Remove from group', icon: 'X', iconColor: 'text-muted-foreground', action: 'removeFromGroup' },
  { label: 'Edit asset\u2026', icon: 'Pencil', iconColor: 'text-amber-400', action: 'editAsset', separator: true },
  { label: 'Delete asset', icon: 'Trash2', iconColor: 'text-red-400', action: 'deleteAsset', destructive: true },
]

interface Props {
  state: ContextMenuState
  mode: TreeMode
  onAction: (action: string, targetName: string) => void
  onClose: () => void
}

export function AssetTreeContextMenu({ state, mode, onAction, onClose }: Props) {
  const menuRef = useRef<HTMLDivElement>(null)

  const handleClickOutside = useCallback((e: MouseEvent) => {
    if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
      onClose()
    }
  }, [onClose])

  useEffect(() => {
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [handleClickOutside])

  // Close on Escape
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [onClose])

  const items = state.target.type === 'group' ? GROUP_MENU_ITEMS : ASSET_MENU_ITEMS
  const visibleItems = items.filter(item => !item.modes || item.modes.includes(mode))

  // Clamp position to viewport
  const menuWidth = 240
  const menuHeight = visibleItems.length * 34 + 16
  const x = Math.min(state.x, window.innerWidth - menuWidth - 8)
  const y = Math.min(state.y, window.innerHeight - menuHeight - 8)

  return (
    <div
      ref={menuRef}
      className="fixed z-50 bg-popover border border-border rounded-lg shadow-lg py-1.5 min-w-[220px]"
      style={{ left: x, top: y, fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif" }}
    >
      {visibleItems.map((item, i) => {
        const Icon = ICON_MAP[item.icon]
        return (
          <div key={item.action}>
            {item.separator && i > 0 && <div className="my-1.5 mx-2 border-t border-border" />}
            <button
              className={`w-full px-3 py-2 text-[14px] flex items-center gap-3 transition-colors ${
                item.disabled
                  ? 'opacity-40 cursor-not-allowed'
                  : item.destructive
                    ? 'text-destructive hover:bg-accent cursor-pointer'
                    : 'text-popover-foreground hover:bg-accent cursor-pointer'
              }`}
              disabled={item.disabled}
              onClick={() => {
                if (!item.disabled) {
                  onAction(item.action, state.target.name)
                  onClose()
                }
              }}
            >
              {Icon && (
                <Icon className={`w-[18px] h-[18px] shrink-0 ${
                  item.disabled ? '' : (item.iconColor ?? 'text-muted-foreground')
                }`} />
              )}
              <span className="flex-1 text-left">{item.label}</span>
              {item.shortcut && (
                <span className="text-xs text-muted-foreground ml-auto">{item.shortcut}</span>
              )}
            </button>
          </div>
        )
      })}
    </div>
  )
}
