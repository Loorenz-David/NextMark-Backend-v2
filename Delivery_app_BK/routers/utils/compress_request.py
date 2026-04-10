import gzip
import brotli
from flask import request

MIN_SIZE = 1024  # bytes


def compress_payload(response):
    # ---------- Guards ----------
    if response.headers.get("X-No-Compress"):
        return response

    if response.content_type != "application/json":
        return response

    if response.status_code != 200:
        return response

    accept_encoding = request.headers.get("Accept-Encoding", "")
    if not accept_encoding:
        return response

    data = response.get_data()

    if not data or len(data) < MIN_SIZE:
        return response

    # ---------- Brotli (preferred) ----------
    if "br" in accept_encoding:
        try:
            compressed = brotli.compress(
                data,
                quality=5  # good balance for APIs
            )
            response.set_data(compressed)
            response.headers["Content-Encoding"] = "br"
            response.headers["Content-Length"] = len(compressed)
            response.headers["Vary"] = "Accept-Encoding"
            return response
        except Exception:
            pass  # fall through to gzip

    # ---------- Gzip fallback ----------
    if "gzip" in accept_encoding:
        compressed = gzip.compress(data)
        response.set_data(compressed)
        response.headers["Content-Encoding"] = "gzip"
        response.headers["Content-Length"] = len(compressed)
        response.headers["Vary"] = "Accept-Encoding"
        return response

    return response