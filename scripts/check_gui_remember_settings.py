from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from scripts.frontend_static_utils import read_static_js

APP_JS = read_static_js(PROJECT_ROOT)

from fastapi.testclient import TestClient
from app.main import app


def main() -> int:
    print("=== GUI remember settings check ===")

    client = TestClient(app)
    response = client.get("/")

    text = response.text
    client_text = text + "\n" + APP_JS

    print("index_status_code=", response.status_code, sep="")
    print("contains_storage_key=", "seedance_gui_form_preferences_v1" in client_text, sep="")
    print("contains_model_field=", '"model"' in text, sep="")
    print("contains_duration_field=", '"duration"' in text, sep="")
    print("contains_resolution_field=", '"resolution"' in text, sep="")
    print("contains_aspect_ratio_field=", '"aspect_ratio"' in text, sep="")
    print("contains_generate_audio_field=", '"generate_audio"' in text, sep="")
    print("contains_return_last_frame_field=", '"return_last_frame"' in text, sep="")
    print("contains_localstorage_set=", "localStorage.setItem" in client_text, sep="")
    print("contains_localstorage_get=", "localStorage.getItem" in client_text, sep="")

    ok = (
        response.status_code == 200
        and "seedance_gui_form_preferences_v1" in client_text
        and '"model"' in text
        and '"duration"' in text
        and '"resolution"' in text
        and '"aspect_ratio"' in text
        and "localStorage.setItem" in client_text
        and "localStorage.getItem" in client_text
    )

    if ok:
        print("RESULT=GUI_REMEMBER_SETTINGS_OK")
        return 0

    print("RESULT=GUI_REMEMBER_SETTINGS_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
