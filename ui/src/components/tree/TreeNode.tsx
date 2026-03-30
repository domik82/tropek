import { ChevronRight } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

export interface TreeNodeBadge {
  type: 'count' | 'version'
  value: string | number
}

export interface TreeNodeProps {
  icon: LucideIcon
  iconColor: string
  label: string
  subtitle?: string
  depth: number
  isExpandable: boolean
  isExpanded: boolean
  isSelected: boolean
  selectionColor?: string
  isGroup?: boolean
  badge?: TreeNodeBadge
  onClick?: () => void
  onToggle?: () => void
  onContextMenu?: (e: React.MouseEvent) => void
  onDoubleClick?: () => void
  trailingAction?: React.ReactNode
  testId?: string
}

export function TreeNode({
  icon: Icon,
  iconColor,
  label,
  subtitle,
  depth,
  isExpandable,
  isExpanded,
  isSelected,
  selectionColor,
  isGroup,
  badge,
  onClick,
  onToggle,
  onContextMenu,
  onDoubleClick,
  trailingAction,
  testId,
}: TreeNodeProps) {
  const paddingLeft = depth * 24
  const selectedPaddingLeft = isSelected ? paddingLeft - 2 : paddingLeft

  return (
    <div
      data-testid={testId}
      data-selected={isSelected ? 'true' : 'false'}
      className={`flex items-center gap-1.5 cursor-pointer transition-colors h-8 group ${
        isSelected ? '' : 'hover:bg-muted/50'
      }`}
      style={{
        paddingLeft: selectedPaddingLeft,
        paddingRight: 8,
        ...(isSelected && selectionColor
          ? { backgroundColor: `${selectionColor}1f`, borderLeft: `2px solid ${selectionColor}` }
          : {}),
      }}
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={e => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick?.() }
      }}
      onContextMenu={onContextMenu}
      onDoubleClick={onDoubleClick}
    >
      {isExpandable ? (
        <button
          data-testid="chevron"
          aria-label={`Toggle ${label}`}
          className={`shrink-0 p-0.5 text-muted-foreground hover:text-foreground transition-transform ${
            isExpanded ? 'rotate-90' : ''
          }`}
          onClick={e => { e.stopPropagation(); onToggle?.() }}
        >
          <ChevronRight className="w-3 h-3" />
        </button>
      ) : (
        <span className="shrink-0 w-4" />
      )}

      <Icon className="w-4 h-4 shrink-0" style={{ color: iconColor }} strokeWidth={2} />

      <span className="truncate flex-1 min-w-0">
        <span
          className={`text-[14px] truncate leading-4 ${
            isGroup ? 'font-semibold' : 'font-normal'
          }`}
        >
          {label}
        </span>
        {subtitle && (
          <span className="block text-[10px] text-muted-foreground truncate leading-3">
            {subtitle}
          </span>
        )}
      </span>

      {trailingAction ? (
        <span className="shrink-0 inline-flex items-center justify-center">
          {badge && (
            badge.type === 'count' ? (
              <span
                className="group-hover:hidden text-[10px] font-semibold min-w-[18px] h-[18px] inline-flex items-center justify-center rounded-full px-1.5"
                style={{
                  backgroundColor: isSelected && selectionColor ? `${selectionColor}33` : '#30363d',
                  color: isSelected && selectionColor ? selectionColor : '#c9d1d9',
                }}
              >
                {badge.value}
              </span>
            ) : (
              <span className="group-hover:hidden text-[10px] text-muted-foreground border border-border rounded px-1.5 py-px">
                {badge.value}
              </span>
            )
          )}
          <span className="hidden group-hover:inline-flex">{trailingAction}</span>
        </span>
      ) : (
        <>
          {badge && (
            badge.type === 'count' ? (
              <span
                className="shrink-0 text-[10px] font-semibold min-w-[18px] h-[18px] inline-flex items-center justify-center rounded-full px-1.5"
                style={{
                  backgroundColor: isSelected && selectionColor ? `${selectionColor}33` : '#30363d',
                  color: isSelected && selectionColor ? selectionColor : '#c9d1d9',
                }}
              >
                {badge.value}
              </span>
            ) : (
              <span className="shrink-0 text-[10px] text-muted-foreground border border-border rounded px-1.5 py-px">
                {badge.value}
              </span>
            )
          )}
        </>
      )}
    </div>
  )
}
