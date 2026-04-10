# Facility, Vehicle & Zone Config Expansion Plan

> Status: PENDING IMPLEMENTATION
> Scope: Model layer only. No business logic, no router changes beyond renaming.
> Sequence: Each phase is a discrete migration + file set. Do not mix phases.

---

## Architectural Principles (locked in before writing code)

**RouteGroup** is a zone container. It holds orders grouped by zone within a plan.
It does not hold configuration, facility references, or anything the user or AI edits.

**RouteSolution** is the configuration layer. It is what the user and AI tune to improve
optimization. Driver, vehicle, facility anchor, timing window — all of it lives here.

**ZoneTemplate** is the imprint contract. At plan creation time, the system reads the
active ZoneTemplate for each zone and stamps its values onto the created RouteSolution.
After that point, the RouteSolution is independent. Editing the template does not
retroactively change existing solutions.

**Facility** is an operational node in the logistics graph, not just an address store.
A depot dispatches. A hub transfers. A warehouse stores. The `type` + `can_dispatch`
columns encode this without table splitting.

---

## Phase 1 — Rename `warehouse` → `facility`

### 1.1 Migration

Write one Alembic migration that:
- Renames table `warehouse` → `facility`
- Renames FK column `warehouse_id` → `facility_id` on any referencing table
  (currently none outside of the model itself, but check before running)
- Renames the sequence and any named constraints/indexes that include "warehouse"

```python
# Pseudocode — fill in actual constraint names from \d warehouse in psql
op.rename_table("warehouse", "facility")
op.execute("ALTER INDEX ix_warehouse_team_id RENAME TO ix_facility_team_id")
op.execute("ALTER INDEX ix_warehouse_client_id RENAME TO ix_facility_client_id")
op.execute("ALTER INDEX ix_warehouse_name RENAME TO ix_facility_name")
# Rename the backref sequence if using serial
```

### 1.2 Python Model File

Rename file:
`models/tables/infrastructure/warehouse.py` → `models/tables/infrastructure/facility.py`

Rename class: `Warehouse` → `Facility`
Change `__tablename__` = `"facility"`
Change backref on Team relationship: `"ware_houses"` → `"facilities"`

### 1.3 All Referencing Python Files (full list)

| Current path | Action |
|---|---|
| `models/__init__.py` | Update import: `from ...facility import Facility` |
| `services/commands/infrastructure/create/create_warehouse.py` | Rename file → `create_facility.py`, update class/import |
| `services/commands/infrastructure/update/update_warehouse.py` | Rename file → `update_facility.py`, update class/import |
| `services/commands/infrastructure/delete/delete_warehouse.py` | Rename file → `delete_facility.py`, update class/import |
| `services/commands/infrastructure/create/__init__.py` | Update import |
| `services/commands/infrastructure/update/__init__.py` | Update import |
| `services/commands/infrastructure/delete/__init__.py` | Update import |
| `services/queries/infrastructure/warehouse/get_warehouse.py` | Move to `queries/infrastructure/facility/get_facility.py` |
| `services/queries/infrastructure/warehouse/find_warehouses.py` | Move to `queries/infrastructure/facility/find_facilities.py` |
| `services/queries/infrastructure/warehouse/list_warehouses.py` | Move to `queries/infrastructure/facility/list_facilities.py` |
| `services/queries/infrastructure/warehouse/serialize_warehouses.py` | Move to `queries/infrastructure/facility/serialize_facilities.py` |
| `services/queries/infrastructure/warehouse/__init__.py` | Recreate under `facility/` folder |
| `services/queries/infrastructure/__init__.py` | Update import |
| `routers/api_v2/infrastructure.py` | Rename all `warehouse` → `facility` in endpoint paths, imports, variable names |
| `templates/shopify_app.html` | Update any "warehouse" references in the HTML |

### 1.4 Verification Checklist (Phase 1)

