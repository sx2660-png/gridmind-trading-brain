/** Readable workflow result renderer. */

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatCurvePreview(values, maxHead = 4, maxTail = 2) {
  if (!Array.isArray(values) || values.length === 0) return "—";
  if (values.length <= maxHead + maxTail) {
    return values.map((v) => Number(v).toFixed(2)).join(", ");
  }
  const head = values.slice(0, maxHead).map((v) => Number(v).toFixed(2));
  const tail = values.slice(-maxTail).map((v) => Number(v).toFixed(2));
  return `${head.join(", ")} … ${tail.join(", ")}（共 ${values.length} 点）`;
}

function renderKvRows(rows) {
  return rows
    .filter(([, value]) => value !== undefined && value !== null && value !== "")
    .map(
      ([label, value]) =>
        `<div class="kv-row"><span class="kv-label">${escapeHtml(label)}</span><span class="kv-value">${escapeHtml(value)}</span></div>`
    )
    .join("");
}

function renderList(items, emptyText = "无") {
  if (!items?.length) return `<p class="muted">${emptyText}</p>`;
  return `<ul class="bullet-list">${items
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("")}</ul>`;
}

function renderEvidence(evidence) {
  if (!evidence?.length) {
    return `<p class="muted">未检索到政策片段</p>`;
  }
  return evidence
    .map(
      (item, index) => `
      <details class="evidence-item">
        <summary>
          <span class="evidence-rank">#${index + 1}</span>
          <span class="evidence-source">${escapeHtml(item.source)}</span>
          <span class="evidence-score">相似度 ${escapeHtml(item.score)}</span>
        </summary>
        <p class="evidence-text">${escapeHtml(item.text)}</p>
      </details>`
    )
    .join("");
}

function renderWorkflowSection(stepNum, stepKey, title, subtitle, bodyHtml) {
  return `
    <section class="wf-step wf-step-${stepKey}">
      <div class="wf-step-head">
        <span class="wf-step-badge">${escapeHtml(stepNum)}</span>
        <div>
          <h3 class="wf-step-title">${escapeHtml(title)}</h3>
          <p class="wf-step-sub">${escapeHtml(subtitle)}</p>
        </div>
      </div>
      <div class="wf-step-body">${bodyHtml}</div>
    </section>`;
}

