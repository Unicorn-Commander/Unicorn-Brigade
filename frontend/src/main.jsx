import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { AuthProvider } from './contexts/AuthContext.jsx'
import { initTheme } from './utils/theme'

// Apply the saved theme choice and keep 'system' following the OS. The inline
// script in index.html already set the pre-paint state; this re-affirms it and
// wires the live OS listener.
initTheme()

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <AuthProvider>
      <App />
    </AuthProvider>
  </StrictMode>,
)
