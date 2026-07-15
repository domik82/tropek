from tropek.config import CacheTTLSettings


def test_trend_column_ttl_defaults_to_seven_days():
    settings = CacheTTLSettings({})
    assert settings.trend_column == 7 * 24 * 60 * 60


def test_trend_column_ttl_reads_override():
    settings = CacheTTLSettings({'trend_column': 3600})
    assert settings.trend_column == 3600
