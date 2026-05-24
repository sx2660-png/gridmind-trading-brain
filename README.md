# GridMind Trading Brain

具备合规审查能力的自动化电力交易大脑 — 基于 Python 的多智能体交易系统原型。

**仓库：** [github.com/sx2660-png/gridmind-trading-brain](https://github.com/sx2660-png/gridmind-trading-brain)

## 项目简介

面向广东电力现货/中长期交易场景，将政策规则、市场预测、策略申报与风控合规串联为可审计、可回滚的自动化工作流。

| 方向 | 说明 |
|------|------|
| 政策解析 | 非结构化规则文档 → 结构化 `policy_params` |
| 风控合规 | 申报曲线长度、偏差、检修上限等规则检查 |
| 架构弹性 | `trace_id` 审计、人机审核、失败分支、LangGraph 编排（演示级） |

## 当前实现进度

### 已完成

- [x] **Day 1 工程底座** — FastAPI、`app/models` 骨架、配置、目录结构
- [x] **Policy Agent（原型）** — 本地 embedding 检索（R）+ **规则或大模型生成**（G，OpenAI 兼容 API）
- [x] **Policy API** — `/policy/status`、`/policy/index`、`/policy/query`、`/demo/policy-agent`
- [x] **Risk Agent（最小版）** — `risk_agent.py`：曲线长度、缺失字段、5% 偏差、检修上限 → `PASS` / `REJECT` / `RETURN_FOR_RECALCULATION` / `REQUIRES_HUMAN_REVIEW`
- [x] **Mock 交易 API** — `mock_api/`：预测 / 策略 / 申报（独立 FastAPI，供工作流调用）
- [x] **LangGraph 工作流演示** — `workflow_demo/main.py`：Prediction → Strategy → Risk →（条件分支）→ Execution / Reject / Human Review
- [x] **交易日一键流水线 API** — `POST /workflow/run`：输入 `trade_date` → 政策 → mock 预测 → mock 策略 → 风控 → mock 报文
- [x] **简易 Web 前端** — `static/` + `/ui`：流水线运行、政策查询、快捷调试
- [x] **单元测试** — `tests/test_health.py`、`tests/test_policy_agent.py`、`tests/test_workflow.py`

### 尚未完成 / 演示级限制

- [ ] Policy Agent 与 LangGraph 主流程**未统一**（工作流用根目录 `trading_state.py`，API 用 `app/models/state.py`）
- [ ] 未接真实交易中心、真实 LLM/向量模型（当前为本地哈希 embedding）
- [ ] 无持久化检查点、无生产级 UI

## 目录结构

```
trading-brain/
├── app/                    # 主应用（FastAPI + Policy Agent）
│   ├── agents/             # policy_agent.py
│   ├── api/                # routes.py
│   ├── core/               # config.py
│   ├── models/             # TradingState（API 用）、policy / prediction / strategy / risk
│   └── services/           # document_loader、embedding_store
├── articles/               # 政策原文（PDF/DOCX 等）
├── data/
│   ├── processed/          # policy_index.json 等
│   └── mock/
├── mock_api/               # 模拟预测/策略/申报 API（独立服务）
├── workflow_demo/          # LangGraph 端到端演示
├── risk_agent.py           # 风控节点（LangGraph 用）
├── trading_state.py        # LangGraph 共享状态（24 点曲线）
├── static/                 # 简易 Web 前端（访问 /ui）
├── tests/
├── main.py                 # 主 FastAPI 入口
└── requirements.txt
```

> **说明：** 存在两套状态模型 — `app/models/state.py`（96 点、API 演示）与 `trading_state.py`（24 点、LangGraph 工作流）。后续需合并或映射。

## 环境要求

- Python 3.11+（本机可用 `python3` 3.11+）

## 本地启动

```bash
cd trading-brain

python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env

uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 主服务 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/ui` | **简易 Web 控制台** |
| GET | `/` | 服务状态（JSON） |
| GET | `/health` | 健康检查 |
| GET | `/demo/state` | 示例 `TradingState`（API 模型） |
| GET | `/policy/status` | Policy 索引状态 |
| POST | `/policy/index` | 重建政策 embedding 索引 |
| POST | `/policy/query` | 政策检索与参数抽取 |
| GET | `/demo/policy-agent` | Policy 示例查询 |
| POST | `/workflow/run` | **交易日端到端**：规则 → 预测 → 策略 → 风控 → mock 报文 |
| — | `/docs` | Swagger UI |

环境变量（见 `.env.example`）：

```bash
POLICY_ARTICLES_DIR=articles
POLICY_INDEX_PATH=data/processed/policy_index.json
```

## 如何测试

### 1. 自动化测试（推荐先做）

```bash
cd trading-brain
source .venv/bin/activate
pip install pytest   # 若未安装
pytest tests/ -v
```

覆盖：API 健康检查、Policy Agent 对本地 txt 的检索与 `policy_params` 抽取。

### 2. 主 FastAPI 手工测试

启动服务后：

```bash
# 健康检查
curl http://127.0.0.1:8000/health

# 重建政策索引（需 articles/ 下有文档）
curl -X POST http://127.0.0.1:8000/policy/index

# 政策查询
curl -X POST http://127.0.0.1:8000/policy/query \
  -H "Content-Type: application/json" \
  -d '{"query":"广东电力市场日前交易申报规则和96点曲线要求","top_k":5}'

# 示例接口
curl http://127.0.0.1:8000/demo/policy-agent

# 给定交易日，跑完整 mock 流水线
curl -X POST http://127.0.0.1:8000/workflow/run \
  -H "Content-Type: application/json" \
  -d '{"trade_date":"2026-05-22","market_type":"day_ahead"}'
```

也可在浏览器打开 `http://127.0.0.1:8000/docs` 用 Swagger 试调 `POST /workflow/run`。

### 3. LangGraph 工作流演示

不启动主 API，直接跑编排演示（使用 `mock_api` 模块内存调用）：

```bash
cd trading-brain
source .venv/bin/activate
python workflow_demo/main.py
```

终端会打印各节点日志及最终 `risk_status`、`execution_status`。

### 4. Risk Agent 单测

```bash
python risk_agent.py
```

会打印内置 `example_input` 的风控结果（含偏差超 5% 等场景）。

### 5. Mock 交易 API（可选）

独立端口演示预测/策略/申报（与主服务默认同为 8000，需改端口避免冲突）：

```bash
cd mock_api
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

详见 [mock_api/README.md](mock_api/README.md)。

## Policy Agent 说明

- 文档目录：`articles/`（已含广东电力市场相关 PDF/DOCX）
- 索引输出：`data/processed/policy_index.json`
- Embedding：`local-hashed-char-word-embedding-v1`（本地、无外部 API）
- 首次 `query` 会自动建索引；也可 `POST /policy/index` 手动重建

## 后续规划

1. 统一 `TradingState`（API 与工作流一套模型或明确映射）
2. Policy Agent 接入更强 embedding / LLM 抽取
3. 将 `workflow_demo` 迁入 `app/agents` 并由主 API 触发
4. 检查点持久化、`audit_log` 落库
5. 对接真实交易中心 Mock → 生产 API

## License

TBD
