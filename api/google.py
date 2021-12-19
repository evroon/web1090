from typing import Any

from logger import get_logger


class Schiphol:
    logger = get_logger('google')

    def __init__(self, data: Any) -> None:
        self.adsbdata = data
        self.db = data.db
