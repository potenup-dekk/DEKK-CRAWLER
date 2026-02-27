import os
import logging

from core.config import LOG_DIR
from logging.handlers import TimedRotatingFileHandler

def _setup_logger():
    logger = logging.getLogger("DEKK_Crawler")
    
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = TimedRotatingFileHandler(
        filename=os.path.join(LOG_DIR, "crawler.log"),
        when="midnight",
        interval=1,
        backupCount=30,   
        encoding="utf-8"
    )
    file_handler.suffix = "%Y-%m-%d"
    file_handler.setFormatter(formatter)

    # 에러 전용
    err_handler = TimedRotatingFileHandler(
        filename=os.path.join(LOG_DIR, "error.log"),
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8"
    )
    err_handler.suffix = "%Y-%m-%d"
    err_handler.setFormatter(formatter)
    err_handler.setLevel(logging.ERROR)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.addHandler(err_handler)
    
    return logger

logger = _setup_logger()