export function renderWorkflowResult(data) {
  const sub = data.execution_payload?.submission || {};
  const policy = data.policy_output || {};
  const params = data.policy_params || {};
  const pred = data.prediction_output || {};
  const strat = data.strategy_output || {};
  const risk = data.risk_check_result || {};
  const decl = data.execution_payload?.declaration_curve_mwh || strat.declaration_curve_mwh || [];

  const overview = `
    <dl class="result-summary wf-overview">
      <dt>trace_id</dt><dd>${escapeHtml(data.trace_id)}</dd>
      <dt>交易日</dt><dd>${escapeHtml(data.trade_date)}</dd>
      <dt>市场</dt><dd>${escapeHtml(pred.market_type || data.execution_payload?.market_type || "-")}</dd>
      <dt>整体状态</dt><dd>${escapeHtml(data.status)}</dd>
    </dl>`;

  const policyBody = `
    ${renderKvRows([
      ["检索问句", policy.query],
      ["生成方式", data.policy_generation_mode || policy.generation_mode],
      ["说明", policy.generation_note],
    ])}
    <div class="wf-block">
      <h4>生成摘要（G）</h4>
      <p class="wf-answer">${escapeHtml(policy.answer || "—")}</p>
    </div>
    <div class="wf-block">
      <h4>结构化规则参数</h4>
      ${renderKvRows([
        ["区域", params.region],
        ["市场环节", params.market_stage],
        [
          "曲线粒度",
          params.time_resolution
            ? `${params.time_resolution.points_per_day} 点 / ${params.time_resolution.interval_minutes} 分钟`
            : null,
        ],
      ])}
      ${
        params.declaration_rules?.length
          ? `<div class="wf-subblock"><strong>申报规则</strong>${renderList(params.declaration_rules.slice(0, 3))}</div>`
          : ""
      }
      ${
        params.settlement_rules?.length
          ? `<div class="wf-subblock"><strong>结算/偏差</strong>${renderList(params.settlement_rules.slice(0, 3))}</div>`
          : ""
      }
    </div>
    <div class="wf-block">
      <h4>检索证据（R）Top ${policy.evidence?.length || 0}</h4>
      ${renderEvidence(policy.evidence)}
    </div>`;

  const predictionBody = `
    ${renderKvRows([
      ["交易日", pred.trading_date],
      ["市场类型", pred.market_type],
    ])}
    <div class="wf-block">
      <h4>24 点曲线预览（Mock）</h4>
      ${renderKvRows([
        ["日前电价", formatCurvePreview(pred.predicted_da_price)],
        ["实时电价", formatCurvePreview(pred.predicted_rt_price)],
        ["预测负荷 MWh", formatCurvePreview(pred.predicted_load_mwh)],
      ])}
    </div>`;

  const strategyBody = `
    ${renderKvRows([
      ["预估收益", strat.estimated_profit != null ? `${strat.estimated_profit}` : null],
    ])}
    <div class="wf-block">
      <h4>申报曲线（Mock 策略输出）</h4>
      ${renderKvRows([
        ["申报 MWh", formatCurvePreview(strat.declaration_curve_mwh)],
        ["申报比例", formatCurvePreview(strat.declaration_ratio)],
      ])}
    </div>`;

  const riskStatus = risk.risk_status || "—";
  const riskClass =
    riskStatus === "PASS"
      ? "ok"
      : riskStatus === "REQUIRES_HUMAN_REVIEW"
        ? "human_review"
        : "rejected";

  const riskBody = `
    <div class="wf-risk-banner wf-risk-${riskClass}">
      <strong>风控结论：${escapeHtml(riskStatus)}</strong>
    </div>
    ${renderKvRows([["违规/提示条数", risk.risk_flags?.length ?? 0]])}
    <div class="wf-block">
      <h4>风控明细</h4>
      ${renderList(risk.risk_flags, "无违规项")}
    </div>`;

  const executionBody = `
    ${renderKvRows([
      ["报文类型", data.execution_payload?.message_type],
      ["提交状态", sub.status],
      ["提交时间", sub.submitted_at],
      ["需人工审核", data.human_review_required ? "是" : "否"],
    ])}
    <div class="wf-block">
      <h4>最终申报曲线</h4>
      <p class="curve-line">${escapeHtml(formatCurvePreview(decl))}</p>
    </div>`;

  const steps = [
    renderWorkflowSection(
      "①",
      "policy",
      "政策检索（RAG）",
      "Embedding 检索 + 规则/大模型生成",
      policyBody
    ),
    renderWorkflowSection(
      "②",
      "prediction",
      "预测（Mock）",
      "日前/实时电价与负荷曲线",
      predictionBody
    ),
    renderWorkflowSection(
      "③",
      "strategy",
      "策略（Mock）",
      "根据预测生成申报曲线",
      strategyBody
    ),
    renderWorkflowSection("④", "risk", "风控", "合规检查 gate", riskBody),
    renderWorkflowSection(
      "⑤",
      "execution",
      "申报报文（Mock）",
      "虚拟交易中心提交载荷",
      executionBody
    ),
  ].join("");

  const audit = data.audit_log?.length
    ? `<details class="wf-raw"><summary>审计日志（${data.audit_log.length} 步）</summary><pre>${escapeHtml(JSON.stringify(data.audit_log, null, 2))}</pre></details>`
    : "";

  const raw = `<details class="wf-raw"><summary>完整 JSON</summary><pre>${escapeHtml(JSON.stringify(data, null, 2))}</pre></details>`;

  return `
    <div class="result-header">
      <span>流水线结果</span>
      <span class="badge ${escapeHtml(data.status)}">${escapeHtml(data.status)}</span>
    </div>
    ${overview}
    <div class="wf-pipeline">${steps}</div>
    ${audit}
    ${raw}`;
}

export function showWorkflowResult(container, data) {
  container.classList.remove("hidden");
  container.innerHTML = renderWorkflowResult(data);
}
