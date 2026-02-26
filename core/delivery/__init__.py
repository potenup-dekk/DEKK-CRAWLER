import os
from .base import BaseDelivery
from .batch import BatchDelivery

def get_delivery() -> BaseDelivery:
    mode = os.getenv('DELIVERY_MODE', 'BATCH').upper()
    if mode == 'BATCH':
        return BatchDelivery()
    raise ValueError(f"지원하지 않는 DELIVERY_MODE: {mode}")
