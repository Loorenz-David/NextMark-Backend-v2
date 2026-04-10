# Development Quickstart

## 1) Create and activate virtual environment
```bash
python -m venv .venv
source .venv/bin/activate
```

## 2) Install dependencies
```bash
pip install -r requirements.txt
```

## 3) Apply migrations
```bash
.venv/bin/flask --app 'Delivery_app_BK:create_app("development")' db upgrade -d migrations
```

## 4) Run API
```bash
python run.py
```

## 5) Optional async processes (separate terminals)
```bash
APP_ENV=development .venv/bin/python redis_dispatcher.py
APP_ENV=development .venv/bin/python redis_worker_default.py
APP_ENV=development .venv/bin/python redis_worker_io.py
APP_ENV=development .venv/bin/python redis_scheduler.py
```

## 6) Run tests
```bash
python -m pytest tests/unit/
```
