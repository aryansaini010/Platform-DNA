import json
import sys
import time
import traceback

import httpx

body = {
    "platform": "Disney+ Canada",
    "region": "Canada",
    "depth": "deep",
    "force": True,
    "enhance": True,
}
t0 = time.time()
try:
    r = httpx.post("http://127.0.0.1:8001/api/generate", json=body, timeout=780.0)
    r.raise_for_status()
    d = r.json()
except Exception:
    with open("outputs/_disney_ca_run_error.txt", "w", encoding="utf-8") as fh:
        fh.write(traceback.format_exc())
    print("GENERATE_TRANSPORT_FAIL")
    sys.exit(1)
elapsed = time.time() - t0
with open("outputs/_disney_ca_run.json", "w", encoding="utf-8") as fh:
    json.dump(d, fh, ensure_ascii=False)
st = d.get("stats", {}) or {}
print("DONE elapsed=%.1f" % elapsed)
print("errors=", d.get("errors"))
print("entry=", d.get("entry"))
print("overall=", d.get("overall"))
print("provider=", st.get("provider"), "| research_s=", st.get("research_s"),
      "| enhance_s=", st.get("enhance_s"), "| lang=", st.get("searx_lang"))
print("enhanced=", st.get("enhanced"), "| top=", st.get("enhanced_top"))
print("enhance_errors=", st.get("enhance_errors"))
