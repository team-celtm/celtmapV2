import asyncio
import logging
import threading
from typing import Any, Coroutine, TypeVar

T = TypeVar("T")
logger = logging.getLogger(__name__)

# Global storage for a shared event loop per thread if needed,
# though usually asyncio.run is fine if no loop exists.
def run_async(coro: Coroutine[Any, Any, T]) -> T:
    """
    Safely runs an async coroutine from a synchronous context.
    Handles 'RuntimeError: asyncio.run() cannot be called from a running event loop'
    by using existing loops if available, or creating a new one.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running event loop, safe to use asyncio.run
        return asyncio.run(coro)

    # If we are here, there is already an event loop running in this thread.
    # We must ensure we don't try to nest asyncio.run().
    # Using nest_asyncio is one option, but here we can try a direct execution
    # or offloading to a thread if possible. 
    # For Celery tasks, usually there isn't a loop unless the worker is async.
    
    if loop.is_running():
        # This is a critical situation in synchronous Celery workers.
        # We can't use loop.run_until_complete(coro) since the loop is running.
        # We use a thread-safe future and wait for it.
        from concurrent.futures import Future

        def _run(c, f):
            try:
                res = asyncio.run(c)
                f.set_result(res)
            except Exception as e:
                f.set_exception(e)

        future = Future()
        thread = threading.Thread(target=_run, args=(coro, future))
        thread.start()
        return future.result()
    
    return loop.run_until_complete(coro)
