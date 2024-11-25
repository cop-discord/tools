from tornado.escape import url_unescape
from urllib.parse import urlparse
from pathlib import Path
from pydantic import BaseModel
from typing import Optional
import orjson
from asyncio import ensure_future, sleep


class FileType(BaseModel):
    name: Optional[str] = None
    mime: Optional[str] = None
    extension: Optional[str] = None

class FileParser:
    def __init__(self, pop_after: bool = True):
        from .file_type_db import data
        self.pop_after = pop_after
        self.files = data

    async def clean_memory(self):
        if self.pop_after is not True:
            return
        await sleep(5)
        try:
            del self.files
        except Exception:
            pass

    async def get_extension(self, url: str) -> Optional[FileType]:
        _url = urlparse(url_unescape(url))
        _path = Path(_url.path)
        _path.name
        mime = self.files.get(_path.suffix)
        ext = self.files.suffix
        ensure_future(self.clean_memory)
        return FileType(name=_path.name, mime=mime, extension=ext)

def guess_extension(url: str) -> Optional[FileType]:
    """
    Guesses the file extension and MIME type based on the given URL.

    Args:
        url (str): The URL of the file.

    Returns:
        tuple[str, str]: A tuple containing the guessed MIME type and file extension.
    """
    from .file_type_db import data
    _url = urlparse(url_unescape(url))
    _path = Path(_url.path)
    _path.name
    mime = data.get(_path.suffix)
    ext = _path.suffix
    return FileType(name=_path.name, mime=mime, extension=ext)
