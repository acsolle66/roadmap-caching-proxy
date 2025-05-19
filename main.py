import asyncio

from caching_proxy.argument_parser import set_up_arguments
from caching_proxy.cache.in_memory import InMemoryResponseCache
from caching_proxy.server import CachingProxyServer
from utils.logger import get_logger

logger = get_logger(__name__)


async def periodic_cache_cleaner(storage: InMemoryResponseCache, interval: int = 60):
    logger.info(f"Periodic cache cleaner started with interval: {interval}s")
    while True:
        await asyncio.sleep(interval)
        if storage.get_cache_size() == 0:
            logger.info("Periodic cache cleaner: nothing to clear")
        else:
            storage.evict()
            logger.info("Periodic cache cleaner: cache cleared")


async def main():
    logger.debug("Logging level: DEBUG")

    args = set_up_arguments()

    host = args.host
    port = args.port
    origin_url = args.origin

    cache_size_limit = args.cache_size_limit
    cache_clean_interval = args.cache_clean_interval
    eviction_policy = args.eviction_policy
    hit_ttl = args.hit_ttl

    logger.info(
        f"Initializing cache with cache size limit: {cache_size_limit}, eviction policy: {eviction_policy}, hit TTL: {hit_ttl}"
    )
    cache = InMemoryResponseCache(cache_size_limit, eviction_policy, hit_ttl)

    logger.info(f"Starting proxy server on {host}:{port} forwarding to {origin_url}")
    server = CachingProxyServer(host, port, origin_url, cache)

    if cache_clean_interval == 0:
        logger.info("Periodic cache cleaner is disabled")
        await server.run()
    else:
        async with asyncio.TaskGroup() as tg:
            run_server = tg.create_task(server.run())
            clear_cache = tg.create_task(
                periodic_cache_cleaner(cache, cache_clean_interval)
            )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Thanks for using me. Bye")
    except Exception as e:
        logger.error(f"Something bad happened: {e}", exc_info=True)
