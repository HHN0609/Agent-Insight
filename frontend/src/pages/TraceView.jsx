import { useState, useEffect } from 'react'

const API_BASE = '/api/v1'

function TraceView() {
  const [traces, setTraces] = useState([])
  const [selectedTrace, setSelectedTrace] = useState(null)
  const [traceList, setTraceList] = useState([])
  const [loading, setLoading] = useState(true)

  // 加载 trace 列表
  useEffect(() => {
    fetch(`${API_BASE}/traces`)
      .then(res => res.json())
      .then(data => {
        if (data.status === 'success') {
          setTraceList(data.data || [])
          // 按 trace_id 去重
          const uniqueTraces = [...new Map(data.data.map(t => [t.trace_id, t])).values()]
          setTraceList(uniqueTraces)
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
          setTraces(data.data || [])
        }
      })
      .catch(err => console.error('Failed to load trace detail:', err))
  }, [selectedTrace])

  // 计算瀑布图数据
  const waterfallData = buildWaterfall(traces)

  return (
    <div>
      <h2 className="page-title">链路跟踪 (Trace View)</h2>

      <div className="trace-selector">
        <select
          value={selectedTrace || ''}
          onChange={e => setSelectedTrace(e.target.value)}
        >
          <option value="">选择一条链路...</option>
          {traceList.map(t => (
            <option key={t.trace_id} value={t.trace_id}>
              {t.trace_id.slice(0, 8)}... - {t.name} ({new Date(t.start_time).toLocaleString()})
            </option>
          ))}
        </select>
      </div>

      {loading ? (
        <div className="loading">加载中...</div>
      ) : !selectedTrace ? (
        <div className="loading">请选择一条链路查看瀑布图</div>
      ) : (
        <div className="waterfall">
          {waterfallData.length === 0 ? (
            <div className="loading">暂无数据</div>
          ) : (
            waterfallData.map((item, idx) => (
              <div className="waterfall-item" key={idx}>
                <div className="waterfall-label" title={item.name}>
                  {'  '.repeat(item.depth)}{item.name}
                </div>
                <div className="waterfall-bar-container">
                  <div
                    className={`waterfall-bar ${item.type}`}
                    style={{
                      left: `${item.offsetPercent}%`,
                      width: `${Math.max(item.durationPercent, 2)}%`,
                    }}
                  >
                    {item.durationPercent > 10 ? `${item.durationMs.toFixed(0)}ms` : ''}
                  </div>
                </div>
                <div className="waterfall-duration">{item.durationMs.toFixed(1)}ms</div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}

function buildWaterfall(traces) {
  if (!traces || traces.length === 0) return []

  // 找到全局时间范围
  const times = traces.flatMap(t => [
    new Date(t.start_time).getTime(),
    new Date(t.end_time).getTime(),
  ])
  const globalStart = Math.min(...times)
  const globalEnd = Math.max(...times)
  const totalDuration = globalEnd - globalStart || 1

  // 构建树形结构
  const spanMap = new Map()
  traces.forEach(t => {
    spanMap.set(t.span_id, { ...t, children: [] })
  })

  const roots = []
  traces.forEach(t => {
    const span = spanMap.get(t.span_id)
    if (t.parent_span_id && spanMap.has(t.parent_span_id)) {
      spanMap.get(t.parent_span_id).children.push(span)
    } else {
      roots.push(span)
    }
  })

  // 扁平化为瀑布图数据
  const result = []
  function flatten(spans, depth) {
    spans.forEach(span => {
      const start = new Date(span.start_time).getTime()
      const end = new Date(span.end_time).getTime()
      const durationMs = end - start
      const offsetPercent = ((start - globalStart) / totalDuration) * 100
      const durationPercent = (durationMs / totalDuration) * 100

      let type = 'trace'
      const attrs = typeof span.attributes === 'string'
        ? JSON.parse(span.attributes || '{}')
        : (span.attributes || {})
      if (span.name === 'llm_metrics' || attrs.model) type = 'llm'
      else if (span.name?.includes('tool')) type = 'tool'

      result.push({
        name: span.name || 'unknown',
        type,
        depth,
        offsetPercent,
        durationPercent,
        durationMs,
      })

      flatten(span.children, depth + 1)
    })
  }

  flatten(roots, 0)
  return result
}

export default TraceView
