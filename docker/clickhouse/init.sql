-- ClickHouse 初始化脚本
-- 创建 AI Agent 可观测性系统所需的数据表

-- 1. agent_traces 表：记录全局链路追踪数据
CREATE TABLE IF NOT EXISTS agent_traces (
    trace_id String,
    span_id String,
    parent_span_id String,
    name String,
    start_time DateTime64(3),
    end_time DateTime64(3),
    duration_ms Float64 MATERIALIZED (end_time - start_time) * 1000,
    attributes String DEFAULT '{}',
    created_at DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(start_time)
ORDER BY (trace_id, start_time)
SETTINGS index_granularity = 8192;

-- 2. llm_metrics 表：记录大模型推理细粒度指标
CREATE TABLE IF NOT EXISTS llm_metrics (
    trace_id String,
    span_id String,
    model_name String,
    prefill_ms Float64,
    decode_ms Float64,
    input_tokens UInt32,
    output_tokens UInt32,
    tps Float64,
    cost_usd Float64 DEFAULT 0,
    created_at DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (model_name, created_at)
SETTINGS index_granularity = 8192;

-- 创建物化视图用于聚合统计（可选优化）
CREATE TABLE IF NOT EXISTS model_stats_daily (
    day Date,
    model_name String,
    total_requests UInt64,
    avg_prefill_ms Float64,
    avg_decode_ms Float64,
    avg_tps Float64,
    total_input_tokens UInt64,
    total_output_tokens UInt64,
    total_cost_usd Float64
) ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(day)
ORDER BY (day, model_name);

CREATE MATERIALIZED VIEW IF NOT EXISTS model_stats_daily_mv
TO model_stats_daily AS
SELECT
    toDate(created_at) AS day,
    model_name,
    count() AS total_requests,
    avg(prefill_ms) AS avg_prefill_ms,
    avg(decode_ms) AS avg_decode_ms,
    avg(tps) AS avg_tps,
    sum(input_tokens) AS total_input_tokens,
    sum(output_tokens) AS total_output_tokens,
    sum(cost_usd) AS total_cost_usd
FROM llm_metrics
GROUP BY day, model_name;
