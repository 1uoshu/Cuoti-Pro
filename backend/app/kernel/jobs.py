from collections.abc import Callable
from typing import Any

from fastapi import BackgroundTasks


KernelBackgroundTasks = BackgroundTasks


class JobRunner:
    """Kernel-owned background job adapter.

    The v1 implementation uses FastAPI background tasks. Plugins submit jobs
    through this adapter so the kernel can later replace it with a queue.
    """

    def enqueue(self, background_tasks: KernelBackgroundTasks, handler: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        background_tasks.add_task(handler, *args, **kwargs)
