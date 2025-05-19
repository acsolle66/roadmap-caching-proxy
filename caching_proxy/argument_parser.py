import argparse


def discard_negative_int(argument: str):
    ivalue = int(argument)
    if ivalue < 0:
        raise argparse.ArgumentTypeError("can not set to negative int value")
    return ivalue


def discard_zero(argument: str):
    ivalue = int(argument)
    if ivalue == 0:
        raise argparse.ArgumentTypeError(
            f"can not set to 0, to disable cache use --eviction-policy none"
        )
    return ivalue


def set_up_arguments():
    parser = argparse.ArgumentParser(description="Start a simple caching proxy server.")

    parser.add_argument(
        "host",
        help="Proxy server host (e.g., '127.0.0.1').",
    )

    parser.add_argument(
        "port",
        type=int,
        help="Proxy server port (e.g., 8888).",
    )

    parser.add_argument(
        "origin",
        help="Origin server base URL (e.g., 'https://dummyjson.com').",
    )

    parser.add_argument(
        "-s",
        "--cache-size-limit",
        type=discard_negative_int,
        default=10,
        help="Maximum number of cached responses before the cache is cleared. Set to 0 to disable cache (default: 10). ",
    )

    parser.add_argument(
        "-i",
        "--cache-clean-interval",
        type=discard_negative_int,
        default=0,
        help="Interval (in seconds) for periodic cache cleaning. Set to 0 to disable (default: 0).",
    )

    parser.add_argument(
        "-e",
        "--eviction-policy",
        choices=["entire", "lru", "none"],
        default="lru",
        help="Cache eviction policy: 'entire' for clear the entire cache, 'lru' for least recently used, 'none' for unlimited (default: lru).",
    )

    parser.add_argument(
        "-t",
        "--hit-ttl",
        type=discard_zero,
        default=10,
        help="How many times a response can be served from cache before expiring. Set to value < 0 for unlimited. Can not be set to 0 (default: 10). ",
    )
    args = parser.parse_args()

    return args
