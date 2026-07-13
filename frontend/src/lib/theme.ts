import { useEffect, useState } from 'react'

export type Theme = 'dark' | 'light'

const KEY = 'alphamemoir-theme'

function apply(theme: Theme) {
  const root = document.documentElement
  root.classList.toggle('light', theme === 'light')
}

export function initTheme(): Theme {
  const saved = (localStorage.getItem(KEY) as Theme | null) ?? 'dark'
  apply(saved)
  return saved
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(() => (localStorage.getItem(KEY) as Theme | null) ?? 'dark')

  useEffect(() => {
    apply(theme)
    localStorage.setItem(KEY, theme)
  }, [theme])

  return { theme, toggle: () => setTheme((t) => (t === 'dark' ? 'light' : 'dark')) }
}
