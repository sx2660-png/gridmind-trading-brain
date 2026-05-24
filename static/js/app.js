import { showWorkflowResult } from "./workflow-view.js";

const $ = (sel, root = document) => root.querySelector(sel);

const LLM_STORAGE_KEY = "trading-brain-llm-config";

function loadLlmConfig() {
  try {
    const raw = localStorage.getItem(LLM_STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function saveLlmConfig(config) {
  localStorage.setItem(LLM_STORAGE_KEY, JSON.stringify(config));
}

function clearLlmConfig() {
  localStorage.removeItem(LLM_STORAGE_KEY);
}

function readLlmForm() {
  const enabled = $("#llm-enabled").checked;
  const api_key = $("#llm-api-key").value.trim();
  const base_url = $("#llm-base-url").value.trim() || "https://api.openai.com/v1";
  const model = $("#llm-model").value.trim() || "gpt-4o-mini";
  return { enabled, api_key, base_url, model };
}

function applyLlmForm(config) {
  if (!config) return;
  $("#llm-enabled").checked = config.enabled !== false;
  $("#llm-api-key").value = config.api_key || "";
  $("#llm-base-url").value = config.base_url || "https://api.openai.com/v1";
  $("#llm-model").value = config.model || "gpt-4o-mini";
}

function buildLlmPayload() {
  const form = readLlmForm();
  if (!form.enabled || !form.api_key) return null;
  return {
    api_key: form.api_key,
    base_url: form.base_url,
    model: form.model,
    enabled: true,
  };
}

function initLlmSettings() {
  applyLlmForm(loadLlmConfig());
  $("#llm-settings-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const config = readLlmForm();
    saveLlmConfig(config);
    $("#llm-save-hint").textContent = config.api_key
      ? "已保存到浏览器（仅本机）。"
      : "已保存；未填写 API Key 时将使用规则抽取。";
  });
  $("#llm-clear-btn").addEventListener("click", () => {
    clearLlmConfig();
    $("#llm-api-key").value = "";
    $("#llm-save-hint").textContent = "已清除本地配置。";
  });
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  const text = await res.text();
  let data;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { raw: text };
  }
  if (!res.ok) {
    const msg = data?.detail ? JSON.stringify(data.detail) : res.statusText;
    throw new Error(`${res.status} ${msg}`);
  }
  return data;
}

function showResult(container, { title, badge, summary, data }) {
  container.classList.remove("hidden");
  const badgeHtml = badge
    ? `<span class="badge ${badge.cls}">${badge.text}</span>`
    : "";
  const summaryHtml = summary
    ? `<dl class="result-summary">${summary
        .map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`)
        .join("")}</dl>`
    : "";
  container.innerHTML = `
    <div class="result-header">
      <span>${title}</span>
      ${badgeHtml}
    </div>
    ${summaryHtml}
    <pre>${JSON.stringify(data, null, 2)}</pre>
  `;
}

function showError(container, err) {
  showResult(container, {
    title: "请求失败",
    badge: { cls: "rejected", text: "ERROR" },
    data: { message: String(err.message || err) },
  });
}

function setLoading(btn, loading) {
  if (!btn) return;
  btn.disabled = loading;
  btn.dataset.originalText ??= btn.textContent;
  btn.textContent = loading ? "处理中…" : btn.dataset.originalText;
}

async function refreshHealth() {
  const pill = $("#health-pill");
  try {
    const data = await api("/health");
    pill.textContent = `${data.service} · ${data.status}`;
    pill.classList.add("ok");
    pill.classList.remove("err");
  } catch {
    pill.textContent = "服务不可用";
    pill.classList.add("err");
    pill.classList.remove("ok");
  }
}

$("#workflow-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = $("#workflow-btn");
  const box = $("#workflow-result");
  const fd = new FormData(e.target);
  const body = {
    trade_date: fd.get("trade_date"),
    market_type: fd.get("market_type"),
  };
  const policyQuery = fd.get("policy_query")?.toString().trim();
  if (policyQuery) body.policy_query = policyQuery;
  const llm = buildLlmPayload();
  if (llm) body.llm = llm;

  setLoading(btn, true);
  try {
    const data = await api("/workflow/run", {
      method: "POST",
      body: JSON.stringify(body),
    });
    showWorkflowResult(box, data);
  } catch (err) {
    showError(box, err);
  } finally {
    setLoading(btn, false);
  }
});

$("#policy-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const box = $("#policy-result");
  const fd = new FormData(e.target);
  const btn = e.submitter;
  const payload = {
    query: fd.get("query"),
    top_k: Number(fd.get("top_k") || 5),
  };
  const llm = buildLlmPayload();
  if (llm) payload.llm = llm;

  setLoading(btn, true);
  try {
    const data = await api("/policy/query", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    showResult(box, {
      title: "政策查询",
      summary: [
        ["生成方式", data.generation_mode ?? "-"],
        ["证据条数", data.evidence?.length ?? 0],
        ["区域", data.policy_params?.region ?? "-"],
      ],
      data,
    });
  } catch (err) {
    showError(box, err);
  } finally {
    setLoading(btn, false);
  }
});

$("#rebuild-index-btn").addEventListener("click", async () => {
  const btn = $("#rebuild-index-btn");
  const box = $("#policy-result");
  setLoading(btn, true);
  try {
    const data = await api("/policy/index", { method: "POST" });
    showResult(box, {
      title: "索引已重建",
      summary: [
        ["文档数", data.document_count],
        ["分块数", data.chunk_count],
        ["就绪", data.ready ? "是" : "否"],
      ],
      data,
    });
  } catch (err) {
    showError(box, err);
  } finally {
    setLoading(btn, false);
  }
});

document.querySelectorAll("[data-action]").forEach((el) => {
  el.addEventListener("click", async () => {
    const box = $("#quick-result");
    const action = el.dataset.action;
    setLoading(el, true);
    try {
      let data;
      let title = action;
      if (action === "health") {
        data = await api("/health");
        title = "健康检查";
      } else if (action === "policy-status") {
        data = await api("/policy/status");
        title = "政策索引";
      } else if (action === "demo-state") {
        data = await api("/demo/state");
        title = "示例状态";
      } else if (action === "demo-policy") {
        data = await api("/demo/policy-agent");
        title = "示例政策";
      }
      showResult(box, { title, data });
    } catch (err) {
      showError(box, err);
    } finally {
      setLoading(el, false);
    }
  });
});

initLlmSettings();
refreshHealth();
