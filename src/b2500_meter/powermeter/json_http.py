import json

import requests
from jsonpath_ng import parse
from requests.auth import HTTPBasicAuth

from b2500_meter.config.logger import logger

from .base import Powermeter


def extract_json_value(data, path):
    jsonpath_expr = parse(path)
    match = jsonpath_expr.find(data)
    if match:
        return float(match[0].value)
    else:
        raise ValueError("No match found for the JSON path")


class JsonHttpPowermeter(Powermeter):
    def __init__(
        self,
        url: str,
        json_path: str | list[str],
        username: str | None = None,
        password: str | None = None,
        headers: dict[str, str] | None = None,
    ):
        self.url = url
        self.json_paths = [json_path] if isinstance(json_path, str) else list(json_path)
        self.auth = HTTPBasicAuth(username, password) if username or password else None
        self.headers = headers or {}
        self.session = requests.Session()

    def get_json(self):
        try:
            response = self.session.get(
                self.url, headers=self.headers, auth=self.auth, timeout=10
            )
            response.raise_for_status()
            return response.json()
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON: {e}")
            logger.error(f"Response content: {response.text[:200]}...")
            raise ValueError(f"Invalid JSON response: {e}") from e
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP request error: {e}")
            raise ValueError(f"HTTP request error: {e}") from e

    def get_powermeter_watts(self) -> list[float]:
        data = self.get_json()
        values = []
        for path in self.json_paths:
            values.append(extract_json_value(data, path))
        return values
