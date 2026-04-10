# Flask_Delivery_Application

Backend for the delivery application. It is built with Flask and SQLAlchemy, uses PostgreSQL for application data, Redis for async/realtime infrastructure, and Socket.IO for shared websocket delivery across the admin and driver apps.

## Documentation
- [AI Operator Architecture](Delivery_app_BK/ai/AI_OPERATOR.md)
- [Docs Index](docs/README.md)
- [State Transitions](docs/domain/state-transitions.md)
- [State Transition Spec](docs/domain/state-transitions-spec.md)
- [Architecture Overview](docs/architecture/overview.md)
- [Development Quickstart](docs/runbooks/development-quickstart.md)

## Tech Stack
- Python 3.10+
- Flask & Flask SQLAlchemy
- Flask-JWT-Extended for access/refresh tokens
- Marshmallow for payload validation
- Pytest for testing
- Redis + RQ + RQ Scheduler for async jobs, durable event dispatch, and realtime relay
- python-dotenv for local configuration

## Project Layout
```
Back_end/
├── Delivery_app_BK/
│   ├── __init__.py              # Flask application factory, DB/JWT wiring, blueprint registration
│   ├── config/                  # Environment specific configuration classes
│   ├── models/                  # SQLAlchemy tables, mixins, and managers
│   ├── routers/                 # Flask blueprints (auth + item catalogue)
│   ├── services/                # Business logic helpers used by the routers
│   └── sockets/                 # Socket.IO auth, rooms, handlers, emitters, telemetry
├── run.py                       # Local entry point (python run.py)
├── redis_dispatcher.py          # Durable event dispatcher loop
├── redis_worker_default.py      # Default/background worker
├── redis_worker_io.py           # Provider-facing worker (email/SMS)
├── redis_scheduler.py           # Delayed jobs + repair sweeps
├── redis_admin.py               # Async/realtime inspection + replay helper
├── tests/                       # Pytest suite (uses an in-memory SQLite database)
└── pytest.ini                   # Pytest discovery settings
```

