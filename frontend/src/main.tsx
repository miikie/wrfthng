import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './index.css'
import { useBuildStore } from './stores/buildStore'
import { decodeState, encodeState } from './utils/url'

// A shared link wins over whatever this browser last had open.
const fromUrl = decodeState(window.location.search)
if (fromUrl) {
  useBuildStore.setState((s) => ({
    builds: [fromUrl.a, fromUrl.b ?? s.builds[1]],
    compare: fromUrl.b !== null,
    sharedEnemy: fromUrl.b ? fromUrl.sharedEnemy : s.sharedEnemy,
    view: fromUrl.view,
  }))
}

// Keep the address bar pointing at the current build so it can be shared.
let urlTimer = 0
const syncUrl = () => {
  const s = useBuildStore.getState()
  const next = `${window.location.pathname}?${encodeState(s)}`
  if (next !== window.location.pathname + window.location.search) {
    window.history.replaceState(null, '', next)
  }
}
useBuildStore.subscribe(() => {
  clearTimeout(urlTimer)
  urlTimer = window.setTimeout(syncUrl, 300)
})
syncUrl()

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false } },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
)
