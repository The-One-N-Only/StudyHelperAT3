import threading
import logging
import uuid
from typing import Callable, Any, Optional
from dataclasses import dataclass, field
from queue import Queue
from enum import Enum

logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2


@dataclass
class Task:
    id: str
    func: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL


class BackgroundTaskQueue:
    """Simple in-process background task queue using threading."""

    def __init__(self, max_workers: int = 2):
        self._queue: Queue[Task] = Queue()
        self._workers: list[threading.Thread] = []
        self._running = False
        self._max_workers = max_workers
        self._results: dict[str, Any] = {}
        self._lock = threading.Lock()

    def start(self):
        self._running = True
        for _ in range(self._max_workers):
            worker = threading.Thread(target=self._worker_loop, daemon=True)
            worker.start()
            self._workers.append(worker)
        logger.info(f"Background task queue started with {self._max_workers} workers")

    def stop(self):
        self._running = False
        for _ in range(self._max_workers):
            self._queue.put(None)

    def enqueue(self, task: Task):
        self._queue.put(task)
        logger.debug(f"Task enqueued: {task.id}")

    def get_result(self, task_id: str) -> Optional[Any]:
        with self._lock:
            return self._results.get(task_id)

    def _set_result(self, task_id: str, result: Any):
        with self._lock:
            self._results[task_id] = result

    def _worker_loop(self):
        while self._running:
            task = self._queue.get()
            if task is None:
                break
            try:
                logger.info(f"Processing task: {task.id}")
                result = task.func(*task.args, **task.kwargs)
                self._set_result(task.id, result)
                logger.info(f"Task completed: {task.id}")
            except Exception as e:
                logger.error(f"Task failed: {task.id}", exc_info=e)
                self._set_result(task.id, {"status": False, "error": str(e)})
            finally:
                self._queue.task_done()


# Global singleton
task_queue = BackgroundTaskQueue(max_workers=2)


def generate_task_id() -> str:
    return str(uuid.uuid4())
