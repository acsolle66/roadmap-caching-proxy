import random
import unittest
from ctypes.util import test

from caching_proxy.cache.in_memory import InMemoryResponseCache


class TestInMemoryResponseCache(unittest.TestCase):
    def setUp(self):
        self.cache = InMemoryResponseCache()
        self.test_key = "test_key"
        self.test_response = "test_response"

    def test_has_cached_response_return_false_when_empty(self):
        self.assertFalse(self.cache.has_cached_response(self.test_key))

    def test_has_cached_response_return_true_when_not_empty(self):
        self.cache.cache_response(self.test_key, self.test_response)
        self.assertTrue(self.cache.has_cached_response(self.test_key))

    def test_get_cached_response_returns_correct_response(self):
        self.cache.cache_response(self.test_key, self.test_response)
        self.assertEqual(
            self.test_response, self.cache.get_cached_response(self.test_key)
        )

    def test_hit_ttl_decremetns_correctly_after_access(self):
        self.cache.cache_response(self.test_key, self.test_response)
        self.assertEqual(
            self.cache.hit_ttl, self.cache._cache[self.test_key]["HIT_TTL"]
        )

    def test_cache_entry_expires_after_hit_ttl_reaches_zero(self):
        random_hit_ttl = random.randint(1, 10)
        self.cache.hit_ttl = random_hit_ttl
        self.cache.cache_response(self.test_key, self.test_response)
        self.assertTrue(self.cache.has_cached_response(self.test_key))
        for access in range(random_hit_ttl):
            self.cache.get_cached_response(self.test_key)
        self.assertFalse(self.cache.has_cached_response(self.test_key))

    def test_get_cache_size(self):
        self.assertEqual(self.cache.get_cache_size(), 0)
        self.cache.cache_response(self.test_key, self.test_response)
        self.assertEqual(self.cache.get_cache_size(), 1)

    def test_remove_from_cache(self):
        self.assertEqual(self.cache.get_cache_size(), 0)
        self.cache.cache_response(self.test_key, self.test_response)
        self.assertEqual(self.cache.get_cache_size(), 1)
        self.cache.remove_from_cache(self.test_key)
        self.assertEqual(self.cache.get_cache_size(), 0)

    def test_enitre_eviction_policy_after_cache_size_limit_reached(self):
        cache_size_limit = self.cache.cache_size_limit
        self.cache.eviction_policy = "entire"
        for i in range(cache_size_limit):
            self.cache.cache_response(self.test_key + str(i), self.test_response)
        self.assertEqual(self.cache.get_cache_size(), cache_size_limit)

        self.cache.cache_response(self.test_key, self.test_response)
        self.assertEqual(self.cache.get_cache_size(), 1)

    def test_lru_eviction_policy_after_cache_size_limit_reached(self):
        cache_size_limit = self.cache.cache_size_limit
        for i in range(cache_size_limit):
            self.cache.cache_response(self.test_key + str(i), self.test_response)
        self.assertEqual(self.cache.get_cache_size(), cache_size_limit)

        self.cache.cache_response(self.test_key, self.test_response)
        self.assertEqual(self.cache.get_cache_size(), cache_size_limit)

    def test_none_eviction_policy_after_cache_size_limit_reached(self):
        cache_size_limit = self.cache.cache_size_limit
        self.cache.eviction_policy = "none"
        for i in range(cache_size_limit):
            self.cache.cache_response(self.test_key + str(i), self.test_response)
        self.assertEqual(self.cache.get_cache_size(), cache_size_limit)

        self.cache.cache_response(self.test_key, self.test_response)
        self.assertEqual(self.cache.get_cache_size(), cache_size_limit + 1)


if __name__ == "__main__":
    unittest.main()