- [ ] `grep -r "warehouse" Delivery_app_BK/` returns zero hits (excluding migration history)
- [ ] `grep -r "Warehouse" Delivery_app_BK/` returns zero hits
- [ ] All migrations run cleanly against a local DB
- [ ] `/facilities/` endpoints return 200
- [ ] Existing facility rows are intact after migration

---

## Phase 2 — Expand Facility Model

Add columns to the `facility` table. One Alembic migration.

### 2.1 New Columns

```python
# Type discriminator — enables conditional routing logic and AI reasoning
facility_type = Column(
    String,
    nullable=False,
    default="warehouse",
    index=True,
)
# Values: "warehouse" | "depot" | "hub" | "pickup_point"
# Column named facility_type to avoid collision with SQLAlchemy reserved word "type"

# Dispatch capability — the single flag the optimizer queries when selecting a route start
can_dispatch = Column(Boolean, nullable=False, default=False)

# Return capability — whether this facility can receive returned orders
can_receive_returns = Column(Boolean, nullable=False, default=False)

# Operating hours — when the facility is open; used by AI and optimizer for time window validation
operating_hours = Column(
    JSONB().with_variant(JSON, "sqlite"),
    nullable=True,
)
# Schema: [{"day": "mon", "open": "08:00", "close": "18:00"}, ...]
# Days: "mon" | "tue" | "wed" | "thu" | "fri" | "sat" | "sun"

# Service time defaults — used when no vehicle-specific override is set
default_loading_time_seconds = Column(Integer, nullable=False, default=600)
default_unloading_time_seconds = Column(Integer, nullable=False, default=300)

# Throughput cap — soft limit for optimizer and AI scheduling
max_orders_per_day = Column(Integer, nullable=True)

# External system references — for ERP, WMS, or third-party integrations
external_refs = Column(
    JSONB().with_variant(JSON, "sqlite"),
    nullable=True,
)
# Schema: {"erp_id": "...", "wms_location_code": "...", "shopify_location_id": "..."}
```

### 2.2 Migration Pseudocode

```python
op.add_column("facility", sa.Column("facility_type", sa.String(), nullable=False, server_default="warehouse"))
op.add_column("facility", sa.Column("can_dispatch", sa.Boolean(), nullable=False, server_default="false"))
op.add_column("facility", sa.Column("can_receive_returns", sa.Boolean(), nullable=False, server_default="false"))
op.add_column("facility", sa.Column("operating_hours", postgresql.JSONB(), nullable=True))
op.add_column("facility", sa.Column("default_loading_time_seconds", sa.Integer(), nullable=False, server_default="600"))
op.add_column("facility", sa.Column("default_unloading_time_seconds", sa.Integer(), nullable=False, server_default="300"))
op.add_column("facility", sa.Column("max_orders_per_day", sa.Integer(), nullable=True))
op.add_column("facility", sa.Column("external_refs", postgresql.JSONB(), nullable=True))

op.create_index("ix_facility_facility_type", "facility", ["team_id", "facility_type"])
op.create_index("ix_facility_can_dispatch", "facility", ["team_id", "can_dispatch"])
```

### 2.3 Verification Checklist (Phase 2)

- [ ] Migration runs cleanly, all columns present in `\d facility`
- [ ] Existing rows have `facility_type = "warehouse"`, `can_dispatch = false`
- [ ] Model file reflects all new columns with correct types and defaults

---

## Phase 3 — Expand Vehicle Model

One Alembic migration. No rename — table stays `vehicle`.

### 3.1 New Columns

