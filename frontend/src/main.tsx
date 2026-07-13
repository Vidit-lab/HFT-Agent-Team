import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import './index.css'
import App from './App.tsx'
import { initTheme } from './lib/theme'

initTheme()

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      // Short, and refetch on focus. The backend is a live system that can be
      // driven from outside this tab -- a cycle, a reflect, a curl -- and with a
      // long staleTime and focus-refetch off, the UI would confidently serve a
      // cached answer that the system had already moved past.
      staleTime: 3_000,
      refetchOnWindowFocus: true,
      refetchOnMount: true,
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
