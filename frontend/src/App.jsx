import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import TraceView from './pages/TraceView'
import Timeline from './pages/Timeline'
import PromptReplay from './pages/PromptReplay'
import MetricsCompare from './pages/MetricsCompare'
import StatsDashboard from './pages/StatsDashboard'

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
            <NavLink to="/timeline" className={({ isActive }) => isActive ? 'active' : ''}>
              时间线
            </NavLink>
            <NavLink to="/prompt-replay" className={({ isActive }) => isActive ? 'active' : ''}>
              Prompt 回放
            </NavLink>
            <NavLink to="/metrics" className={({ isActive }) => isActive ? 'active' : ''}>
              模型效能对比
            </NavLink>
            <NavLink to="/stats" className={({ isActive }) => isActive ? 'active' : ''}>
              统计分析
            </NavLink>
          </nav>
        </aside>
        <main className="main-content">
          <Routes>
            <Route path="/" element={<TraceView />} />
            <Route path="/timeline" element={<Timeline />} />
            <Route path="/prompt-replay" element={<PromptReplay />} />
            <Route path="/metrics" element={<MetricsCompare />} />
            <Route path="/stats" element={<StatsDashboard />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

export default App
