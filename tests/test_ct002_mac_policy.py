from ct002.ct002 import CT002, build_payload


def make_request(ct_mac):
    fields = ["HMG-50", "AABBCCDDEEFF", "HME-4", ct_mac, "0", "0"]
    return build_payload(fields)


def test_ct002_accepts_any_when_no_mac():
    device = CT002(ct_mac="", allow_any_ct_mac=True)
    response = device._handle_request(make_request("DEADBEEF0001"), ("1.1.1.1", 12345))
    assert response is not None


def test_ct002_strict_mac_rejects_mismatch():
    device = CT002(ct_mac="AABBCCDDEEFF", allow_any_ct_mac=False)
    response = device._handle_request(make_request("DEADBEEF0001"), ("1.1.1.1", 12345))
    assert response is None


def test_ct002_strict_mac_accepts_match():
    device = CT002(ct_mac="AABBCCDDEEFF", allow_any_ct_mac=False)
    response = device._handle_request(make_request("AABBCCDDEEFF"), ("1.1.1.1", 12345))
    assert response is not None
