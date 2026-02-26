import logging
import os

# 로그 파일이 저장될 디렉토리 (없으면 자동 생성)
LOG_DIR = 'data' 
os.makedirs(LOG_DIR, exist_ok=True)

def _setup_logger():
    logger = logging.getLogger("DEKK_Crawler")
    
    if logger.hasHandlers():
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

    all_handler = logging.FileHandler(f'{LOG_DIR}/crawler.log', encoding='utf-8')
    all_handler.setFormatter(formatter)
    all_handler.setLevel(logging.INFO)
    logger.addHandler(all_handler)

    err_handler = logging.FileHandler(f'{LOG_DIR}/error.log', encoding='utf-8')
    err_handler.setFormatter(formatter)
    err_handler.setLevel(logging.ERROR)
    logger.addHandler(err_handler)
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)

    return logger

logger = _setup_logger()