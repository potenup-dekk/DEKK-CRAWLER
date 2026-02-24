import os
from .base import BaseDelivery
from .sqs import SQSDelivery


def get_delivery() -> BaseDelivery:
    mode = os.getenv('DELIVERY_MODE', 'SQS').upper()
    if mode == 'SQS':
        return SQSDelivery()
    raise ValueError(f"지원하지 않는 DELIVERY_MODE: {mode}")
