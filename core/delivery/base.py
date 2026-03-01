from abc import ABC, abstractmethod


class BaseDelivery(ABC):
    
    @abstractmethod
    def create_batch(self, platform: str) -> int:
        pass

    @abstractmethod
    def send_raw_data(self, batch_id: int, chunk_list: list, crawled_at: str) -> None:
        pass
    
    @abstractmethod
    def complete_batch(self, batch_id: int, total_count: int, completed_at: str, error_message: str = None) -> None:
        pass