```python
# Home facility — where this vehicle is based; enables multi-depot vehicle assignment
home_facility_id = Column(
    Integer,
    ForeignKey("facility.id", ondelete="SET NULL"),
    nullable=True,
    index=True,
)

# Operational state — current state of the vehicle for UI and AI reasoning
status = Column(
    String,
    nullable=False,
    default="idle",
    index=True,
)
# Values: "idle" | "in_route" | "loading" | "offline" | "maintenance"

# Availability flag — hard off-switch; overrides scheduling
is_active = Column(Boolean, nullable=False, default=True, index=True)

# Capabilities — what this vehicle can carry; matched against order requirements
capabilities = Column(
    JSONB().with_variant(JSON, "sqlite"),
    nullable=True,
)
# Schema: ["cold_chain", "fragile", "heavy_load", "returns", "oversized"]

# Per-stop service time — improves ETA accuracy for this vehicle specifically
loading_time_per_stop_seconds = Column(Integer, nullable=False, default=0)
unloading_time_per_stop_seconds = Column(Integer, nullable=False, default=0)

# Fixed routing cost — used by cost-aware optimizer scoring
fixed_cost = Column(Float, nullable=False, default=0.0)
```

### 3.2 New Relationship (add to Vehicle class)

```python
home_facility = relationship(
    "Facility",
    foreign_keys=[home_facility_id],
    lazy="selectin",
)
```

### 3.3 Migration Pseudocode

```python
op.add_column("vehicle", sa.Column("home_facility_id", sa.Integer(), sa.ForeignKey("facility.id", ondelete="SET NULL"), nullable=True))
op.add_column("vehicle", sa.Column("status", sa.String(), nullable=False, server_default="idle"))
op.add_column("vehicle", sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"))
op.add_column("vehicle", sa.Column("capabilities", postgresql.JSONB(), nullable=True))
op.add_column("vehicle", sa.Column("loading_time_per_stop_seconds", sa.Integer(), nullable=False, server_default="0"))
op.add_column("vehicle", sa.Column("unloading_time_per_stop_seconds", sa.Integer(), nullable=False, server_default="0"))
op.add_column("vehicle", sa.Column("fixed_cost", sa.Float(), nullable=False, server_default="0"))

op.create_index("ix_vehicle_home_facility_id", "vehicle", ["team_id", "home_facility_id"])
op.create_index("ix_vehicle_is_active", "vehicle", ["team_id", "is_active"])
op.create_index("ix_vehicle_status", "vehicle", ["team_id", "status"])
```

### 3.4 Verification Checklist (Phase 3)

- [ ] Migration runs cleanly
- [ ] Existing vehicle rows have `is_active = true`, `status = "idle"`, `fixed_cost = 0`
- [ ] `home_facility_id` is nullable for all existing rows (they have no home facility yet)

---

## Phase 4 — Expand ZoneTemplate (replace config_json with typed columns)

Replace the untyped `config_json` JSONB blob with explicit typed columns.
Keep a `meta` JSONB column for anything that does not warrant a dedicated column.

### 4.1 Design Rationale

Typed columns allow:
- Direct SQL filtering: `WHERE max_vehicles > 1` or `WHERE default_facility_id = 3`
- AI tool queries: the operator can query `zone_template` efficiently without parsing JSONB
- Pydantic validation at the service layer against a known schema
- Index support on `default_facility_id` for facility-scoped plan creation

`meta` JSONB survives for customer-specific overrides and future fields that have not
yet earned a column.

### 4.2 New Columns

```python
# Facility anchor — the facility that dispatches orders for this zone
default_facility_id = Column(
    Integer,
    ForeignKey("facility.id", ondelete="SET NULL"),
    nullable=True,
    index=True,
)

# Route sizing — maximum orders per route solution in this zone
max_orders_per_route = Column(Integer, nullable=True)

# Vehicle count cap — how many route solutions to create for this zone's route group
max_vehicles = Column(Integer, nullable=True)

# Operating window — the time window applied to route solutions created from this template
operating_window_start = Column(String(5), nullable=True)   # "HH:MM", e.g. "08:00"
operating_window_end = Column(String(5), nullable=True)     # "HH:MM", e.g. "18:00"

# ETA tolerance — default eta_tolerance_seconds stamped onto route solutions
eta_tolerance_seconds = Column(Integer, nullable=False, default=0)

# Capability filter — only vehicles with ALL of these capabilities are eligible
vehicle_capabilities_required = Column(
    JSONB().with_variant(JSON, "sqlite"),
    nullable=True,
)
# Schema: ["cold_chain", "fragile"]

# Preferred vehicles — soft preference list; AI uses this before selecting from the full pool
preferred_vehicle_ids = Column(
    JSONB().with_variant(JSON, "sqlite"),
    nullable=True,
)
# Schema: [1, 4, 7]  (vehicle.id values scoped to this team)

# Route end strategy default — stamped onto route solutions at creation
default_route_end_strategy = Column(
    String,
    nullable=False,
    default="round_trip",
)
# Values: "round_trip" | "custom_end_address" | "last_stop"

# Meta — escape hatch for unstructured or future config; not queried by core logic
meta = Column(
    JSONB().with_variant(JSON, "sqlite"),
    nullable=True,
)
```

