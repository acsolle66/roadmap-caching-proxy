# Async Caching Proxy Server

A lightweight, fully async HTTP proxy server with in-memory caching and cache eviction policies. Built with Python `asyncio` for performance and extensibility.   
This project is based on a roadmap task to build a **CLI tool** that starts a **caching proxy server**.   
https://roadmap.sh/projects/caching-server

## 🚀 Features
- Asynchronous HTTP proxying
- In-memory response caching 
- Eviction policies (LRU / full / none)
- TTL (hit-to-live) based cache invalidation
- Optional periodic cache cleanup
- CLI support for runtime configuration

### 🚫 About --clear-cache
The original spec suggested a `--clear-cache` command-line option.
This has not been implemented since the cache is in-memory — every new run starts with a clean cache.    
Instead, the server provides configurable cache eviction strategies to manage memory and avoid overflows:
- entire: Clears the full cache when full
- lru: Removes the least recently used item
- none: Keeps all cached entries (no eviction)
   
## 📦 Requirements
- Python 3.11+
- No external dependencies (pure standard library)

## ⚙️ Usage

### ▶️ Run Locally
```bash
python main.py 127.0.0.1 8888 https://dummyjson.com \
  --cache-size-limit 20 \
  --cache-clean-interval 120
  --eviction-policy none \
  --hit-ttl 10 \
```

### 🔧 CLI Arguments
| Argument | Description |
| -------- | ----------- |
| host | Proxy server host (e.g., '127.0.0.1') |
| port | Proxy server port (e.g., 8888) |
| origin | Origin server base URL (e.g., 'https://dummyjson.com')|
| --cache-size-limit | Maximum number of cached responses before the cache is cleared. Set to 0 to disable cache (default: 10) |
| --cache-clean-interval | Interval (in seconds) for periodic cache cleaning. Set to 0 to disable (default: 0) |
| --eviction-policy | ECache eviction policy: `entire` for clear the entire cache, `lru` for least recently used, `none` for unlimited (default: `lru`) |
| --hit-ttl | How many times a response can be served from cache before expiring. Set to value < 0 for unlimited. Can not be set to 0 (default: 10) |

## ⚠️ Known Limitations
1. Redirect Handling
If the origin server responds with a redirect (e.g. HTTP 301/302), the browser will follow the redirect to the new URL, bypassing the proxy server.
Why this happens: The Location header in redirect responses typically points to the original server, not the proxy address.
Planned Improvement: Redirects should ideally be handled internally by the proxy, with the final response returned to the client.

2. Browser-Side Caching
Modern browsers cache responses aggressively based on headers like Cache-Control, ETag, and Expires.
Why this matters: This may prevent requests from reaching the proxy altogether, defeating the purpose of proxy-level caching.
Suggestion: To ensure proper proxy behavior, the proxy should overwrite response headers to disable browser caching. This is currently not implemented but may be added later.

## 🧪 Testing
A few basic unit tests are currently implemented for the InMemoryResponseCache. You can run them using:  `python -m unittest discover --verbose tests/`.