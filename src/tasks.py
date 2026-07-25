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


def check_search_alerts(app) -> None:
    """Check due search alerts and create notifications for new results."""
    import src.db as db
    import src.search as search
    import json

    with app.app_context():
        due = db.get_due_search_alerts()
        for alert in due:
            try:
                sources = json.loads(alert["sources_json"])
                results = []
                for source in sources:
                    if source == "wikipedia":
                        results.extend(search.wikipedia(alert["query"], 10, user_id=alert["user_id"]))
                    elif source == "gbooks":
                        results.extend(search.gbooks(alert["query"], 10, {}, user_id=alert["user_id"]))
                    elif source == "semantic_scholar":
                        results.extend(search.semantic_scholar(alert["query"], 10, user_id=alert["user_id"]))
                    elif source:
                        try:
                            results.extend(search.browse_serpapi_search(alert["query"], 10, source, {}, user_id=alert["user_id"]))
                        except Exception:
                            pass

                new_ids = [str(r.get("id", "")) for r in results if r.get("id")]
                old_ids = json.loads(alert.get("last_result_ids_json", "[]"))
                new_results = [r for r in results if str(r.get("id", "")) not in old_ids]

                if new_results:
                    db.create_notification(
                        user_id=alert["user_id"],
                        title=f"New results for: {alert['query']}",
                        message=f"Found {len(new_results)} new result(s) for your saved alert '{alert['query']}'",
                        notification_type="search_alert",
                    )

                db.update_search_alert_check(alert["id"], new_ids)
            except Exception as e:
                logger.error(f"Search alert check failed for alert {alert['id']}: {e}")
