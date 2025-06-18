from .base import Powermeter
import requests
import json
from typing import Union, List
from config.logger import logger


class HomeAssistant(Powermeter):
    def __init__(
        self,
        ip: str,
        port: str,
        use_https: bool,
        access_token: str,
        current_power_entity: Union[str, List[str]],
        power_calculate: bool,
        power_input_alias: Union[str, List[str]],
        power_output_alias: Union[str, List[str]],
        path_prefix: str,
    ):
        self.ip = ip
        self.port = port
        self.use_https = use_https
        self.access_token = access_token
        self.current_power_entity = (
            [current_power_entity]
            if isinstance(current_power_entity, str)
            else current_power_entity
        )
        self.power_calculate = power_calculate
        self.power_input_alias = (
            [power_input_alias]
            if isinstance(power_input_alias, str)
            else power_input_alias
        )
        self.power_output_alias = (
            [power_output_alias]
            if isinstance(power_output_alias, str)
            else power_output_alias
        )
        self.path_prefix = path_prefix
        self.session = requests.Session()

    def get_json(self, path):
        if self.path_prefix:
            path = self.path_prefix + path
        if self.use_https:
            url = f"https://{self.ip}:{self.port}{path}"
        else:
            url = f"http://{self.ip}:{self.port}{path}"
        headers = {
            "Authorization": "Bearer " + self.access_token,
            "content-type": "application/json",
        }

        try:
            response = self.session.get(url, headers=headers, timeout=10)
            response.raise_for_status()  # Raise an exception for bad status codes
            return response.json()
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON response from Home Assistant API: {e}")
            logger.error(
                f"Response content: {response.text[:200]}..."
            )  # Log first 200 chars
            raise ValueError(f"Home Assistant API returned invalid JSON: {e}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to connect to Home Assistant API: {e}")
            raise ValueError(f"Home Assistant API connection error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error calling Home Assistant API: {e}")
            raise ValueError(f"Home Assistant API error: {e}")

    def get_powermeter_watts(self):
        if not self.power_calculate:
            results = []
            for entity in self.current_power_entity:
                path = f"/api/states/{entity}"
                response = self.get_json(path)
                results.append(float(response["state"]))
            return results
        else:
            results = []
            for in_entity, out_entity in zip(
                self.power_input_alias, self.power_output_alias
            ):
                response = self.get_json(f"/api/states/{in_entity}")
                power_in = float(response["state"])
                response = self.get_json(f"/api/states/{out_entity}")
                power_out = float(response["state"])
                results.append(power_in - power_out)
            return results
