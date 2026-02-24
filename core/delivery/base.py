from abc import ABC, abstractmethod


class BaseDelivery(ABC):
    @abstractmethod
    def send(self, dtos: list) -> None:
        raise NotImplementedError
