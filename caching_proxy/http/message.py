import re
from asyncio import StreamReader
from enum import Enum

from utils.logger import get_logger

from .reader import AsyncHTTPStreamReader, BodyReaderType

logger = get_logger(__name__)


class HTTPRequestMethod(Enum):
    GET = "GET"


class HTTPHeaders:
    def __init__(self, raw_header: bytes = b"") -> None:
        self.raw = raw_header
        self.start_line = ""
        self.headers = self._parse_raw_headers()

    def get_header(self, name: str) -> list[str] | None:
        return self.headers.get(self._normalize_header(name))

    def insert(self, name: str, values: list[str]) -> None:
        normalized_name = self._normalize_header(name)
        if self.headers.get(normalized_name) is None:
            self.headers[normalized_name] = values
        else:
            for value in values:
                self.headers[normalized_name].append(value)
        self._update_raw_bytes()

    def replace(self, name: str, values: list[str]) -> bool:
        normalized_name = self._normalize_header(name)
        if self.headers.get(normalized_name) is not None:
            self.headers[normalized_name] = values
            self._update_raw_bytes()
            return True
        else:
            return False

    def delete(self, name: str) -> bool:
        try:
            self.headers.pop(self._normalize_header(name))
            self._update_raw_bytes()
            return True
        except KeyError:
            return False

    @property
    def names(self) -> list[str]:
        return list(self.headers.keys())

    def __str__(self):
        return self.raw.decode(errors="replace")

    def _normalize_header(self, repr_txt: str) -> str:
        words = repr_txt.strip().split("-")
        words = [word.lower() for word in words]
        return "_".join(words)

    def _format_header(self, norm_txt: str) -> str:
        words = norm_txt.split("_")
        words = [word.capitalize() for word in words]
        return "-".join(words)

    def _decode_header_bytes(self, raw: bytes) -> str:
        return raw.decode("utf-8", errors="replace")

    def _split_header_lines(self, decoded: str) -> list[str]:
        return decoded.replace("\r\n", "\n").split("\n")

    def _unfold_lines(self, lines: list[str]) -> list[str]:
        unfolded: list[str] = []
        for line in lines:
            if line.strip() == "":
                continue
            if line.startswith(" ") or line.startswith("\t"):
                unfolded[-1] += " " + line.strip()
            else:
                unfolded.append(line)
        return unfolded

    def _parse_header_lines(self, lines: list[str]) -> tuple[str, dict[str, list[str]]]:
        start_line = lines[0]
        headers: dict[str, list[str]] = {}
        for line in lines[1:]:
            pattern = r"([\w\-]+):\s*(.*)"
            pattern_match = re.search(pattern, line)
            if pattern_match:
                name, value = pattern_match.groups()
                name = self._normalize_header(name)
                value = value.strip()
                headers.setdefault(name, []).append(value)
        return start_line, headers

    def _parse_raw_headers(self) -> dict[str, list[str]]:
        decoded = self._decode_header_bytes(self.raw)
        lines = self._split_header_lines(decoded)
        unfolded = self._unfold_lines(lines)
        self.start_line, headers = self._parse_header_lines(unfolded)
        return headers

    def _update_raw_bytes(self):
        headers = [self.start_line + "\r\n"]
        for name, values in self.headers.items():
            for value in values:
                headers.append(self._format_header(name) + ": " + value + "\r\n")
        headers.append("\r\n")
        headers_raw = [header.encode("utf-8") for header in headers]
        self.raw = b"".join(headers_raw)


class HTTPBody:
    def __init__(self, raw_body: bytes = b""):
        self.raw = raw_body

    @property
    def size(self) -> int:
        return len(self.raw)

    def __str__(self):
        return self.raw.decode(errors="replace")


class HTTPMessage:
    def __init__(self, headers: HTTPHeaders, body: HTTPBody):
        self.headers = headers

        self.body = body

    def replace_header(self, name: str, value: list[str]) -> None:
        self.headers.replace(name, value)

    def set_header(self, name: str, value: list[str]) -> None:
        self.headers.insert(name, value)

    @property
    def raw(self):
        return self.headers.raw + self.body.raw

    def __str__(self):
        return self.raw.decode(errors="replace")


class HTTPRequest(HTTPMessage):
    @property
    def request_line(self):
        return self.headers.start_line

    @property
    def method(self):
        return self.request_line.split(" ")[0].upper()

    @property
    def path(self):
        return self.request_line.split(" ")[1]

    @property
    def address(self):
        return self.headers.get_header("host")


class HTTPResponse(HTTPMessage):
    @property
    def response_line(self):
        return self.headers.start_line


class DechunkedAsyncStreamMessageBuilder:
    def __init__(self, reader: StreamReader) -> None:
        self.http_reader = AsyncHTTPStreamReader(reader)

    async def build_request(self):
        logger.debug("Building HTTP request from stream")
        headers = await self._build_headers()
        body = await self._build_body(headers)
        logger.debug("Built HTTP request successfully")
        return HTTPRequest(headers, body)

    async def build_response(self):
        logger.debug("Building HTTP response from stream")
        headers = await self._build_headers()
        body = await self._build_body(headers)
        logger.debug("Built HTTP response successfully")
        return HTTPResponse(headers, body)

    async def _build_headers(self):
        logger.debug("Reading headers")
        raw_headers = await self.http_reader.read_headers()
        logger.debug(f"Headers read ({len(raw_headers)} bytes)")
        return HTTPHeaders(raw_headers)

    async def _build_body(self, headers: HTTPHeaders):
        logger.debug("Determining body read strategy")
        body = HTTPBody()

        if self._expect_chunked_body(headers):
            logger.debug("Expecting chunked body")
            self.http_reader.body_reader_type = BodyReaderType.CHUNKED
            body.raw = await self.http_reader.read_body()
            self._dechunk_body(headers, body)
            logger.debug("Dechunked body processed")
            return body

        elif content_length := self._expected_body_size(headers):
            logger.debug(f"Expecting body of content length: {content_length}")
            self.http_reader.body_reader_type = BodyReaderType.CONTENT_LENGTH
            self.http_reader.content_length = content_length
            body.raw = await self.http_reader.read_body()
            logger.debug(f"Read body of size: {len(body.raw)} bytes")
            return body

        logger.debug("No body expected")
        return body

    def _expected_body_size(self, headers: HTTPHeaders):
        content_length_header = headers.get_header("content_length")
        logger.debug(f"Content-length header found: {content_length_header}")
        return 0 if content_length_header is None else int(content_length_header[0])

    def _expect_chunked_body(self, headers: HTTPHeaders) -> bool:
        chunked_header = headers.get_header("transfer_encoding")
        logger.debug(f"Transfer-Encoding header chunked: {chunked_header}")
        return chunked_header is not None and chunked_header[0] == "chunked"

    def _dechunk_body(self, headers: HTTPHeaders, body: HTTPBody):
        body_size = str(body.size)
        logger.debug(f"Dechunking body, new size: {body_size}")
        if headers.get_header("transfer_encoding"):
            headers.delete("transfer_encoding")
            if headers.get_header("content_length"):
                headers.replace("content_length", [body_size])
            else:
                headers.insert("content_length", [body_size])


class RawMessageBuilder:
    async def build_request(self, raw_headers: bytes, raw_body: bytes):
        headers = HTTPHeaders(raw_headers)
        body = HTTPBody(raw_body)
        return HTTPRequest(headers, body)

    async def build_response(self, raw_headers: bytes, raw_body: bytes):
        headers = HTTPHeaders(raw_headers)
        body = HTTPBody(raw_body)
        return HTTPResponse(headers, body)
