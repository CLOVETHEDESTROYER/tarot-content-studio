"""Serialize generation acceptance with the desktop install barrier."""
import functools
import threading
LOCK=threading.RLock()
installing=False


def generation_action(function):
    @functools.wraps(function)
    def wrapped(*args,**kwargs):
        with LOCK:
            if installing:raise ValueError('The studio is installing an update. Retry after relaunch.')
            return function(*args,**kwargs)
    return wrapped
