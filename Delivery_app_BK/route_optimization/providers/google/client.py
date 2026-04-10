from __future__ import annotations
from functools import lru_cache

import os

from google.maps import routeoptimization_v1
from google.protobuf.json_format import MessageToDict

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.route_optimization.domain.models import (
    OptimizationRequest,
    OptimizationResult,
)
from Delivery_app_BK.route_optimization.providers.base import RouteOptimizationProvider
from Delivery_app_BK.route_optimization.providers.google.mapper import (
    GoogleRequestMapper,
    GoogleResponseMapper,
)



from google.oauth2 import service_account
from google.maps import routeoptimization_v1

from Delivery_app_BK.lib.secrets.google_credentials import (
    get_google_credentials_dict,
)


@lru_cache()
def get_optimization_client():
    credentials_info = get_google_credentials_dict()

    credentials = service_account.Credentials.from_service_account_info(
        credentials_info,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )

    return routeoptimization_v1.RouteOptimizationClient(
            credentials=credentials
        )


class GoogleRouteOptimizationProvider(RouteOptimizationProvider):
    name = "google_route_optimization"

    def __init__(self, project_id: str | None = None, location: str | None = None) -> None:
        project_id = project_id or os.environ.get("GOOGLE_ROUTE_OPTIMIZATION_PROJECT_ID")
        location = location or os.environ.get("GOOGLE_ROUTE_OPTIMIZATION_LOCATION", "us-central1")

        if not project_id:
            raise ValidationFailed("GOOGLE_ROUTE_OPTIMIZATION_PROJECT_ID is not configured.")

       
        self.parent = f"projects/{project_id}"
        self.location = location

        self.client = get_optimization_client()

    def optimize(self, request: OptimizationRequest) -> OptimizationResult:
        """
        Executes route optimization using Google Route Optimization API.
        """
        
        google_request = GoogleRequestMapper.build_request(
            parent=self.parent,
            request=request,
        )

        try:
            response = self.client.optimize_tours(request=google_request)
            print('Debugging: ', 'response')
            print(response)
            print('-------------')

        except Exception as e:
            print("GOOGLE API ERROR:", e, flush=True)
            raise ValidationFailed(f"Google Route Optimization API failed: {e}") from e


        try:
            response_dict = MessageToDict(
                response._pb,
                preserving_proto_field_name=True,
            )

        except Exception:
            print("Could not convert response to dict", flush=True)

        result = GoogleResponseMapper.parse_response(
            response_dict=response_dict,
            request=request,
        )

        if result is None:
            raise ValidationFailed("Google optimization returned no result")

        return result
