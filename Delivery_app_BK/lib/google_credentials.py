import os
import json
import boto3
from functools import lru_cache


SECRET_NAME = "prod/google/service-account"
GEOCODING_SECRET_NAME = "prod/google/geocoding-api-key"
REGION = "eu-north-1"


@lru_cache()
def get_google_credentials_dict():
    """
    Load Google service account credentials.

    Priority:
    1. Local environment variable (for dev)
    2. AWS Secrets Manager (for production)
    """

    # ✅ 1. Local fallback (development)
    local_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if local_json:
        try:
            return json.loads(local_json)
        except Exception as exc:
            raise RuntimeError(f"Invalid GOOGLE_SERVICE_ACCOUNT_JSON: {exc}") from exc

    # ✅ 2. AWS Secrets Manager (production)
    try:
        client = boto3.client("secretsmanager", region_name=REGION)
        response = client.get_secret_value(SecretId=SECRET_NAME)
    except Exception as exc:
        raise RuntimeError(f"Failed to fetch secret from AWS: {exc}") from exc

    secret_string = response.get("SecretString")
    if not secret_string:
        raise RuntimeError("SecretString not found in AWS response")

    try:
        return json.loads(secret_string)
    except Exception as exc:
        raise RuntimeError(f"Invalid JSON in AWS secret: {exc}") from exc


@lru_cache()
def get_google_geocoding_api_key() -> str:
    """
    Load the Google Geocoding API key.

    Priority:
    1. Local environment variable (for dev)
    2. AWS Secrets Manager (for production)

    Supported AWS secret formats:
    - raw string API key
    - JSON object containing one of:
      GOOGLE_GEOCODING_API_KEY, google_geocoding_api_key, api_key
    """

    local_key = os.environ.get("GOOGLE_GEOCODING_API_KEY")
    if local_key:
        return local_key

    try:
        client = boto3.client("secretsmanager", region_name=REGION)
        response = client.get_secret_value(SecretId=GEOCODING_SECRET_NAME)
    except Exception as exc:
        raise RuntimeError(f"Failed to fetch geocoding secret from AWS: {exc}") from exc

    secret_string = response.get("SecretString")
    if not secret_string:
        raise RuntimeError("SecretString not found in AWS response")

    try:
        payload = json.loads(secret_string)
    except Exception:
        payload = secret_string

    if isinstance(payload, str):
        key = payload.strip()
        if key:
            return key
        raise RuntimeError("Google geocoding API key secret is empty")

    if isinstance(payload, dict):
        for field_name in (
            "GOOGLE_GEOCODING_API_KEY",
            "google_geocoding_api_key",
            "api_key",
        ):
            key = payload.get(field_name)
            if isinstance(key, str) and key.strip():
                return key.strip()

    raise RuntimeError(
        "Google geocoding API key not found in AWS secret. "
        "Expected a raw string or a JSON object with GOOGLE_GEOCODING_API_KEY, "
        "google_geocoding_api_key, or api_key."
    )