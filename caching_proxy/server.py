import asyncio
from asyncio import StreamReader, StreamWriter

from utils.logger import get_logger

from .http.message import (
    DechunkedAsyncStreamMessageBuilder,
    HTTPRequest,
    HTTPRequestMethod,
    HTTPResponse,
    RawMessageBuilder,
)

logger = get_logger(__name__)


class CachingProxyServer:
    def __init__(self, host, port, origin_url, storage) -> None:
        self.host = host
        self.port = port
        self.origin_url = origin_url
        self.storage = storage

    async def run(self):
        server = await asyncio.start_server(self._handle_request, self.host, self.port)

        async with server:
            logger.info(f"Serving on address {self.host}:{self.port}")
            await server.serve_forever()

    async def _handle_request(
        self,
        client_reader: StreamReader,
        client_writer: StreamWriter,
    ) -> None:
        try:
            client_address = client_writer.get_extra_info("peername")
            logger.info(f"New connection from {client_address}")

            client_message_builder = DechunkedAsyncStreamMessageBuilder(client_reader)

            origin_host, origin_port = self._parse_origin_host_port()

            request = await client_message_builder.build_request()
            logger.info(
                f"Received request: {request.request_line} from {client_address}"
            )

            request.replace_header("host", [origin_host + ":" + str(origin_port)])

            origin_reader, origin_writer = await self._open_connection_to_origin(
                origin_host, origin_port
            )

            origini_message_builder = DechunkedAsyncStreamMessageBuilder(origin_reader)

            if request.method != HTTPRequestMethod.GET.value:
                logger.info("Request method is not GET, forwarding without caching.")
                await self._write_request_to_origin(origin_writer, request)
                response = await origini_message_builder.build_response()
                response.set_header("x_cached_by_proxy", ["MISS"])
                await self._write_response_to_client_and_close(client_writer, response)
                return

            cache_key = request.request_line
            if self.storage.has_cached_response(cache_key):
                logger.info(f"Cache HIT for key: {cache_key}")
                raw_message_builder = RawMessageBuilder()
                cached_response = self.storage.get_cached_response(cache_key)
                response = await raw_message_builder.build_response(
                    cached_response["header"], cached_response["body"]
                )
                response.set_header("x_cached_by_proxy", ["HIT"])
                await self._write_response_to_client_and_close(client_writer, response)
                return
            else:
                logger.info(f"Cache MISS for key: {cache_key}, fetching from origin.")
                await self._write_request_to_origin(origin_writer, request)
                response = await origini_message_builder.build_response()
                cachable_response = {
                    "header": response.headers.raw,
                    "body": response.body.raw,
                }
                self.storage.cache_response(cache_key, cachable_response)
                response.set_header("x_cached_by_proxy", ["MISS"])
                await self._write_response_to_client_and_close(client_writer, response)

        except Exception as e:
            logger.error(f"Error handling request: {e}", exc_info=True)
            client_writer.close()
            await client_writer.wait_closed()

    def _parse_origin_host_port(self) -> tuple[str, int]:
        address = self.origin_url.split("//")
        host = address[1][:-1] if address[1].endswith("/") else address[1]
        port = 443 if address[0].startswith("https") else 80
        logger.debug(f"Parsed origin host: {host}, port: {port}")
        return host, port

    async def _open_connection_to_origin(
        self, origin_host: str, origin_port: int
    ) -> tuple[StreamReader, StreamWriter]:
        ssl = True if origin_port == 443 else False
        logger.debug(
            f"Opening connection to origin {origin_host}:{origin_port} ssl={ssl}"
        )
        return await asyncio.open_connection(origin_host, origin_port, ssl=ssl)

    async def _write_request_to_origin(
        self, writer: StreamWriter, request: HTTPRequest
    ) -> None:
        logger.debug(f"Forwarding request to origin: {request.request_line}")
        writer.write(request.raw)
        await writer.drain()

    async def _write_response_to_client_and_close(
        self, writer: StreamWriter, response: HTTPResponse
    ) -> None:
        logger.debug("Sending response back to client")
        writer.write(response.raw)
        await writer.drain()
        writer.close()
        await writer.wait_closed()
        logger.debug("Closed client connection")
