"""Explicit, opt-in Meta API smoke test using synthetic image bytes."""

import base64
import os

from app.services.meta_api import MetaAPIError, MetaModelClient


if os.environ.get("RUN_META_LIVE_TEST") != "1":
    raise SystemExit("Set RUN_META_LIVE_TEST=1 to explicitly enable the live Meta API test")

# 1x1 transparent PNG; this is synthetic and contains no identity data.
synthetic_png = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)

try:
    result = MetaModelClient().extract_document_fields(synthetic_png, "image/png", "passport")
except MetaAPIError:
    print("Meta API smoke test failed")
else:
    print(f"Meta API smoke test completed; confidence_present={result.confidence is not None}")
