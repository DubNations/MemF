from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from cognitive_os.agents.communication.message_queue import Message, MessageQueue


class MessageRouter:
    def __init__(self):
        self._handlers: Dict[str, Callable] = {}
        self._queues: Dict[str, MessageQueue] = {}
        self._routes: Dict[str, List[str]] = {}
    
    def register_handler(self, message_type: str, handler: Callable) -> None:
        self._handlers[message_type] = handler
    
    def unregister_handler(self, message_type: str) -> None:
        if message_type in self._handlers:
            del self._handlers[message_type]
    
    def create_queue(self, name: str, max_size: int = 100) -> MessageQueue:
        queue = MessageQueue(max_size=max_size)
        self._queues[name] = queue
        return queue
    
    def get_queue(self, name: str) -> Optional[MessageQueue]:
        return self._queues.get(name)
    
    def delete_queue(self, name: str) -> bool:
        if name in self._queues:
            del self._queues[name]
            return True
        return False
    
    def add_route(self, source: str, targets: List[str]) -> None:
        self._routes[source] = targets
    
    def remove_route(self, source: str) -> None:
        if source in self._routes:
            del self._routes[source]
    
    def route_message(self, message: Message) -> List[str]:
        targets = self._routes.get(message.sender, [])
        for target in targets:
            queue = self._queues.get(target)
            if queue:
                queue.push(message)
        return targets
    
    def broadcast(self, message: Message, targets: List[str]) -> None:
        for target in targets:
            queue = self._queues.get(target)
            if queue:
                queue.push(message)
    
    def send_to(self, target: str, message: Message) -> None:
        queue = self._queues.get(target)
        if queue:
            queue.push(message)
    
    def process_message(self, message: Message) -> Any:
        handler = self._handlers.get(message.metadata.get("type", "default"))
        if handler:
            return handler(message)
        return None
    
    def process_all_pending(self, queue_name: str) -> List[Any]:
        queue = self._queues.get(queue_name)
        if not queue:
            return []
        
        results = []
        for message in queue.get_all():
            result = self.process_message(message)
            results.append(result)
        return results
