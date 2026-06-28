import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import TraceView from './pages/TraceView'
import MetricsCompare from './pages/MetricsCompare'

function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <aside className="sidebar">
          <h1>Agent-Insight</h1>
          <nav>
            <NavLink to="/" end className={({ isActive }) => isActive ? 'active' : ''}>
              链路跟踪
            </NavLink>
            <NavLink to="/metrics" className={({ isActive }) => isActive ? 'active' : ''}>
              模型效能对比
            </NavLink>
          </nav>
        </aside>
        <main className="main-content">
          <Routes>
            <Route path="/" element={<TraceView />} />
            <Route path="/metrics" element={<MetricsCompare />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

export default App
