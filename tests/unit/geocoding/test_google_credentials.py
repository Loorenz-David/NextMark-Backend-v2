import json

from Delivery_app_BK.lib import google_credentials as module


class _FakeSecretsClient:
    def __init__(self, secret_string: str):
        self._secret_string = secret_string

    def get_secret_value(self, SecretId):
        return {"SecretString": self._secret_string}


def _reset_caches():
    module.get_google_credentials_dict.cache_clear()
    module.get_google_geocoding_api_key.cache_clear()


def test_get_google_geocoding_api_key_prefers_env(monkeypatch):
    _reset_caches()
    monkeypatch.setenv("GOOGLE_GEOCODING_API_KEY", "env-key")

    key = module.get_google_geocoding_api_key()

    assert key == "env-key"


def test_get_google_geocoding_api_key_loads_raw_string_from_aws(monkeypatch):
    _reset_caches()
    monkeypatch.delenv("GOOGLE_GEOCODING_API_KEY", raising=False)
    monkeypatch.setattr(
        module.boto3,
        "client",
        lambda *args, **kwargs: _FakeSecretsClient("aws-raw-key"),
    )

    key = module.get_google_geocoding_api_key()

    assert key == "aws-raw-key"


def test_get_google_geocoding_api_key_loads_json_field_from_aws(monkeypatch):
    _reset_caches()
    monkeypatch.delenv("GOOGLE_GEOCODING_API_KEY", raising=False)
    secret_string = json.dumps({"GOOGLE_GEOCODING_API_KEY": "aws-json-key"})
    monkeypatch.setattr(
        module.boto3,
        "client",
        lambda *args, **kwargs: _FakeSecretsClient(secret_string),
    )

    key = module.get_google_geocoding_api_key()

    assert key == "aws-json-key"