### 4.3 New Relationship (add to ZoneTemplate class)

```python
default_facility = relationship(
    "Facility",
    foreign_keys=[default_facility_id],
    lazy="selectin",
)
```

### 4.4 Migration Pseudocode

```python
# Add all new typed columns
op.add_column("zone_template", sa.Column("default_facility_id", sa.Integer(), sa.ForeignKey("facility.id", ondelete="SET NULL"), nullable=True))
op.add_column("zone_template", sa.Column("max_orders_per_route", sa.Integer(), nullable=True))
op.add_column("zone_template", sa.Column("max_vehicles", sa.Integer(), nullable=True))
op.add_column("zone_template", sa.Column("operating_window_start", sa.String(5), nullable=True))
op.add_column("zone_template", sa.Column("operating_window_end", sa.String(5), nullable=True))
op.add_column("zone_template", sa.Column("eta_tolerance_seconds", sa.Integer(), nullable=False, server_default="0"))
op.add_column("zone_template", sa.Column("vehicle_capabilities_required", postgresql.JSONB(), nullable=True))
op.add_column("zone_template", sa.Column("preferred_vehicle_ids", postgresql.JSONB(), nullable=True))
op.add_column("zone_template", sa.Column("default_route_end_strategy", sa.String(), nullable=False, server_default="round_trip"))
op.add_column("zone_template", sa.Column("meta", postgresql.JSONB(), nullable=True))

# Migrate any existing data from config_json into typed columns
# Run a data migration script if config_json has live values (check before dropping)

# Drop config_json only after data migration is confirmed
op.drop_column("zone_template", "config_json")

op.create_index("ix_zone_template_default_facility", "zone_template", ["team_id", "default_facility_id"])
```

> IMPORTANT: Before dropping `config_json`, run a SELECT to check if any rows have
> non-empty config_json values that need to be migrated to the new columns.
> If rows are empty (default=dict), drop immediately. If not, write a data migration loop first.

### 4.5 Verification Checklist (Phase 4)

- [ ] `config_json` column no longer exists in `zone_template`
- [ ] All new typed columns present
- [ ] `default_facility_id` nullable for all existing rows
- [ ] `default_route_end_strategy` = `"round_trip"` for all existing rows
- [ ] `eta_tolerance_seconds` = `0` for all existing rows

---

## Phase 5 — Add Facility FKs to RouteSolution

The user edits RouteSolution to configure route optimization.
The driver departs from and optionally returns to a Facility.
These replace the raw `start_location` / `end_location` JSONB when a facility is the anchor.

### 5.1 New Columns

```python
start_facility_id = Column(
    Integer,
    ForeignKey("facility.id", ondelete="SET NULL"),
    nullable=True,
    index=True,
)

end_facility_id = Column(
    Integer,
    ForeignKey("facility.id", ondelete="SET NULL"),
    nullable=True,
)
```

### 5.2 Resolution Rule (enforced in domain layer, not model)

When `start_facility_id` is set → optimizer uses `facility.property_location.coordinates`
as the route start anchor. `start_location` JSONB is ignored.

When `start_facility_id` is null → optimizer falls back to `start_location` JSONB.