## Getting Started
1. **Create a Python virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   ```
2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
3. **Environment variables**  
   Copy `.env.example` to `.env` and adjust as needed:
   ```dotenv
   SECRET_KEY=devkey
   JWT_SECRET_KEY=change-me
   DATABASE_URI=postgresql://postgres:password@localhost:5432/DeliveryApp
   REDIS_URI=redis://localhost:6379/0
   FRONTEND_ORIGIN=http://localhost:5173
   ```
   `FRONTEND_ORIGIN` is used by Flask-CORS so the Vite dev server can hit this API. Set it to the exact origin you'll load the front-end from.

4. **Redis**
   Verify your local Redis instance is running:
   ```bash
   redis-cli ping
   ```
   Expected result:
   ```text
   PONG
   ```

5. **Database**
   ```bash
   .venv/bin/flask --app 'Delivery_app_BK:create_app("development")' db upgrade -d migrations
   ```
   The backend now uses Alembic migrations. Local development should be upgraded to head before starting the app or the async workers.
   
    Note: install and enable PostGIS on your PostgreSQL server for the best zone-geometry performance (simplification, centroid, and bbox derivation in DB). The latest geometry migration also expects `CREATE EXTENSION postgis` to succeed.

6. **Run the web application**
   ```bash
   python run.py
   ```

7. **Run the async stack**
   Start each process in its own terminal:
   ```bash
   APP_ENV=development .venv/bin/python redis_dispatcher.py
   APP_ENV=development .venv/bin/python redis_worker_default.py
   APP_ENV=development .venv/bin/python redis_worker_io.py
   APP_ENV=development .venv/bin/python redis_scheduler.py
   ```
   Process roles:
   - `redis_dispatcher.py`: claims durable event rows and enqueues Redis jobs
   - `redis_worker_default.py`: processes event, maintenance, and realtime relay jobs
   - `redis_worker_io.py`: processes provider-facing jobs like SMS/email
   - `redis_scheduler.py`: schedules repair sweeps, retries, and delayed work

## Production Deployment Model

Elastic Beanstalk web environments should run the web process only:

```text
web: gunicorn --worker-class eventlet -w 2 application:application
```

Do not run `dispatcher`, `worker-default`, `worker-io`, or `scheduler` in the EB web Procfile. Those processes should run in a separate supervised runtime such as:
- a separate EB worker environment
- ECS tasks
- a dedicated EC2/systemd process host

### Production Behavior

- Web runtime:
  - boots even if Redis is missing or temporarily unreachable
  - initializes Socket.IO with Redis fanout only when Redis is available
  - falls back to in-process Socket.IO if Redis is unavailable
- Async runtime:
  - requires a valid reachable `REDIS_URI`
  - fails fast on startup if Redis is unavailable
  - logs the Redis target and startup failure clearly

### Production Environment Variables

Required for the web environment:
- `APP_ENV=production`
- `DATABASE_URI`
- `SECRET_KEY`
- `JWT_SECRET_KEY`

Required for the async runtime:
- all of the above as needed by the app
- `REDIS_URI`

Recommended for both runtimes:
- `FRONTEND_ORIGINS`

### Degraded Mode Note

If the web environment is up but the async runtime is down, the API can still serve normal HTTP traffic, but Redis-backed features will be degraded or unavailable:
- delayed/scheduled jobs
- Redis unread notifications
- multi-instance websocket fanout
- background dispatch/worker processing

## Async Backbone

The backend now uses a DB-outbox style flow for durable business events:

```text
domain write
-> durable DB event row
-> dispatcher claim
-> Redis job
-> worker
-> side effect or websocket relay
```

Key rules:
- PostgreSQL remains the source of truth for durable events
- Redis is transport and shared ephemeral state, not the source of truth
- delivery is at-least-once
- workers must be idempotent
- driver live location stays ephemeral and is stored in Redis with TTL, not in the DB outbox

### Scheduled Messages

SMS and email actions now use the same async backbone, but with action-row scheduling metadata:

```text
business event row
-> enabled message template lookup
-> action row created
-> action row stores:
   - scheduled_for
   - schedule_anchor_type
   - schedule_anchor_at
-> action dispatcher decides:
   - enqueue now on messaging queue
   - or schedule for later with RQ Scheduler
-> worker reloads action row by id at execution time
```

Important behavior:
- the action row is the durable source of truth for send timing
- Redis/RQ does not calculate timing on its own
- `action_dispatch.py` reads the stored action-row schedule and either enqueues immediately or schedules the job
- the send task reloads the action row, entity state, and current template before sending
- template timing is snapshotted when the action row is created
- template content is read from the current template at execution time

Current scheduling model:
- positive offset: delayed send
- negative offset: anticipated send
- anticipated sends are only allowed for events with a future business anchor
- events without a future anchor support immediate or delayed sends only

## Async Admin Commands

Use [`redis_admin.py`](/Users/davidloorenz/Desktop/Developer/BeyoApps_2025/NextMark-app/Back_end/redis_admin.py) to inspect queues and replay failed durable work.

Examples:

```bash
APP_ENV=development .venv/bin/python redis_admin.py summary
APP_ENV=development .venv/bin/python redis_admin.py failed-jobs --limit 10
APP_ENV=development .venv/bin/python redis_admin.py failed-jobs --queue realtime --limit 20
APP_ENV=development .venv/bin/python redis_admin.py replay-order-event --id 463
APP_ENV=development .venv/bin/python redis_admin.py replay-plan-event --id 12
APP_ENV=development .venv/bin/python redis_admin.py replay-app-event --id 5
APP_ENV=development .venv/bin/python redis_admin.py requeue-order-action --id 17
APP_ENV=development .venv/bin/python redis_admin.py requeue-plan-action --id 8
```

Supported debug operations:
- queue summary
- failed job inspection
- replay durable order events
- replay durable delivery-plan events
- replay generic app outbox events
- requeue order and delivery-plan action rows

## Working with the Front-end

The React clients expect CORS to allow `http://localhost:5173`. As long as you keep `FRONTEND_ORIGIN` synced with the URL your dev server runs on, browser requests will succeed after signing in.

