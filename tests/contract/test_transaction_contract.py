import pytest
from foundry_v2.contracts.models import Conflict
from foundry_v2.substrate.transactions import assert_version, canonical, decode_cursor, encode_cursor


def test_cursor_roundtrip_and_malformed_input():
    resource = 'stable-opaque-id'
    assert decode_cursor(encode_cursor(resource)) == resource
    for value in ('not-base64', 'e30=', 'W10=', 'bnVsbA=='):
        with pytest.raises(ValueError):
            decode_cursor(value)


def test_version_and_payload_canonicalization():
    assert_version(3,3)
    with pytest.raises(Conflict,match='stale_version'):
        assert_version(3,2)
    assert canonical({'b':1,'a':2}) == canonical({'a':2,'b':1})
    with pytest.raises(ValueError):
        canonical({'amount':float('nan')})
