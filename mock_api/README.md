# Mock Electricity Trading API

FastAPI mock services for end-to-end workflow testing before connecting to real enterprise systems.

## Run

```bash
cd mock_api
pip install -r requirements.txt
uvicorn main:app --reload
```

Swagger UI:

```text
http://127.0.0.1:8000/docs
```

## Example Requests

Prediction:

```bash
curl -X POST http://127.0.0.1:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"trading_date":"2026-05-22","market_type":"day_ahead"}'
```

Strategy:

```bash
curl -X POST http://127.0.0.1:8000/strategy \
  -H "Content-Type: application/json" \
  -d '{
    "predicted_da_price":[390,392,395,398,405,415,430,450,460,455,440,420,390,370,365,380,410,455,480,500,490,460,430,405],
    "predicted_rt_price":[395,390,400,405,410,420,435,455,470,460,430,415,380,360,370,390,430,470,510,520,500,470,440,410],
    "predicted_load_mwh":[410,405,400,398,405,430,470,520,560,590,610,600,570,540,530,550,590,640,690,720,700,640,560,480],
    "mid_long_term_contract_mwh":[380,380,380,380,390,400,430,460,500,520,540,530,510,500,500,510,540,580,620,650,630,580,520,450]
  }'
```

Execution:

```bash
curl -X POST http://127.0.0.1:8000/execute \
  -H "Content-Type: application/json" \
  -d '{
    "declaration": {
      "trace_id": "trace-20260522-001",
      "trading_date": "2026-05-22",
      "market_type": "day_ahead",
      "declaration_curve_mwh": [410, 405, 400],
      "declaration_ratio": [0.99, 0.99, 0.99]
    }
  }'
```
