import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { Provider } from 'react-redux'
import { Toaster } from 'react-hot-toast'
import './assets/styles/index.css'
import App from './App.jsx'
import { ThemeProvider } from './context/ThemeContext'
import { store } from './store/store'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ThemeProvider>
      <Provider store={store}>
        <App />
        <Toaster
          position="top-right"
          toastOptions={{
            duration: 4000,
            style: {
              background: 'var(--bg-card)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border)',
              fontSize: '13px',
            },
            success: {
              iconTheme: { primary: 'var(--success)', secondary: 'var(--bg-card)' },
            },
            error: {
              duration: 6000,
              iconTheme: { primary: 'var(--danger)', secondary: 'var(--bg-card)' },
            },
          }}
        />
      </Provider>
    </ThemeProvider>
  </StrictMode>,
)
