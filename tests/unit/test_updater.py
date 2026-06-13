from app.core.updater import parse_version


def test_parse_version():
    assert parse_version("1.0.0") == (1, 0, 0)
    assert parse_version("v2.1.4") == (2, 1, 4)
    assert parse_version("  V3.0.12  ") == (3, 0, 12)
    assert parse_version("invalid") == (0,)
