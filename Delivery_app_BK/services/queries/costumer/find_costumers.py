from __future__ import annotations

from typing import Any

from sqlalchemy import String, or_
from sqlalchemy.orm import Query

from Delivery_app_BK.models import Costumer, CostumerAddress, CostumerPhone, db
from Delivery_app_BK.services.queries.utils import parsed_string_to_list
from Delivery_app_BK.services.utils import inject_team_id, model_requires_team

from ...context import ServiceContext
from ..utils import apply_pagination_by_date


def find_costumers(
    params: dict[str, Any],
    ctx: ServiceContext,
    query: Query | None = None,
):
    query = query or db.session.query(Costumer)

    params_dict = dict(params or {})
    if model_requires_team(Costumer) and ctx.inject_team_id:
        params_dict = inject_team_id(params_dict, ctx)

    if "team_id" in params_dict:
        query = query.filter(Costumer.team_id == params_dict.get("team_id"))

    q = str(params_dict.get("q") or "").strip()
    if q:
        pattern = f"%{q}%"
        string_filter_map = {
            "first_name": {"column": Costumer.first_name, "join": None},
            "last_name": {"column": Costumer.last_name, "join": None},
            "name": {
                "column": (
                    Costumer.first_name,
                    Costumer.last_name,
                ),
                "join": None,
            },
            "email": {"column": Costumer.email, "join": None},
            "external_source": {"column": Costumer.external_source, "join": None},
            "external_costumer_id": {"column": Costumer.external_costumer_id, "join": None},
            "phone": {
                "column": CostumerPhone.phone.cast(String),
                "join": (CostumerPhone, CostumerPhone.costumer_id == Costumer.id),
            },
            "address": {
                "column": CostumerAddress.address.cast(String),
                "join": (CostumerAddress, CostumerAddress.costumer_id == Costumer.id),
            },
        }

        selector_keys = set()
        reserved_keys = {
            "q",
            "team_id",
            "sort",
            "limit",
            "after_date",
            "after_id",
            "before_date",
            "before_id",
        }

        if "s" in params_dict:
            selector_keys.update(parsed_string_to_list(params_dict["s"], ctx))

        selector_keys.update(
            key for key in params_dict.keys() if key not in reserved_keys and key in string_filter_map
        )

        active_columns = selector_keys if selector_keys else set(string_filter_map.keys())
        joined_relations = set()
        filters = []

        for key in active_columns:
            config = string_filter_map.get(key)
            if not config:
                continue

            column = config["column"]
            join_target = config.get("join")

            if join_target and key not in joined_relations:
                query = query.outerjoin(*join_target)
                joined_relations.add(key)

            if isinstance(column, tuple):
                filters.append(or_(*[col.ilike(pattern) for col in column]))
            else:
                filters.append(column.ilike(pattern))

        if filters:
            query = query.filter(or_(*filters))
            if joined_relations:
                query = query.distinct()

    sort = str(params_dict.get("sort") or "").lower().strip()
    if sort == "last_name_asc":
        query = query.order_by(
            Costumer.last_name.asc(),
            Costumer.id.asc(),
        )
        return query
    else:
        query = query.order_by(
            Costumer.created_at.desc(),
            Costumer.id.desc(),
        )

    query = apply_pagination_by_date(
        query=query,
        date_column=Costumer.created_at,
        id_column=Costumer.id,
        params=params_dict,
        sort="date_asc" if sort == "created_at_asc" else "date_desc",
    )

    return query
