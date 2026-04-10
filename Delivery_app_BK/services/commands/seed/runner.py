from sqlalchemy.exc import InvalidRequestError

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import db
from Delivery_app_BK.services.context import ServiceContext

from .registry import SEED_REGISTRY


def run_seed_registry(ctx: ServiceContext) -> dict:
    results: dict = {}

    def _apply() -> dict:
        for entry in SEED_REGISTRY:
            missing = [dep for dep in entry.depends_on if dep not in results]
            if missing:
                raise ValidationFailed(
                    f"Seeder '{entry.name}' missing dependencies: {', '.join(missing)}."
                )

            kwargs = {dep: results[dep] for dep in entry.depends_on}
            results[entry.name] = entry.seeder(ctx, **kwargs)

        return results

    try:
        with db.session.begin():
            return _apply()
    except InvalidRequestError as exc:
        if "already begun" not in str(exc).lower():
            raise
        return _apply()