This rule lives in the domain/optimizer layer, not in the model. The model stays dumb.

### 5.3 New Relationships (add to RouteSolution class)

```python
start_facility = relationship(
    "Facility",
    foreign_keys=[start_facility_id],
    lazy="selectin",
)

end_facility = relationship(
    "Facility",
    foreign_keys=[end_facility_id],
    lazy="selectin",
)
```

### 5.4 Migration Pseudocode

```python
op.add_column("route_solution", sa.Column("start_facility_id", sa.Integer(), sa.ForeignKey("facility.id", ondelete="SET NULL"), nullable=True))
op.add_column("route_solution", sa.Column("end_facility_id", sa.Integer(), sa.ForeignKey("facility.id", ondelete="SET NULL"), nullable=True))

op.create_index("ix_route_solution_start_facility_id", "route_solution", ["start_facility_id"])
```

### 5.5 Verification Checklist (Phase 5)

- [ ] Both columns nullable on all existing rows
- [ ] Relationships resolve correctly in ORM queries
- [ ] `start_location` JSONB still present (not dropped — still used for custom addresses)

---

## Entity Relationship Summary (post all phases)

```
Facility
├── facility_type: warehouse | depot | hub | pickup_point
├── can_dispatch: bool
├── operating_hours: JSONB
└── FK ← Vehicle.home_facility_id
    FK ← ZoneTemplate.default_facility_id
    FK ← RouteSolution.start_facility_id
    FK ← RouteSolution.end_facility_id

Vehicle
├── home_facility_id → Facility
├── status: idle | in_route | loading | offline | maintenance
├── is_active: bool
├── capabilities: JSONB ["cold_chain", ...]
└── FK ← RouteSolution.vehicle_id  (already exists)

ZoneTemplate (per zone, one active)
├── default_facility_id → Facility
├── max_vehicles: int
├── max_orders_per_route: int
├── operating_window_start / end: "HH:MM"
├── eta_tolerance_seconds: int
├── vehicle_capabilities_required: JSONB
├── preferred_vehicle_ids: JSONB
├── default_route_end_strategy: string
└── meta: JSONB

Zone → RouteGroup (zone container, no config)
    └── RouteSolution (user/AI editable config)
            ├── driver_id → User
            ├── vehicle_id → Vehicle
            ├── start_facility_id → Facility
            ├── end_facility_id → Facility
            ├── set_start_time / set_end_time
            ├── route_end_strategy
            └── eta_tolerance_seconds
```

---

## AI Reasoning Path (enabled by this schema)

At plan creation for Zone X:
1. Read active ZoneTemplate for Zone X
2. Stamp `default_facility_id` → `RouteSolution.start_facility_id`
3. Stamp `default_route_end_strategy` → `RouteSolution.route_end_strategy`
4. Stamp `eta_tolerance_seconds` → `RouteSolution.eta_tolerance_seconds`
5. Filter available vehicles: `Vehicle.home_facility_id = default_facility_id AND is_active = true`
   AND capabilities ⊇ `vehicle_capabilities_required`
6. Apply `preferred_vehicle_ids` as priority order
7. Create up to `max_vehicles` RouteSolutions

At runtime, the AI can query:
- "Which facilities can dispatch today?" → `WHERE can_dispatch = true AND team_id = X`
- "Which vehicles are available at Depot B?" → `WHERE home_facility_id = B AND is_active = true AND status = 'idle'`
- "What is the default config for Zone 3?" → typed column read, no JSONB parsing

---

## Implementation Order

```
Phase 1 (rename)  →  Phase 2 (facility expand)  →  Phase 3 (vehicle expand)
                                                          ↓
                                                   Phase 4 (zone template)
                                                          ↓
                                                   Phase 5 (route solution FKs)
```

Phase 1 must complete before Phase 2-5 (they all FK to `facility`).
Phases 2, 3, 4 are independent of each other after Phase 1.
Phase 5 depends on Phase 2 (needs `facility` table to exist under the new name).
