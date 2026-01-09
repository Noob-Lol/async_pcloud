import datetime

from async_pcloud.api import to_api_datetime


def test_to_api_datetime_dt():
    dt = datetime.datetime(2023, 10, 5, 12, 3, 12, tzinfo=datetime.timezone.utc)
    assert to_api_datetime(dt) == "2023-10-05T12:03:12+00:00"


def test_to_api_datetime_iso():
    assert to_api_datetime("2013-12-05T12:03:12") == "2013-12-05T12:03:12"
