import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import Sidebar from './components/Sidebar'
import Header from './components/Header'
import Dashboard from './pages/Dashboard'
import Signals from './pages/Signals'
import Sentiment from './pages/Sentiment'
import Technicals from './pages/Technicals'
import OnChain from './pages/OnChain'
import Predictions from './pages/Predictions'
import Performance from './pages/Performance'
import Reports from './pages/Reports'
import Backtesting from './pages/Backtesting'

export default function App() {
  return (
    <BrowserRouter>
      <div className="layout">
        <Sidebar />
        <div className="main-content">
          <Header />
          <div className="page-body">
            <Routes>
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard"    element={<Dashboard />} />
              <Route path="/signals"      element={<Signals />} />
              <Route path="/sentiment"    element={<Sentiment />} />
              <Route path="/technicals"   element={<Technicals />} />
              <Route path="/onchain"      element={<OnChain />} />
              <Route path="/predictions"  element={<Predictions />} />
              <Route path="/performance"  element={<Performance />} />
              <Route path="/reports"      element={<Reports />} />
              <Route path="/backtesting"  element={<Backtesting />} />
            </Routes>
          </div>
        </div>
      </div>
      <Toaster
        position="bottom-right"
        toastOptions={{
          style: {
            background: '#101928',
            color: '#E8EAED',
            border: '1px solid #1A2840',
            fontFamily: "'Inter', sans-serif",
            fontSize: '13px',
          },
        }}
      />
    </BrowserRouter>
  )
}
