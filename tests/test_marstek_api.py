from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from marstek_api import (
    _desired_type,
    _find_existing_managed_device,
    _generate_new_id,
)


def test_desired_type_mapping():
    assert _desired_type("ct002") == "HME-4"
    assert _desired_type("ct003") == "HME-3"


def test_find_existing_managed_device_matches_prefix_and_type():
    devices = [
        {"devid": "acde48aaaaaa", "mac": "acde48aaaaaa", "type": "HME-4"},
        {"devid": "ffffffffffff", "mac": "ffffffffffff", "type": "HME-3"},
    ]

    found = _find_existing_managed_device(
        devices, expected_type="HME-4", mac_prefix="acde48"
    )
    assert found is not None
    assert found["devid"] == "acde48aaaaaa"


def test_find_existing_managed_device_ignores_wrong_type():
    devices = [
        {"devid": "acde48aaaaaa", "mac": "acde48aaaaaa", "type": "HME-3"},
    ]

    found = _find_existing_managed_device(
        devices, expected_type="HME-4", mac_prefix="acde48"
    )
    assert found is None


def test_generate_new_id_uses_prefix_and_avoids_collisions():
    devices = [
        {"devid": "acde48aaaaaa", "mac": "acde48aaaaaa"},
        {"devid": "acde48bbbbbb", "mac": "acde48bbbbbb"},
    ]

    new_id = _generate_new_id(devices, mac_prefix="acde48")
    assert new_id.startswith("acde48")
    assert len(new_id) == 12
    assert new_id not in {"acde48aaaaaa", "acde48bbbbbb"}
