import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react'
import type { Theme } from './theme'
import { clampFontSize } from './theme-utils'

const FONT_DEFAULT = 18
const THEME_DEFAULT: Theme = 'forest'

interface ThemeCtx {
  theme:       Theme
  setTheme:    (t: Theme) => void
  isDark:      boolean
  fontSize:    number
  setFontSize: (n: number) => void
}

const Ctx = createContext<ThemeCtx | null>(null)

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, _setTheme] = useState<Theme>(() =>
    (localStorage.getItem('tropek-theme') as Theme | null) ?? THEME_DEFAULT
  )
  const [fontSize, _setFontSize] = useState<number>(() =>
    clampFontSize(Number(localStorage.getItem('tropek-font-size')) || FONT_DEFAULT)
  )

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('tropek-theme', theme)
  }, [theme])

  useEffect(() => {
    document.documentElement.style.fontSize = `${fontSize}px`
    localStorage.setItem('tropek-font-size', String(fontSize))
  }, [fontSize])

  function setTheme(t: Theme) { _setTheme(t) }
  function setFontSize(n: number) { _setFontSize(clampFontSize(n)) }

  return (
    <Ctx.Provider value={{ theme, setTheme, isDark: theme !== 'corporate', fontSize, setFontSize }}>
      {children}
    </Ctx.Provider>
  )
}

export function useTheme(): ThemeCtx {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useTheme must be used inside ThemeProvider')
  return ctx
}
