"""Retrieval-based policy agent."""

from __future__ import annotations

from pathlib import Path
import re

from typing import Optional

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
    return f"针对“{query}”，" + "".join(sections) + f" 主要依据：{top_sources}。"
