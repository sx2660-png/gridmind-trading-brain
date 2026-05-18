# Trading Brain

具备合规审查能力的自动化电力交易大脑 — 基于 Python 的多智能体交易系统原型。

## 项目简介

本项目面向广东电力现货/中长期交易场景，目标是将政策规则、市场预测、策略申报与风控合规串联为可审计、可回滚的自动化工作流。Day 1 仅搭建工程底座，不包含真实交易对接与复杂智能体编排。

**重点方向：**

- **政策解析**：将广东 2026 电力交易规则、公告、通知等非结构化文本转为结构化 JSON 参数
- **风控合规**：对交易指令进行偏差考核、申报约束等规则检查
- **架构弹性**：支持人机协作、失败回滚、检查点与 `trace_id` 全链路审计

## Day 1 当前范围

- [x] 项目目录结构与模块占位（`agents` / `api` / `services` / `models` / `utils`）
- [x] FastAPI 最小可运行服务（`/`、`/health`、`/demo/state`）
- [x] Pydantic 领域模型骨架（`TradingState`、`PredictionOutput`、`StrategyOutput`、`RiskCheckOutput`）
- [x] 基础配置读取（`.env` + `app/core/config.py`）
- [x] `data/`、`docs/`、`notebooks/`、`tests/` 目录预留

**不在 Day 1 范围：** LangGraph 编排、真实 Policy/Risk Agent、UI、Mock 交易 API、业务逻辑实现。

## 目录结构

```
trading-brain/
├── app/
│   ├── agents/          # 多智能体（后续 LangGraph）
│   ├── api/             # HTTP 路由
│   ├── core/            # 配置与公共能力
│   ├── models/          # Pydantic 领域模型
│   ├── services/        # 业务服务层
│   └── utils/           # 工具函数
├── data/
│   ├── raw/             # 原始政策/行情数据
│   ├── processed/       # 清洗后数据
│   └── mock/            # 模拟数据
├── docs/                # 设计文档
├── notebooks/           # 探索性分析
├── tests/               # 单元/集成测试
├── main.py              # FastAPI 入口
├── requirements.txt
├── .env.example
└── README.md
```

## 环境要求

- Python 3.11+

## 本地启动

```bash
cd trading-brain

# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 复制环境变量模板
cp .env.example .env

# 启动服务
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

启动后访问：

| 端点 | 说明 |
|------|------|
| http://127.0.0.1:8000/ | 服务状态 |
| http://127.0.0.1:8000/health | 健康检查 |
| http://127.0.0.1:8000/demo/state | 示例 `TradingState` |
| http://127.0.0.1:8000/docs | Swagger UI |

## 后续规划

1. **Policy Agent** — 解析广东 2026 规则文本，输出 `policy_params` 结构化 JSON
2. **Risk Agent** — 基于规则引擎对 `strategy_output` 做合规校验
3. **LangGraph** — 编排预测 → 策略 → 风控 → 人机审核 → 执行的状态机工作流
4. **Mock API** — 模拟交易中心申报/撤单接口，支撑端到端联调
5. **检查点与审计** — `trace_id` 贯穿、`audit_log` 持久化、失败回滚

## License

TBD
