import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'
import { useUpdatePreferences } from '@/hooks/queries/useUser'
import type { CustomTheme } from '@/types/api'

export type ThemeMode = 'light' | 'dark' | 'black' | 'high-contrast' | 'deuteranopia' | 'protanopia' | 'tritanopia' | 'custom'

interface ThemeContextType {
  theme: ThemeMode
  setTheme: (theme: ThemeMode) => void
  customTheme: CustomTheme | null
  setCustomTheme: (theme: CustomTheme | null) => void
  applyCustomTheme: (colors: Record<string, string>) => void
  exportTheme: () => string
  importTheme: (json: string) => boolean
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined)

const THEME_MODES: ThemeMode[] = ['light', 'dark', 'black', 'high-contrast', 'deuteranopia', 'protanopia', 'tritanopia', 'custom']

export function ThemeProvider({ children }: { children: ReactNode }) {
  const updatePreferences = useUpdatePreferences()

  const [theme, setThemeState] = useState<ThemeMode>(() => {
    const stored = localStorage.getItem('theme')
    if (stored && THEME_MODES.includes(stored as ThemeMode)) {
      return stored as ThemeMode
    }
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  })

  const [customTheme, setCustomThemeState] = useState<CustomTheme | null>(() => {
    const stored = localStorage.getItem('customTheme')
    return stored ? JSON.parse(stored) : null
  })

  const setTheme = (newTheme: ThemeMode) => {
    setThemeState(newTheme)
    localStorage.setItem('theme', newTheme)
    
    // Update document class
    document.documentElement.classList.remove(...THEME_MODES)
    document.documentElement.classList.add(newTheme)

    // Sync to backend (with fallback to localStorage)
    updatePreferences.mutate({ theme: newTheme })
  }

  const setCustomTheme = (theme: CustomTheme | null) => {
    setCustomThemeState(theme)
    if (theme) {
      localStorage.setItem('customTheme', JSON.stringify(theme))
      applyCustomTheme(theme.colors)
    } else {
      localStorage.removeItem('customTheme')
    }

    // Sync to backend
    updatePreferences.mutate({ custom_theme: theme || undefined })
  }

  const applyCustomTheme = (colors: Record<string, string>) => {
    // Apply CSS custom properties
    Object.entries(colors).forEach(([key, value]) => {
      document.documentElement.style.setProperty(`--${key}`, value)
    })
  }

  const exportTheme = (): string => {
    const themeData = {
      theme,
      customTheme,
    }
    return JSON.stringify(themeData, null, 2)
  }

  const importTheme = (json: string): boolean => {
    try {
      const data = JSON.parse(json)
      if (data.theme && THEME_MODES.includes(data.theme)) {
        setTheme(data.theme)
      }
      if (data.customTheme) {
        setCustomTheme(data.customTheme)
      }
      return true
    } catch (error) {
      console.error('Failed to import theme:', error)
      return false
    }
  }

  // Sync with system preference changes
  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    const handleChange = (e: MediaQueryListEvent) => {
      const stored = localStorage.getItem('theme')
      if (!stored) {
        setTheme(e.matches ? 'dark' : 'light')
      }
    }
    
    mediaQuery.addEventListener('change', handleChange)
    return () => mediaQuery.removeEventListener('change', handleChange)
  }, [])

  // Apply custom theme on mount
  useEffect(() => {
    if (theme === 'custom' && customTheme) {
      applyCustomTheme(customTheme.colors)
    }
  }, [theme, customTheme])

  const value: ThemeContextType = {
    theme,
    setTheme,
    customTheme,
    setCustomTheme,
    applyCustomTheme,
    exportTheme,
    importTheme,
  }

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme() {
  const context = useContext(ThemeContext)
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider')
  }
  return context
}
