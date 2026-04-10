import gzip
import brotli
from flask import request


MAX_COMPRESSED_SIZE = 512 * 1024      # 512 KB
MAX_DECOMPRESSED_SIZE = 5 * 1024 * 1024  # 5 MB

def decompress_request():
    encoding = request.headers.get("Content-Encoding")

    if not encoding:
        return  # plain JSON, nothing to do

    raw_data = request.get_data()
    if len(raw_data) > MAX_COMPRESSED_SIZE:
        return {"error": "Compressed payload too large"}, 413


    if not raw_data:
        return

    try:
        if encoding == "br":
            decompressed = brotli.decompress(raw_data)
        elif encoding == "gzip":
            decompressed = gzip.decompress(raw_data)
        else:
            return  # unknown encoding → let Flask error naturally
        
        if len(decompressed) > MAX_DECOMPRESSED_SIZE:
            return {"error": "Payload too large"}, 413

    except Exception:
        return {"error": "Invalid compressed payload"}, 400

    # Replace request data with decompressed bytes
    request._cached_data = decompressed

    # Remove encoding header so Flask doesn't try to re-handle it
    request.headers.environ["HTTP_CONTENT_ENCODING"] = ""

    # IMPORTANT: fix content-length
    request.headers.environ["CONTENT_LENGTH"] = str(len(decompressed))