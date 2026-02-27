import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

BASE_DIR = os.path.dirname(CURRENT_DIR)

DATA_DIR = os.path.join(BASE_DIR, 'data')
LOG_DIR = os.path.join(BASE_DIR, 'logs')

STATE_FILE_PATH = os.path.join(DATA_DIR, 'crawler_state.json')

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)
