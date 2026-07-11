from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ["TAKEFLOW_UPDATE_MANIFEST_URL"] = ""

from fastapi.testclient import TestClient

from app import settings
import app.main as main_module
from app.segmind_client import SegmindClient


def main() -> int:
    previous_env_path = main_module.ENV_PATH
    previous_balance = main_module.segmind_balance_context
    previous_key = settings.get_segmind_api_key()
    previous_base = settings.get_segmind_api_base()

    try:
        with tempfile.TemporaryDirectory(prefix="takeflow_runtime_api_") as temp_dir:
            env_path = Path(temp_dir) / ".env"
            main_module.ENV_PATH = env_path
            main_module.segmind_balance_context = lambda: {
                "segmind_balance_label": "Balance",
                "segmind_balance_value": "Unavailable",
                "segmind_balance_hint": "Test balance disabled.",
                "segmind_balance_available": False,
            }

            response = TestClient(main_module.app).post(
                "/update-api-settings",
                data={
                    "segmind_api_key": "runtime-route-test-key",
                    "segmind_api_base": "https://runtime-route.example/",
                },
            )
            client = SegmindClient()
            saved = env_path.read_text(encoding="utf-8")

            checks = {
                "route_ok": response.status_code == 200,
                "success_message_localizable": 'data-flash-message="flash_api_settings_saved"' in response.text,
                "runtime_key_applied": client.api_key == "runtime-route-test-key",
                "runtime_base_applied": client.api_base == "https://runtime-route.example",
                "env_written": "SEGMIND_API_KEY=runtime-route-test-key" in saved
                and "SEGMIND_API_BASE=https://runtime-route.example" in saved,
                "default_model_not_written": "SEGMIND_MODEL=" not in saved,
            }
    finally:
        main_module.ENV_PATH = previous_env_path
        main_module.segmind_balance_context = previous_balance
        settings.apply_runtime_segmind_settings(api_key=previous_key, api_base=previous_base)
        if not previous_key:
            os.environ.pop("SEGMIND_API_KEY", None)

    for name, ok in checks.items():
        print(f"{name}={ok}")
    print("new_paid_submit_started=False")
    if all(checks.values()):
        print("RESULT=RUNTIME_API_SETTINGS_OK")
        return 0
    print("RESULT=RUNTIME_API_SETTINGS_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
