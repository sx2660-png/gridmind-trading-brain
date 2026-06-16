"""Retrieval-based policy agent."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any, Optional

from app.models.llm import LLMConfig
from app.models.policy import PolicyEvidence, PolicyQueryResponse
from app.services.embedding_store import LocalEmbeddingStore
from app.services.llm_client import generate_policy_with_llm
from app.services.llm_resolver import resolve_llm_config


class PolicyAgent:
    """Policy retrieval agent backed by local document embeddings."""

    def __init__(self, source_dir: Path, index_path: Path) -> None:
        self.store = LocalEmbeddingStore(source_dir=source_dir, index_path=index_path)

    def rebuild_index(self) -> dict:
        self.store.build()
        return self.store.status()

    def status(self) -> dict:
        return self.store.status()

    def query(
        self,
        query: str,
        top_k: int = 5,
        llm: Optional[LLMConfig] = None,
    ) -> PolicyQueryResponse:
        results = self.store.search(query=query, top_k=top_k)
        evidence = [
            PolicyEvidence(
                source=chunk.source,
                chunk_id=chunk.chunk_id,
                score=round(score, 4),
                text=chunk.text,
            )
            for chunk, score in results
        ]
        evidence_texts = [item.text for item in evidence]
        sources = [item.source for item in evidence]

        resolved_llm = resolve_llm_config(llm)
        if resolved_llm and evidence_texts:
            try:
                answer, policy_params = generate_policy_with_llm(
                    config=resolved_llm,
                    query=query,
                    evidence_texts=evidence_texts,
                    sources=sources,
                )
                return PolicyQueryResponse(
                    query=query,
                    answer=answer,
                    policy_params=policy_params,
                    evidence=evidence,
                    generation_mode="llm",
                    generation_note=f"model={resolved_llm.model}",
                )
            except Exception as exc:
                policy_params = _extract_policy_params(query, evidence_texts)
                answer = _compose_answer(query, policy_params, evidence)
                return PolicyQueryResponse(
                    query=query,
                    answer=answer,
                    policy_params=policy_params,
                    evidence=evidence,
                    generation_mode="rules_fallback",
                    generation_note=str(exc),
                )

        policy_params = _extract_policy_params(query, evidence_texts)
        answer = _compose_answer(query, policy_params, evidence)
        return PolicyQueryResponse(
            query=query,
            answer=answer,
            policy_params=policy_params,
            evidence=evidence,
            generation_mode="rules",
            generation_note="未配置 LLM API Key，使用规则抽取",
        )


def _extract_policy_params(query: str, texts: list[str]) -> dict:
    joined = "\n".join(texts)
    params: dict = {
        "query": query,
        "region": "广东",
        "evidence_count": len(texts),
    }

    if re.search(r"96|九十六|15分钟|十五分钟", joined):
        params["time_resolution"] = {
            "interval_minutes": 15,
            "points_per_day": 96,
        }

    if "日前" in joined:
        params["market_stage"] = "日前"
    elif "实时" in joined:
        params["market_stage"] = "实时"
    elif "中长期" in joined:
        params["market_stage"] = "中长期"

    declaration_rules = _sentences_matching(joined, ("申报", "报量", "报单", "报价"))
    if declaration_rules:
        params["declaration_rules"] = declaration_rules[:5]

    settlement_rules = _sentences_matching(joined, ("结算", "偏差", "考核", "费用"))
    if settlement_rules:
        params["settlement_rules"] = settlement_rules[:5]

    disclosure_rules = _sentences_matching(joined, ("披露", "公开", "发布", "信息"))
    if disclosure_rules:
        params["information_disclosure_rules"] = disclosure_rules[:5]

    price_rules = _sentences_matching(joined, ("限价", "价格", "出清", "节点电价", "统一结算点"))
    if price_rules:
        params["price_rules"] = price_rules[:5]

    return params


def _sentences_matching(text: str, keywords: tuple[str, ...]) -> list[str]:
    parts = re.split(r"(?<=[。；;.!?？])|\n+", text)
    matches: list[str] = []
    seen: set[str] = set()
    for part in parts:
        sentence = re.sub(r"\s+", " ", part).strip()
        if len(sentence) < 8 or not any(keyword in sentence for keyword in keywords):
            continue
        if sentence in seen:
            continue
        seen.add(sentence)
        matches.append(sentence[:260])
    return matches


def _compose_answer(query: str, params: dict, evidence: list[PolicyEvidence]) -> str:
    if not evidence:
        return "未找到可用政策依据。请确认 articles 目录存在可读取的 PDF、DOCX、TXT 或 MD 文件。"

    sections = []
    if "time_resolution" in params:
        resolution = params["time_resolution"]
        sections.append(f"交易曲线粒度识别为 {resolution['interval_minutes']} 分钟、每日 {resolution['points_per_day']} 点。")
    if "market_stage" in params:
        sections.append(f"相关市场环节识别为：{params['market_stage']}。")
    for key, label in (
        ("declaration_rules", "申报相关规则"),
        ("settlement_rules", "结算/偏差相关规则"),
        ("information_disclosure_rules", "信息披露相关规则"),
        ("price_rules", "价格/出清相关规则"),
    ):
        if key in params:
            sections.append(f"{label}已从证据片段中抽取 {len(params[key])} 条候选规则。")

    if not sections:
        sections.append("已返回最相关的政策片段，但未抽取到稳定的结构化规则字段。")

    top_sources = "、".join(item.source for item in evidence[:3])
    return "针对\"" + query + "\"，" + "".join(sections) + " 主要依据：" + top_sources + "。"


_DEFAULT_POLICY_QUERY = (
    "广东电力市场日前交易申报规则"
    "、96点曲线与偏差考核要求"
)
_DEFAULT_MAINTENANCE_LIMIT_MWH = 900.0


def policy_node(state) -> dict[str, Any]:
    from app.models.trading_state import TradingState
    from app.core.config import get_settings

    if isinstance(state, dict):
        state = TradingState.model_validate(state)

    print("[Policy Agent] current_node=Policy Agent trace_id=" + state.trace_id)

    cfg = get_settings()
    agent = PolicyAgent(
        source_dir=Path(cfg.policy_articles_dir),
        index_path=Path(cfg.policy_index_path),
    )

    llm_config = resolve_llm_config(None)

    response = agent.query(
        query=_DEFAULT_POLICY_QUERY,
        top_k=5,
        llm=llm_config,
    )

    web_evidence_texts = []
    web_sources = []
    for item in state.web_search_results:
        content = item.get("content", "")
        if content:
            web_evidence_texts.append(content)
            web_sources.append(item.get("url", "web"))

    if web_evidence_texts and llm_config:
        all_evidence_texts = [e.text for e in response.evidence] + web_evidence_texts
        all_sources = [e.source for e in response.evidence] + web_sources
        try:
            answer, policy_params = generate_policy_with_llm(
                config=llm_config,
                query=_DEFAULT_POLICY_QUERY,
                evidence_texts=all_evidence_texts,
                sources=all_sources,
            )
            response = PolicyQueryResponse(
                query=_DEFAULT_POLICY_QUERY,
                answer=answer,
                policy_params=policy_params,
                evidence=response.evidence,
                generation_mode="llm_with_web",
                generation_note="model=" + llm_config.model + ", web_results=" + str(len(web_evidence_texts)),
            )
        except Exception:
            pass

    policy_params = response.policy_params
    policy_rules = {
        "region": policy_params.get("region", "guangdong"),
        "market_stage": policy_params.get("market_stage", "day_ahead"),
        "maintenance_limit_mwh": policy_params.get(
            "maintenance_limit_mwh", _DEFAULT_MAINTENANCE_LIMIT_MWH
        ),
    }
    if "time_resolution" in policy_params:
        policy_rules["time_resolution"] = policy_params["time_resolution"]

    print(
        "[Policy Agent] trace_id=" + state.trace_id
        + " mode=" + response.generation_mode
        + " rules=" + str(list(policy_rules.keys()))
    )

    return {
        "policy_rules": policy_rules,
        "updated_at": datetime.now(timezone.utc),
    }
