from collections import OrderedDict
from typing import Any

from utils.logger import get_logger

logger = get_logger(__name__)


class InMemoryResponseCache:

    def __init__(
        self,
        cache_size_limit: int = 10,
        eviction_policy: str = "lru",
        hit_ttl: int = 10,
    ):
        self._cache = OrderedDict()
        self.cache_size_limit = cache_size_limit
        self.eviction_policy = eviction_policy
        self.hit_ttl = hit_ttl

    def has_cached_response(self, key: str) -> bool:
        cached_value = self._cache.get(key)
        if cached_value is None:
            logger.debug(f"Cache miss (no entry) for key: {key}")
            return False
        if cached_value["HIT_TTL"] == 0:
            logger.info(f"Cache expired for key: {key}, removing from cache")
            self.remove_from_cache(key)
            return False
        logger.debug(f"Cache hit for key: {key} with HIT_TTL={cached_value['HIT_TTL']}")
        return True

    def remove_from_cache(self, key: str):
        logger.debug(f"Removing key from cache: {key}")
        self._cache.pop(key)

    def cache_response(self, key: str, response: Any):

        if self.cache_size_limit == 0:
            logger.debug(f"Cache size limit set to 0 (response will not be cached)")
            return

        if len(self._cache) >= self.cache_size_limit:
            logger.info("Cache size limit reached; applying eviction policy")
            self.evict()

        logger.info(f"Caching response for key: {key} with HIT_TTL={self.hit_ttl}")
        self._cache[key] = {"response": response, "HIT_TTL": self.hit_ttl}

    def get_cached_response(self, key: str):
        cached_value = self._cache[key]
        cached_value["HIT_TTL"] -= 1
        logger.debug(f"Decremented HIT_TTL for key: {key} to {cached_value['HIT_TTL']}")
        self._cache.move_to_end(key)

        return cached_value["response"]

    def evict(self):
        match self.eviction_policy:
            case "entire":
                logger.debug("Eviction policy: entire. Clearing entire cache.")
                self._cache.clear()
            case "lru":
                removed_key, _ = self._cache.popitem(last=False)
                logger.debug(f"Eviction policy: lru. Removed: {removed_key}")
            case "none":
                logger.warning(f"Eviction policy is 'none'; skipping cache update")

    def get_cache_size(self) -> int:
        return len(self._cache)
