from __future__ import annotations
from functools import lru_cache
import os


from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.directions.domain.models import DirectionsRequest, DirectionsResult
from Delivery_app_BK.directions.providers.base import DirectionsProvider
from Delivery_app_BK.directions.providers.google.mapper import (
    GoogleDirectionsRequestMapper,
    GoogleDirectionsResponseMapper,
)

from google.oauth2 import service_account
from google.maps import routing_v2



from Delivery_app_BK.lib.secrets.google_credentials import (
    get_google_credentials_dict,
)


@lru_cache()
def get_routes_client():
    credentials_info = get_google_credentials_dict()

    credentials = service_account.Credentials.from_service_account_info(
        credentials_info,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )

    return routing_v2.RoutesClient(credentials=credentials)


class GoogleDirectionsProvider(DirectionsProvider):
    name = "google_compute_routes"

    def __init__(self, project_id: str | None = None) -> None:
        project_id = project_id or os.environ.get("GOOGLE_ROUTE_OPTIMIZATION_PROJECT_ID")
        if not project_id:
            raise ValidationFailed("GOOGLE_ROUTE_OPTIMIZATION_PROJECT_ID is not configured.")
        self.project_id = project_id

    def compute(self, request: DirectionsRequest) -> DirectionsResult:

      
        client = get_routes_client()


        payload, field_mask = GoogleDirectionsRequestMapper.build_request(request)

        try:
            response = client.compute_routes(
                request=payload,
                metadata=[("x-goog-fieldmask", field_mask)],
            )
        except Exception as exc:
            raise ValidationFailed(f"Google compute_routes failed: {exc}") from exc

        return GoogleDirectionsResponseMapper.parse_response(response, request)
