'use client';

import { createContext, useContext, useEffect, useState, ReactNode } from 'react';

type Theme = 'light' | 'dark' | 'system';

interface ThemeContextType {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  resolvedTheme: 'light' | 'dark';
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>('system');
  const [systemTheme, setSystemTheme] = useState<'light' | 'dark'>('light');

  const resolvedTheme = theme === 'system' ? systemTheme : theme;

  // Hydrate from URL query or localStorage after mount (avoids SSR mismatch)
  /* eslint-disable react-hooks/set-state-in-effect -- Hydration must happen in effect */
  useEffect(() => {
    let initialTheme: Theme | null = null;
    if (typeof window !== 'undefined') {
      const urlTheme = new URLSearchParams(window.location.search).get('theme');
      if (urlTheme && ['light', 'dark', 'system'].includes(urlTheme)) {
        initialTheme = urlTheme as Theme;
      }
    }
    if (!initialTheme) {
      const stored = localStorage.getItem('theme') as Theme | null;
      if (stored && ['light', 'dark', 'system'].includes(stored)) {
        initialTheme = stored;
      }
    }
    if (initialTheme) {
      setThemeState(initialTheme);
    }
    setSystemTheme(window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  }, []);
  /* eslint-enable react-hooks/set-state-in-effect */

  // Listen to cross-window / parent-frame postMessage for instant theme sync
  useEffect(() => {
    const handleMessage = (e: MessageEvent) => {
      if (e.data && typeof e.data === 'object' && e.data.type === 'SET_THEME') {
        const incoming = e.data.theme;
        if (['light', 'dark', 'system'].includes(incoming)) {
          setThemeState(incoming as Theme);
        }
      }
    };
    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, []);

  // Apply theme to document
  useEffect(() => {
    const root = document.documentElement;
    if (resolvedTheme === 'dark') {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
  }, [resolvedTheme]);

  // Listen to system theme changes
  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleChange = () => {
      setSystemTheme(mediaQuery.matches ? 'dark' : 'light');
    };
    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, []);

  // Save theme to localStorage
  const handleSetTheme = (newTheme: Theme) => {
    setThemeState(newTheme);
    localStorage.setItem('theme', newTheme);
  };

  return (
    <ThemeContext.Provider value={{ theme, setTheme: handleSetTheme, resolvedTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within ThemeProvider');
  }
  return context;
}
