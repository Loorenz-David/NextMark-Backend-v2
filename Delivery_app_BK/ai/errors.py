from __future__ import annotations


class ThreadNotFoundError(Exception):
    def __init__(self, thread_id: str):
        self.thread_id = thread_id
        super().__init__(f"AI thread not found or expired: {thread_id}")


class ThreadAccessError(Exception):
    def __init__(self, thread_id: str):
        self.thread_id = thread_id
        super().__init__(f"Access denied to AI thread: {thread_id}")
