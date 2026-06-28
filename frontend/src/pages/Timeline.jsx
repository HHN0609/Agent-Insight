import { useState, useEffect } from 'react'

const API_BASE = '/api/v1'

function Timeline() {
  const [traces, setTraces] = useState([])
  const [selectedTrace, setSelectedTrace] = useState(null)
  const [timelineData, setTimelineData] = useState([])
  const [loading, setLoading] = useState(true)

  // 加载 trace 列表
  useEffect(() => {
    fetch(`${API_BASE}/traces`)
      .then(res => res.json())
      .then(data => {
        if (data.status === 'success') {
          const uniqueTraces = [...new Map(data.data.map(t => [t.trace_id, t])).values()]
          setTraces(uniqueTraces)
        }
      })
      .catch(err => console.error('Failed to load traces:', err))
      .finally(() => setLoading(false))
  }, [])

  // 加载选中的 trace 详情
  useEffect(() => {
    if (!selectedTrace) return
    fetch(`${API_BASE}/traces?trace_id=${selectedTrace}`)
      .then(res => res.json())
      .then(data => {
        if (data.status === 'success') {
          setTimelineData(buildTimeline(data.data || []))
        }
      })
      .catch(err => console.error('Failed to load trace detail:', err))
  }, [selectedTrace])

  return (
    <div>
      <h2 className="page-title">时间线 (Timeline)</h2>

      <div className="trace-selector">
        <select
          value={selectedTrace || ''}
          onChange={e => setSelectedTrace(e.target.value)}
        >
          <option value="">选择一条链路...</option>
          {traces.map(t => (
            <option key={t.trace_id} value={t.trace_id}>
              {t.trace_id.slice(0, 8)}... - {t.name} ({new Date(t.start_time).toLocaleString()})
            </option>
          ))}
        </select>
      </div>

      {loading ? (
        <div className="loading">加载中...</div>
      ) : !selectedTrace ? (
        <div className="loading">请选择一条链路查看时间线</div>
      ) : (
        <div className="timeline-container">
          {timelineData.length === 0 ? (
            <div className="loading">暂无数据</div>
          ) : (
            <div className="timeline">
              {timelineData.map((item, idx) => (
                <div className="timeline-item" key={idx}>
                  <div className="timeline-time">
                    {new Date(item.startTime).toLocaleTimeString()}
                  </div>
                  <div className="timeline-dot" />
                  <div className="timeline-content">
                    <div className="timeline-header">
                      <span className={`timeline-badge ${item.type}`}>
                        {item.type}
                      </span>
                      <span className="timeline-name">{item.name}</span>
                      <span className="timeline-duration">{item.durationMs.toFixed(1)}ms</span>
                    </div>
                    {item.attributes && Object.keys(item.attributes).length > 0 && (
                      <div className="timeline-attrs">
                        {Object.entries(item.attributes).map(([key, val]) => (
                          <span key={key} className="timeline-attr">
                            <strong>{key}:</strong> {String(val)}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function buildTimeline(traces) {
  if (!traces || traces.length === 0) return []

  // 按开始时间排序
  const sorted = [...traces].sort(
    (a, b) => new Date(a.start_time) - new Date(b.start_time)
  )

  return sorted.map(t => {
    const start = new Date(t.start_time).getTime()
    const end = new Date(t.end_time).getTime()
    const durationMs = end - start

    let type = 'trace'
    const attrs = typeof t.attributes === 'string'
      ? JSON.parse(t.attributes || '{}')
      : (t.attributes || {})

    if (t.name === 'llm_metrics' || attrs.model) type = 'llm'
    else if (t.name?.includes('tool')) type = 'tool'
    else if (t.name?.includes('memory')) type = 'memory'

    return {
      name: t.name || 'unknown',
      type,
      startTime: t.start_time,
      endTime: t.end_time,
      durationMs,
      attributes: attrs,
    }
  })
}

export default Timeline
