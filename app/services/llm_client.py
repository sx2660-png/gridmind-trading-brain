"""OpenAI-compatible chat client for policy RAG generation."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.models.llm import LLMConfig

GENERATION_SYSTEM_PROMPT = """你是广东电力市场交易规则分析助手。
根据用户问题和检索到的政策证据片段，生成结构化输出。
必须只输出一个 JSON 对象，不要 Markdown 代码块，不要额外说明。
JSON 格式：
{
  "answer": "面向业务人员的中文总结，2-5句",
  "policy_params": {
    "region": "广东",
    "market_stage": "日前或实时或中长期",
    "time_resolution": {"interval_minutes": 15, "points_per_day": 96},
    "declaration_rules": ["规则要点1"],
    "settlement_rules": ["规则要点1"],
    "maintenance_limit_mwh": null
  }
}
只填写证据中确实出现或合理推断的字段；没有的字段可省略。数字字段用 number 或 null。"""


def generate_policy_with_llm(
    *,
    config: LLMConfig,
    query: str,
    evidence_texts: list[str],
    sources: list[str],
) -> tuple[str, dict[str, Any]]:
    """Call chat completions API and parse answer + policy_params."""
    evidence_block = "\n\n---\n\n".join(
        f"[来源 {index + 1}: {sources[index] if index < len(sources) else 'unknown'}]\n{text}"
        for index, text in enumerate(evidence_texts)
    )
    user_prompt = (
        f"用户问题：{query}\n\n"
        f"检索证据（共 {len(evidence_texts)} 段）：\n{evidence_block or '（无证据）'}"
    )

    payload = {
        "model": config.model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": GENERATION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
    }

    url = f"{config.base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=90.0) as client:
        response = client.post(url, headers=headers, json=payload)
        if response.status_code >= 400 and "response_format" in payload:
            payload = {key: value for key, value in payload.items() if key != "response_format"}
            response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    content = data["choices"][0]["message"]["content"]
    parsed = _parse_json_content(content)
    answer = str(parsed.get("answer") or "").strip()
    policy_params = parsed.get("policy_params") or {}
    if not isinstance(policy_params, dict):
        policy_params = {}
    policy_params.setdefault("query", query)
    policy_params.setdefault("evidence_count", len(evidence_texts))
    if not answer:
        answer = "大模型未返回有效总结，已使用结构化字段。"
    return answer, policy_params


def _parse_json_content(content: str) -> dict[str, Any]:
    text = content.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    return json.loads(text)
