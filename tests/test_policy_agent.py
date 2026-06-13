"""Tests for the local policy agent."""

from pathlib import Path

from app.agents.policy_agent import PolicyAgent


def test_policy_agent_retrieves_local_policy_text(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "")

    from app.core import config

    config.get_settings.cache_clear()

    source_dir = tmp_path / "articles"
    source_dir.mkdir()
    (source_dir / "rule.txt").write_text(
        "广东电力市场日前交易采用96点申报曲线，每15分钟一个交易时段。"
        "市场主体应按要求申报电量和价格，偏差费用按照结算规则处理。",
        encoding="utf-8",
    )

    agent = PolicyAgent(
        source_dir=source_dir,
        index_path=tmp_path / "policy_index.json",
    )

    response = agent.query("日前交易申报曲线要求", top_k=2)

    assert response.evidence
    assert response.policy_params["region"] == "广东"
    assert response.policy_params["time_resolution"]["points_per_day"] == 96
    assert "declaration_rules" in response.policy_params
    assert response.generation_mode == "rules"

    config.get_settings.cache_clear()