## Auth Workflow
There is no user-registration route yet. Seed at least one record in the `User` table (manually or via a database client) to exercise the token endpoints.

- `POST /api_v2/auths/login`  
  ```json
  {
    "email": "driver@example.com",
    "password": "secretpass",
    "time_zone": "Europe/Stockholm"
  }
  ```  
  Returns `access_token`, `refresh_token`, and minimal user data when the credentials match an existing row. Tokens include the `time_zone` claim.

- `POST /api_v2/auths/refresh_token`  
  Requires a valid refresh token in the `Authorization: Bearer` header and returns a new access token.

Custom JWT error handlers in `routers/auth_routers/utils/jwt_handler.py` standardise JSON responses for common token failures.

## Item Catalogue Endpoints
All routes live under `/item` and share the same creation pipeline:
1. The route receives JSON payloads.
2. `ObjectCreator.create` validates and normalises the payload.
3. `create_general_object` instantiates SQLAlchemy models and resolves relationships.
4. The response wrapper returns consistent `{"status", "message", "error", "data"}` envelopes.

### Create Category
- `POST /item/create_item_category`
  ```json
  { "name": "Seating" }
  ```

### Create Type
- `POST /item/create_item_type`
  ```json
  {
    "name": "Dining Chair",
    "properties": [1, 2]
  }
  ```
  `properties` is optional and links to `ItemProperty` records by ID.

### Create Property
- `POST /item/create_item_property`
  ```json
  {
    "name": "Set Of",
    "value": "4",
    "field_type": "number-keyboard",
    "options": {"min": 1, "max": 20}
  }
  ```

### Create Item
- `POST /item/create_item`
  ```json
  {
    "article_number": "030303",
    "item_type_id": 1,
    "item_category_id": 1,
    "properties": [1, 2],
    "weight": 12,
    "state": "in-stock",
    "position": "Warehouse A"
  }
  ```
  Relationship IDs are resolved automatically; simple column values pass through `ValueValidator` before assignment.

### Query Items
- `POST /item/query_item`  
  Supply `requested_data` (columns/relationships to serialise) and `query_filters`. Example:
  ```json
  {
    "requested_data": ["id", "article_number", {"properties": ["name", "value"]}],
    "query_filters": {
      "article_number": {"operation": "==", "value": "030303"},
      "state": {"operation": "ilike", "value": "%stock%"}
    }
  }
  ```
  Successful responses compress the payload to base64 GZip when `response.compress_payload()` is triggered.

## Testing
Pytest is configured via `tests/conftest.py` to initialise the app with the `"testing"` configuration and an in-memory SQLite database (`sqlite:///:memory:`). Run the suite with:
```bash
pytest
```
The current tests cover the item creation routes (`tests/test_item_routers/test_routes_create.py`) by asserting happy-path responses.

> **Note:** In this environment `pytest` may not be preinstalled—install it in your virtualenv before running the suite.

## Troubleshooting
- Ensure the PostgreSQL database specified by `DATABASE_URI` exists before starting the server.
- Ensure Redis is reachable at `REDIS_URI` before starting dispatcher/workers/scheduler.
- Because user creation is manual right now, invalid login attempts will fail with the generic `"something went wrong"` error. Seed data up-front for local testing.
- If you are on macOS, the local workers use `SimpleWorker` in development to avoid the Objective-C fork-safety crash that affects normal forked RQ workers.

With this setup you can run the HTTP API, the async stack, and the websocket relay flow locally against PostgreSQL and Redis.
