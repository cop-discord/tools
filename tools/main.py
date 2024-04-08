from types import ModuleType
from logging import getLogger
from typing import Coroutine, Callable, Any, DefaultDict, TypeVar, Optional, Union, AsyncGenerator, Awaitable
from pathlib import Path
from anyio import Path as AsyncPath
from collections import defaultdict
from asyncio import Lock, sleep, to_thread, wait_for, ensure_future
import arrow, traceback, aiohttp
from datetime import datetime
from functools import wraps, partial
from contextlib import asynccontextmanager
from tuuid import tuuid
from cashews._typing import KeyOrTemplate
from cashews.key import get_cache_key
from .file_types import FileParser, FileType
from dataclasses import dataclass

T = TypeVar("T")
logger = getLogger(__name__)
AsyncCallableResult_T = TypeVar("AsyncCallableResult_T")
AsyncCallable_T = Callable[..., Awaitable[AsyncCallableResult_T]]
DecoratedFunc = TypeVar("DecoratedFunc", bound=AsyncCallable_T)

def get_logger():
    return logger

METHOD_LOCKERS = {}

@dataclass
class Timer:
    start: float
    end: Optional[float] = None
    elapsed: Optional[float] = None

@asynccontextmanager
async def timeit():
    start = datetime.now().timestamp()
    timer = Timer(start = start)
    try:
        yield timer
    finally:
        end = datetime.now().timestamp()
        elapsed = end - start
        timer.end = end
        timer.elapsed = elapsed


@asynccontextmanager
async def borrow_temp_file(
    url: Optional[str] = None,
    filepath: Optional[str] = None,
    base="/tmp"
) -> AsyncGenerator[Union[AsyncPath, None], None]:
    if url == None:
        if filepath.endswith('/'):
            filepath = filepath[:-1]
        url = filepath
    parser = FileParser()
    _file = await parser.get_extension(url)
    file = AsyncPath(f"{base}/{_file.name}.{_file.extension}")
    try:
        yield file
    finally:
        await file.unlink(missing_ok=True)
        try:
            del parser
        except:
            pass

def format_int(n: Union[float, str, int]) -> str:
    """This function formats integers that are too large to iterate over with commas.

    Args:
        n: int / float / str

    Returns:
        string
    """
    if isinstance(n, float):
        n = "{:.2f}".format(n)
    if isinstance(n, str):
        if "." in n:
            amount, decimal = n.split('.')
            n = f"{amount}.{decimal[:2]}"
    if str(n).startswith("-"):
        neg = "-"
        n = str(n)[1:]
    else:
        neg = ""
    if "." in str(n):
        amount, decimal = str(n).split('.')
    else:
        amount = str(n)
        decimal = "00"
    reversed_amount = amount[::-1]
    chunks = [reversed_amount[i:i+3] for i in range(0, len(reversed_amount), 3)]
    formatted_amount = ",".join(chunks[::-1])
    return f"{neg}{formatted_amount}.{decimal}"



def retry(retries: int = 0, delay: int = 0, timeout: Optional[int] =None):
    """AutoMatically retry a callable object with an optional pause

    Args:
        retries (int, optional): _description_. Defaults to 0.
        delay (int, optional): _description_. Defaults to 0.
        timeout (_type_, optional): _description_. Defaults to None.
    """
    def decorator(function: Callable):
        async def wrapper(*args, **kwargs):
            errors = []

            for i in range(retries + 1):
                try:
                    result = await wait_for(function(*args, **kwargs), timeout=timeout)

                    return result
                except Exception as e:
                    tb_str = traceback.format_exception(type(e), value=e, tb=e.__traceback__)
                    errors.append(''.join(tb_str))

                    if i < retries:
                        await sleep(delay)

            error_message = f"Function failed after {retries} attempts. Here are the errors:\n" + "\n".join(errors)

            raise Exception(error_message)

        wrapper.original = function

        return wrapper

    return decorator

def lock(key: KeyOrTemplate, wait=True):
    """ In order to share memory between any asynchronous coroutine methods, we should use locker to lock our method,
        so that we can avoid some un-prediction actions.

    Args:
        name: Locker name.
        wait: If waiting to be executed when the locker is locked? if True, waiting until to be executed, else return
            immediately (do not execute).

    NOTE:
        This decorator must to be used on `async method`.
    """
    assert isinstance(key, str)

    def decorating_function(func: DecoratedFunc) -> DecoratedFunc:
        global METHOD_LOCKERS
        value = get_cache_key(func)
        locker = METHOD_LOCKERS.get(func)
        if not locker:
            locker = Lock()
            METHOD_LOCKERS[key] = locker

        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not wait and locker.locked():
                return
            try:
                await locker.acquire()
                return await func(*args, **kwargs)
            finally:
                locker.release()
        return wrapper
    return decorating_function

def limit_calls(freq: float = 1) -> Callable[[Callable[..., Coroutine[Any, Any, T]]], Callable[..., Coroutine[Any, Any, T]]]:
    """Only allows a function to be called x amount of times at a time and will sleep until the ones that are running are finished"""
    def decorator(func: Callable[..., Coroutine[Any, Any, T]]) -> Callable[..., Coroutine[Any, Any, T]]:
        locks: DefaultDict[str, Lock] = defaultdict(Lock)
        call_times: DefaultDict[str, arrow.Arrow] = defaultdict(lambda: arrow.now().shift(seconds=-freq))

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            async with locks[func.__name__]:
                last_call_time = call_times[func.__name__]
                elapsed_time = arrow.now() - last_call_time
                if elapsed_time.total_seconds() < freq:
                    await sleep(freq - elapsed_time.total_seconds())
                result = await func(*args, **kwargs)
                call_times[func.__name__] = arrow.now()
                return result

        return wrapper

    return decorator

def threaded(func: Callable):
    """Runs the function decorated in a seperate thread"""
    async def wrapper(*args, **kwargs):
        return await to_thread(func, *args, **kwargs)
    return wrapper

def reload(module: ModuleType, reload_all, reloaded) -> None:
    # credits to melanie redbot skid bot for the function lol
    from importlib import import_module, reload

    if isinstance(module, ModuleType):
        module_name = module.__name__
    elif isinstance(module, str):
        module_name, module = module, import_module(module)
    else:
        msg = f"'module' must be either a module or str; got: {module.__class__.__name__}"
        raise TypeError(msg)

    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if check := (
            # is it a module?
            isinstance(attr, ModuleType)
            # has it already been reloaded?
            and attr.__name__ not in reloaded
            # is it a proper submodule? (or just reload all)
            and (reload_all or attr.__name__.startswith(module_name))
        ):
            reload(attr, reload_all, reloaded)

    logger.warning(f"reloading module: {module.__name__}")
    reload(module)
    reloaded.add(module_name)


def deepreload(module: ModuleType, reload_external_modules: bool = False) -> None:
    # credits to melanie redbot skid bot for the function lol
    """Recursively reload a module (in order of dependence).

    Parameters
    ----------
    module : ModuleType or str
        The module to reload.

    reload_external_modules : bool, optional

        Whether to reload all referenced modules, including external ones which
        aren't submodules of ``module``.

    """
    reload(module, reload_external_modules, set())

