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


def test_ct002_response_field_count_stable():
    device = CT002()
    request_fields = ["HMG-50", "AABBCCDDEEFF", "HME-4", "112233445566", "0", "0"]

    response_fields = device._build_response_fields(
        request_fields=request_fields,
        values=[500, 0, 0],
        consumer_id="consumer-a",
    )

    assert len(response_fields) == len(RESPONSE_LABELS)


def test_ct002_relays_other_storage_reports_only():
    device = CT002()
    request_fields = ["HMG-50", "AABBCCDDEEFF", "HME-4", "112233445566", "0", "0"]

    # consumer-a is on phase A, consumer-b on phase B
    device._update_consumer_report("consumer-a", charge_power=0, discharge_power=180)
    device._update_consumer_report("consumer-b", charge_power=-240, discharge_power=0)
    device._assign_phase("consumer-a")
    device._assign_phase("consumer-b")

    response_for_a = device._build_response_fields(
        request_fields=request_fields,
        values=[10, 20, 30],
        consumer_id="consumer-a",
    )

    # only consumer-b data is visible to consumer-a
    assert response_for_a[16] == "-240"  # B_chrg_power
    assert response_for_a[21] == "0"  # B_dchrg_power
    assert response_for_a[9] == "1"  # B_chrg_nb
    assert response_for_a[15] == "0"  # A_chrg_power
    assert response_for_a[20] == "0"  # A_dchrg_power

    response_for_b = device._build_response_fields(
        request_fields=request_fields,
        values=[10, 20, 30],
        consumer_id="consumer-b",
    )

    # only consumer-a data is visible to consumer-b
    assert response_for_b[20] == "180"  # A_dchrg_power
    assert response_for_b[8] == "1"  # A_chrg_nb
    assert response_for_b[16] == "0"  # B_chrg_power
