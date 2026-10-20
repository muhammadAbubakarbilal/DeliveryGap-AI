"""Send one small synthetic request through the application's gateway adapter."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps/api"))
from app.ai_gateway import GatewayUnavailable, NeonGateway  # noqa: E402

try:
    answer = NeonGateway().complete("Reply with exactly the word OK.")
    if "OK" not in answer:
        raise GatewayUnavailable("Gateway responded but did not pass the synthetic check")
    print("Neon AI Gateway: synthetic inference passed")
except GatewayUnavailable as exc:
    print(str(exc))
    raise SystemExit(1) from None
