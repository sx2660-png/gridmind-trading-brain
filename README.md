# GridMind Trading Brain

具备合规审查能力的自动化电力交易大脑 — 基于 LangGraph 的多智能体交易系统原型。

**仓库：** [github.com/sx2660-png/gridmind-trading-brain](https://github.com/sx2660-png/gridmind-trading-brain)

## 项目简介

面向广东电力现货/中长期交易场景，将政策规则、市场预测、策略申报与风控合规串联为可审计、可回滚的自动化工作流。

| 方向 | 说明 |
|------|------|
| 政策解析 | 本地 RAG + 联网搜索 + LLM，非结构化规则文档 → 结构化 `policy_params` |
| 市场预警 | 按申报决策时点做联网信息截断，抽取价格/价差/约束/规则异常信号，触发防御性策略与人工复核 |
| 风控合规 | 申报曲线长度、偏差 ±5%、检修上限、市场异常等规则检查，失败自动退回重算或暂停人工审核 |
| 架构弹性 | LangGraph 编排、SQLite 断点续传、人工审核中断/恢复、`trace_id` 全链路审计 |

## 系统架构

```
START → Web Search → Policy → Prediction → Strategy → Risk → 条件路由
                                                              ├─ PASS → Execution → END
                                                              ├─ RETURN_FOR_RECALC → Strategy（循环重算）
                                                              ├─ REJECT → END
                                                              └─ REQUIRES_HUMAN_REVIEW → (interrupt) → Human Review
                                                                                                        ├─ approved → Execution → END
                                                                                                        └─ rejected → END
```

## 当前实现进度

### 第一阶段：建模与环境 ✅

- [x] TradingState 定义（Pydantic v2，24 点曲线）
- [x] 3 个 Mock API（预测 / 策略 / 执行）
- [x] FastAPI 仿真交易中心
- [x] 最小风控拦截逻辑

### 第二阶段：智能体开发 ✅

- [x] **Policy Agent** — 本地 embedding 检索 + 规则提取 / LLM 增强生成
- [x] **联网搜索增强** — Tavily API，覆盖广东电力中心、国家能源局、微信公众号等行业来源
- [x] **Policy LangGraph 节点** — 融合本地文档 + 联网搜索证据，输出结构化政策规则
- [x] **Market Anomaly Agent** — 对广东现货价格/价差/约束/规则变化做信号抽取与预警分级
- [x] **Risk Agent** — 偏差考核、曲线校验、检修限额、状态路由（PASS / REJECT / RETURN / HUMAN_REVIEW）

### 第三阶段：工作流闭环 ✅

- [x] **LangGraph 完整编排** — web_search → policy → prediction → strategy → risk → 条件路由
- [x] **风控失败 → 退回策略重算** 闭环（自动循环）
- [x] **SQLite 断点续传** — `langgraph-checkpoint-sqlite`，进程崩溃后可恢复
- [x] **Human-in-the-Loop** — `interrupt_before` 暂停 + API 恢复，操作员可批准/拒绝
- [x] **工作流状态查询** — `/workflow/status/{trace_id}` 实时查看
- [x] **企业案例回放** — 支持以 D-1 12:00 为信息截点，验证异常搜索信号是否及时触发人工介入

### 第四阶段：集成与移交 🔲

- [ ] Streamlit UI 展示 Agent 思考过程及申报曲线
- [ ] Docker 化部署
- [ ] 底座扩展指南文档

## 目录结构

```
trading-brain/
├── app/
│   ├── agents/             # policy_agent.py、web_search_agent.py
│   ├── api/                # routes.py（含 /workflow/run, /resume, /status）
│   ├── core/               # config.py
│   ├── models/             # workflow、policy、prediction、strategy、risk
│   └── services/           # document_loader、embedding_store、web_search、market_anomaly、workflow_factory
├── articles/               # 政策原文（PDF/DOCX 等）
├── data/
│   ├── processed/          # policy_index.json
│   └── checkpoints.sqlite  # LangGraph 检查点数据库
├── docs/
│   └── reports/            # 本地生成的回放报告（*.md 已忽略）
├── mock_api/               # 模拟预测/策略/申报 API
├── scripts/                # 回放/报告脚本
├── workflow_demo/          # LangGraph 端到端工作流（可独立运行）
├── risk_agent.py           # 风控节点
├── trading_state.py        # LangGraph 共享状态
├── static/                 # 简易 Web 前端（/ui）
├── tests/
├── main.py                 # FastAPI 入口
└── requirements.txt
```

## 快速开始

### 环境要求

- Python 3.11+（推荐 3.12，3.14 下 langgraph 导入较慢）

### 安装

```bash
cd trading-brain
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### 环境变量（`.env`）

```bash
# 必填项无，以下均为可选增强
TAVILY_API_KEY=tvly-xxx          # 联网搜索（不填则跳过，走纯本地 RAG）
LLM_API_KEY=sk-xxx               # 政策分析 LLM 增强（不填则走规则提取 fallback）
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
CHECKPOINT_DB_PATH=data/checkpoints.sqlite
WEB_SEARCH_ENABLED=true
```

### 方式一：命令行直接跑工作流

```bash
python workflow_demo/main.py
```

打印各节点执行日志，最终输出 `risk_status` 和 `execution_status`。

### 方式二：启动 FastAPI 服务

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/ui` | Web 控制台 |
| GET | `/health` | 健康检查 |
| POST | `/workflow/run` | **交易日端到端**：联网搜索 → 政策 → 预测 → 策略 → 风控 → 报文 |
| GET | `/workflow/status/{trace_id}` | 查询工作流状态（含是否暂停） |
| POST | `/workflow/resume` | 人工审核后恢复工作流 |
| POST | `/workflow/run-legacy` | 旧版流水线（不走 LangGraph） |
| GET | `/policy/status` | Policy 索引状态 |
| POST | `/policy/index` | 重建政策 embedding 索引 |
| POST | `/policy/query` | 政策检索与参数抽取 |
| GET | `/demo/policy-agent` | Policy 示例查询 |
| — | `/docs` | Swagger UI |

### 使用示例

```bash
# 跑一个交易日
curl -X POST http://127.0.0.1:8000/workflow/run \
  -H "Content-Type: application/json" \
  -d '{"trade_date":"2026-06-03","market_type":"day_ahead"}'

# 指定申报决策信息截点（用于回放）
curl -X POST http://127.0.0.1:8000/workflow/run \
  -H "Content-Type: application/json" \
  -d '{"trade_date":"2026-05-25","market_type":"day_ahead","as_of_datetime":"2026-05-24T12:00:00+08:00"}'

# 查询工作流状态
curl http://127.0.0.1:8000/workflow/status/{trace_id}

# 人工审核恢复（当工作流暂停在 human_review 时）
curl -X POST http://127.0.0.1:8000/workflow/resume \
  -H "Content-Type: application/json" \
  -d '{"trace_id":"xxx","decision":"approved","comment":"确认通过"}'
```

## 测试

```bash
python -m pytest tests/ -q
```

覆盖：API 健康检查、Policy Agent 检索、LangGraph 工作流端到端、工作流状态查询、企业案例回放。

只跑企业案例回放测试：

```bash
python -m pytest tests/test_enterprise_replay.py -q
```

## 企业案例回放

### 场景说明

用于验证：当广东现货市场在 2026-05-25、2026-05-26、2026-05-27 连续出现价格和价差结构变化时，智能体能否在申报决策截点前通过联网信息触发预警，并指导人工介入调整申报策略。

回放严格使用日前申报决策的信息截点：

| 交易日 | 可用信息截止时间 |
|------|------------------|
| 2026-05-25 | 2026-05-24 12:00 Asia/Shanghai |
| 2026-05-26 | 2026-05-25 12:00 Asia/Shanghai |
| 2026-05-27 | 2026-05-26 12:00 Asia/Shanghai |

### 运行三天回放

```bash
python - <<'PY'
from trading_state import TradingState
from workflow_demo.main import build_workflow, _as_state

for trade_date in ["2026-05-25", "2026-05-26", "2026-05-27"]:
    state = TradingState(
        trace_id=f"enterprise-case-{trade_date}",
        trading_date=trade_date,
        market_type="day_ahead",
        mid_long_term_contract_mwh=[380.0] * 24,
    )
    print("\n===", trade_date, "===")
    final = _as_state(build_workflow().invoke(state))
    print("as_of:", final.as_of_datetime)
    print("alert_level:", final.market_anomaly.get("alert_level"))
    print("signals:", [s.get("code") for s in final.market_anomaly.get("signals", [])])
    print("strategy_adjustments:", final.strategy_adjustments)
    print("risk_status:", final.risk_status)
    print("execution_status:", final.execution_status)
PY
```

预期关键结果：

- 搜索结果在 `as_of_datetime` 后发布的内容会被过滤。
- 若价差、价格规律、约束、规则参数、预测失准等信号达到高风险，`alert_level` 为 `HIGH` 或 `CRITICAL`。
- 策略节点应用 `MARKET_ANOMALY_DEFENSIVE_ALIGN_TO_FORECAST_LOAD`，即将申报比例收敛到 `1.0`，暂停价差驱动的投机性偏移。
- 风控节点输出 `REQUIRES_HUMAN_REVIEW`，执行状态为 `paused_for_human_review`。
- 若 Tavily/API 或 DNS 不可用，系统输出 `UNKNOWN` 和 `WEB_SEARCH_UNAVAILABLE`，同样暂停自动提交，避免在缺失外部信息时静默申报。

### 生成证据报告

生成每一天的 `market_anomaly.evidence` 明细，包括标题、URL、发布时间、搜索分数、命中的 signals 和 excerpt：

```bash
python scripts/run_enterprise_case_report.py
```

报告输出：

```text
docs/reports/enterprise_case_market_anomaly_report.md
```

`docs/reports/*.md` 是本地生成物，默认不提交到 git。若需要归档某次真实回放结果，可将报告另存或在 PR/交付材料中单独附上。

## 核心模块说明

### Policy Agent

- 文档目录：`articles/`（含广东电力市场 PDF/DOCX）
- 索引：`data/processed/policy_index.json`
- Embedding：`local-hashed-char-word-embedding-v1`（本地、无外部依赖）
- 联网搜索：Tavily API，覆盖 `gd.csg.cn`、`occ.csg.cn`、`nea.gov.cn`、`ndrc.gov.cn`、`mp.weixin.qq.com`
- 三种生成模式：`llm_with_web`（LLM + 联网）→ `llm`（纯 LLM）→ `rules`（规则 fallback）

### Risk Agent

纯函数，无副作用，检查规则：
- 曲线长度必须 24 点
- 申报与预测偏差不超过 ±5%
- 申报不超过检修限额
- 市场异常达到 `HIGH` / `CRITICAL` 或联网搜索不可用时，触发人工复核
- 状态路由：`PASS` / `REJECT` / `RETURN_FOR_RECALCULATION` / `REQUIRES_HUMAN_REVIEW`

### Market Anomaly

- 默认信息截点：交易日前一日 12:00（Asia/Shanghai）
- 搜索主题：广东电力现货、日前/实时价格、价差、预测偏差、出清、负荷、检修、规则调整、申报策略
- 主要信号：`PRICE_SPREAD_SHIFT`、`PRICE_REGIME_SHIFT`、`FORECAST_BREAKDOWN`、`GRID_CONSTRAINT`、`RULE_OR_PARAMETER_CHANGE`、`ABNORMAL_MOVE`、`CONSECUTIVE_EVENT`、`SUPPLY_DEMAND_STRESS`、`MARKET_SUSPENSION`
- 预警等级：`NONE` / `LOW` / `MEDIUM` / `HIGH` / `CRITICAL` / `UNKNOWN`
- 执行策略：`HIGH`、`CRITICAL`、`UNKNOWN` 都会收敛申报并暂停人工复核

### LangGraph 工作流

- 条件路由：风控通过 → 执行，偏差超标 → 退回策略重算，需人工 → 中断等待
- 检查点：SQLite 持久化，支持进程重启后恢复
- 人工审核：`interrupt_before=["human_review"]`，通过 API 注入决策后恢复

## 后续规划

1. Streamlit UI — 可视化展示 Agent 思考过程及申报曲线
2. Docker 化部署 + Docker Compose
3. 底座扩展指南文档
4. 对接更强 embedding / 向量数据库
5. 对接真实交易中心 API

## License

TBD
