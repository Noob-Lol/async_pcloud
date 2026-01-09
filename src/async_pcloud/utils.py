import logging
from datetime import datetime

__version__ = "0.3.0"
log = logging.getLogger("async_pcloud")


def to_api_datetime(dt):
    """Converter to a datetime structure the pCloud API understands

    See https://docs.pcloud.com/structures/datetime.html
    """
    if isinstance(dt, datetime):
        return dt.isoformat()
    return dt
