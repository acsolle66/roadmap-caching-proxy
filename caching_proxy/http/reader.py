from abc import ABC, abstractmethod
from asyncio import StreamReader
from enum import Enum

from utils.logger import get_logger

logger = get_logger(__name__)

CRLF = b"\r\n"


class BodyReaderType(Enum):
    NOREAD = 1
    CHUNKED = 2
    CONTENT_LENGTH = 3
    # TODO: Case where content length is missing or malformed, and handle Connection: close


class HTTPReaderStrategy(ABC):
    @abstractmethod
    async def read_headers(self) -> bytes:
        pass

    @abstractmethod
    async def read_body(self) -> bytes:
        pass


class AsyncHTTPStreamReader(HTTPReaderStrategy):
    def __init__(self, reader: StreamReader) -> None:
        self.reader = reader
        self._body_reader_type = BodyReaderType.NOREAD
        self._content_length = 0

    @property
    def body_reader_type(self) -> BodyReaderType:
        logger.debug(f"Setting body_reader_type to {type(self._body_reader_type)}")
        return self._body_reader_type

    @body_reader_type.setter
    def body_reader_type(self, type: BodyReaderType) -> None:
        self._body_reader_type = type

    @property
    def content_length(self) -> int:
        return self._content_length

    @content_length.setter
    def content_length(self, length: int) -> None:
        logger.debug(f"Setting content_length to {length}")
        self._content_length = length

    async def read_headers(self) -> bytes:
        logger.debug("Starting to read headers from stream")
        END_OF_HEADER = CRLF + CRLF
        raw_headers = await self.reader.readuntil(END_OF_HEADER)
        logger.debug(f"Read headers: \n{raw_headers.decode(errors='replace').strip()}")
        return raw_headers

    async def read_body(self) -> bytes:
        logger.debug(f"Reading body with reader type: {self.body_reader_type}")
        match self.body_reader_type:
            case BodyReaderType.NOREAD:
                logger.debug("No body to read (NOREAD)")
                return b""
            case BodyReaderType.CHUNKED:
                logger.debug("Reading chunked body")
                body = await self._read_chunked()
                logger.debug(f"Finished reading chunked body of size {len(body)} bytes")
                return body
            case BodyReaderType.CONTENT_LENGTH:
                logger.debug(f"Reading body with content_length: {self.content_length}")
                body = await self._read_exactly()
                logger.debug(f"Finished reading body of size {len(body)} bytes")
                return body
            case _:
                logger.warning("Unknown body reader type, returning empty body")
                return b""

    async def _read_chunked(self) -> bytes:
        body = b""
        while True:
            size_line = await self.reader.readuntil(CRLF)
            size = int(
                size_line.strip().split(b";")[0], 16
            )  # Strip and ignore optional chunk extensions
            logger.debug(f"Chunk size: {size} bytes")
            if size == 0:
                logger.debug("Reached last chunk (size 0)")
                await self.reader.readuntil(CRLF)  # Discard trailer delimiter
                # Trailer headers are ignored for now
                break
            chunk = await self.reader.readexactly(size)
            await self.reader.readuntil(CRLF)  # Discard chunk delimiter
            body += chunk
        return body

    async def _read_exactly(self) -> bytes:
        logger.debug(f"Reading exactly {self.content_length} bytes from stream")
        return await self.reader.readexactly(self.content_length)
