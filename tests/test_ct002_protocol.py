from ct002.ct002 import (
    build_payload,
    parse_request,
    calculate_checksum,
    SOH,
    STX,
    ETX,
    CT002,
    RESPONSE_LABELS,
)


def test_parse_request_roundtrip():
    fields = ["HMG-50", "AABBCCDDEEFF", "HME-4", "112233445566", "5", "7"]
    payload = build_payload(fields)
    parsed, error = parse_request(payload)
    assert error is None
    assert parsed == fields


def test_parse_request_checksum_error():
    fields = ["HMG-50", "AABBCCDDEEFF", "HME-4", "112233445566", "0", "0"]
    payload = bytearray(build_payload(fields))
    payload[-1] = ord("0") if payload[-1] != ord("0") else ord("1")
    parsed, error = parse_request(payload)
    assert parsed is None
    assert "Checksum" in error


def test_parse_request_checksum_space_tolerance():
    fields = ["HMG-50", "AABBCCDDEEFF", "HME-4", "112233445566", "0", "0"]
    payload = bytearray(build_payload(fields))
    payload[-2] = ord(" ")
    parsed, error = parse_request(payload)
    assert error is None
    assert parsed == fields


def test_build_payload_length_and_checksum():
    fields = ["HMG-50", "AABBCCDDEEFF", "HME-3", "112233445566", "0", "0"]
    payload = build_payload(fields)
    assert payload[0] == SOH
    assert payload[1] == STX
    assert payload[-3] == ETX
    sep_index = payload.find(b"|", 2)
    length = int(payload[2:sep_index].decode("ascii"))
    assert length == len(payload)
    xor = 0
    for b in payload[: length - 2]:
        xor ^= b
    expected = f"{xor:02x}".encode("ascii")
    assert payload[-2:] == expected


def test_checksum_matches_helper():
    payload = bytearray([SOH, STX, 0x30, 0x30, ETX])
    checksum = calculate_checksum(payload)
    assert isinstance(checksum, int)
    expected = SOH ^ STX ^ 0x30 ^ 0x30 ^ ETX
    assert checksum == expected


def test_discharge_from_total_keeps_response_field_count_stable():
    device = CT002(discharge_from_total=True)
    request_fields = ["HMG-50", "AABBCCDDEEFF", "HME-4", "112233445566", "0", "0"]

    response_fields = device._build_response_fields(
        request_fields=request_fields,
        values=[500, 0, 0],
        adjustment=0,
        consumer_id="consumer-a",
    )

    assert len(response_fields) == len(RESPONSE_LABELS)


def test_discharge_from_total_uses_positive_magnitude_for_charge_discharge_fields():
    device = CT002(discharge_from_total=True)
    request_fields = ["HMG-50", "AABBCCDDEEFF", "HME-4", "112233445566", "0", "0"]

    # Net import -> discharge field on phase A
    response_import = device._build_response_fields(
        request_fields=request_fields,
        values=[120, 0, 0],
        adjustment=0,
        consumer_id="consumer-a",
    )
    assert response_import[20] == "120"  # A_dchrg_power

    # Net export -> charge field on phase A (magnitude, not negative)
    response_export = device._build_response_fields(
        request_fields=request_fields,
        values=[-80, 0, 0],
        adjustment=0,
        consumer_id="consumer-a",
    )
    assert response_export[15] == "80"  # A_chrg_power
