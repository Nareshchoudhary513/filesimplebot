"""
shortener.py

Generic URL-shortener integration. Most "shorten a link" APIs (e.g.
GPLinks, ShrinkMe, ShareUS, AdLinkFly-based services, and many others)
follow the same simple convention:

    GET https://<base_url>/api?api=<api_key>&url=<long_url>

    -> {"status": "success", "shortenedUrl": "https://..."}

Because the provider is fully configurable through SHORTENER_BASE_URL
and SHORTENER_API_KEY in `.env`, switching providers never requires a
code change -- just update the two environment variables.

If no shortener is configured, or the remote call fails for any reason,
the original long URL is returned unchanged so a broken shortener never
blocks a user from getting their file.
"""

from __future__ import annotations

import aiohttp

import config


async def shorten_url(long_url: str) -> str:
    """Return a shortened version of `long_url`, or `long_url` itself if
    shortening is disabled or fails."""
    if not config.SHORTENER_API_KEY or not config.SHORTENER_BASE_URL:
        return long_url

    base_url = config.SHORTENER_BASE_URL.strip().rstrip("/")
    if not base_url.startswith("http"):
        base_url = f"https://{base_url}"

    endpoint = f"{base_url}/api"
    params = {"api": config.SHORTENER_API_KEY, "url": long_url}

    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(endpoint, params=params) as response:
                if response.status != 200:
                    return long_url

                data = await response.json(content_type=None)

                # Different shortener providers use slightly different
                # JSON field names for the resulting short link, so we
                # check the common ones in order of popularity.
                short_url = (
                    data.get("shortenedUrl")
                    or data.get("short")
                    or data.get("shortUrl")
                    or data.get("url")
                )
                return short_url or long_url
    except Exception:
        # Any network/parse error silently falls back to the long URL.
        return long_url
