# GridMind Trading Brain

具备合规审查能力的自动化电力交易大脑 — 基于 LangGraph 的多智能体交易系统原型。

**仓库：** [github.com/sx2660-png/gridmind-trading-brain](https://github.com/sx2660-png/gridmind-trading-brain)

## 项目简介

面向广东电力现货/中长期交易场景，将政策规则、市场预测、策略申报与风控合规串联为可审计、可回滚的自动化工作流。

| 方向 | 说明 |
|------|------|
| 政策解析 | 本地 RAG + 联网搜索 + LLM，非结构化规则文档 → 结构化 `policy_params` |
| 风控合规 | 申报曲线长度、偏差 ±5%、检修上限等规则检查，失败自动退回重算 |
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
- [x] **Risk Agent** — 偏差考核、曲线校验、检修限额、状态路由（PASS / REJECT / RETURN / HUMAN_REVIEW）

### 第三阶段：工作流闭环 ✅

- [x] **LangGraph 完整编排** — web_search → policy → prediction → strategy → risk → 条件路由
- [x] **风控失败 → 退回策略重算** 闭环（自动循环）
- [x] **SQLite 断点续传** — `langgraph-checkpoint-sqlite`，进程崩溃后可恢复
- [x] **Human-in-the-Loop** — `interrupt_before` 暂停 + API 恢复，操作员可批准/拒绝
- [x] **工作流状态查询** — `/workflow/status/{trace_id}` 实时查看

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
│   └── services/           # document_loader、embedding_store、web_search、workflow_factory
├── articles/               # 政策原文（PDF/DOCX 等）
├── data/
│   ├── processed/          # policy_index.json
│   └── checkpoints.sqlite  # LangGraph 检查点数据库
├── mock_api/               # 模拟预测/策略/申报 API
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

# 查询工作流状态
curl http://127.0.0.1:8000/workflow/status/{trace_id}

# 人工审核恢复（当工作流暂停在 human_review 时）
curl -X POST http://127.0.0.1:8000/workflow/resume \
  -H "Content-Type: application/json" \
  -d '{"trace_id":"xxx","decision":"approved","comment":"确认通过"}'
```

## 测试

```bash
pytest tests/ -v
```

覆盖：API 健康检查、Policy Agent 检索、LangGraph 工作流端到端、工作流状态查询。

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
- 状态路由：`PASS` / `REJECT` / `RETURN_FOR_RECALCULATION` / `REQUIRES_HUMAN_REVIEW`

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
