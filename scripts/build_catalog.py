"""Generate curated platforms + full ISO regions catalogs."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "catalog"
OUT_DIR.mkdir(parents=True, exist_ok=True)

def slug(name: str) -> str:
    import re as _re
    s = "".join(c.lower() if c.isalnum() else "_" for c in name)
    s = _re.sub(r"_+", "_", s).strip("_")
    return s or "platform"

PLATFORMS: list[dict] = [
    # India core (aliases must be unique across platforms — no alias may
    # equal another platform's name, else _platform_entry first-wins hides it)
    ("JioHotstar", "India", ["JioHotstar", "Jio Hotstar"], ["IN", "GB", "CA", "SG"]),
    ("Netflix India", "India", ["Netflix India"], ["IN"]),
    ("Prime Video India", "India", ["Prime Video India", "Amazon Prime Video India"], ["IN"]),
    ("ZEE5", "India", ["ZEE5"], ["IN", "US", "GB", "AE", "SG", "CA", "AU"]),
    ("SonyLIV", "India", ["SonyLIV", "Sony LIV"], ["IN", "US", "GB", "AE", "SG"]),
    ("MX Player", "India", ["Amazon MX Player", "MX Player"], ["IN"]),
    ("Hoichoi", "India", ["Hoichoi"], ["IN", "US", "GB", "AE"]),
    ("aha Video", "India", ["aha Video", "aha"], ["IN", "US"]),
    ("Sun NXT", "India", ["Sun NXT", "SunNXT"], ["IN", "US", "GB", "SG"]),
    ("ALTBalaji", "India", ["ALTBalaji", "ALT Balaji"], ["IN"]),
    ("Eros Now", "India", ["Eros Now"], ["IN", "US", "GB"]),
    ("Voot", "India", ["Voot"], ["IN"]),
    ("JioCinema", "India", ["JioCinema", "Jio Cinema"], ["IN"]),
    ("Disney+ Hotstar", "India", ["Hotstar"], ["IN", "GB", "CA", "SG"]),
    ("Chaupal", "India", ["Chaupal"], ["IN"]),
    ("STAGE", "India", ["STAGE"], ["IN"]),
    ("Ullu", "India", ["Ullu"], ["IN"]),
    ("ShemarooMe", "India", ["Shemaroo Entertainment", "Shemaroo", "ShemarooMe"], ["IN", "US", "GB"]),
    ("Hungama Play", "India", ["Hungama Play"], ["IN"]),
    ("Discovery+ India", "India", ["Discovery+ India", "discovery+"], ["IN"]),
    # United States
    ("Netflix", "United States", ["Netflix"], ["US", "GB", "CA", "AU", "DE", "FR", "IN", "JP", "BR", "MX"]),
    ("Hulu", "United States", ["Hulu"], ["US", "JP"]),
    ("Disney+", "United States", ["Disney+"], ["US", "GB", "CA", "AU", "DE", "FR", "IN"]),
    ("Max", "United States", ["Max", "HBO Max"], ["US", "GB", "BR", "MX"]),
    ("Prime Video", "United States", ["Prime Video", "Amazon Prime Video"], ["US", "GB", "IN", "DE", "JP", "BR"]),
    ("Apple TV+", "United States", ["Apple TV+"], ["US", "GB", "CA", "AU", "IN", "DE", "FR", "JP"]),
    ("Peacock", "United States", ["Peacock"], ["US", "GB"]),
    ("Paramount+", "United States", ["Paramount+"], ["US", "GB", "CA", "AU", "DE", "BR", "MX"]),
    ("Tubi", "United States", ["Tubi"], ["US", "CA", "AU", "MX"]),
    ("The Roku Channel", "United States", ["The Roku Channel", "Roku"], ["US", "GB", "CA", "MX"]),
    ("Acorn TV (Via Amazon Prime)", "United States", ["Acorn TV"], ["US", "GB", "CA", "AU"]),
    ("AMC+", "United States", ["AMC+"], ["US", "GB", "CA", "AU"]),
    ("Shudder", "United States", ["Shudder"], ["US", "GB", "CA", "AU"]),
    ("Crunchyroll", "United States", ["Crunchyroll"], ["US", "GB", "CA", "IN", "BR", "MX", "FR", "DE"]),
    ("YouTube Premium", "Global", ["YouTube Premium"], ["US", "GB", "IN", "DE", "BR", "JP"]),
    ("YouTube TV", "United States", ["YouTube TV"], ["US"]),
    ("Fubo", "United States", ["Fubo"], ["US", "CA"]),
    ("Sling TV", "United States", ["Sling TV"], ["US"]),
    # United Kingdom
    ("BBC iPlayer", "United Kingdom", ["BBC iPlayer"], ["GB"]),
    ("Netflix UK", "United Kingdom", ["Netflix UK"], ["GB"]),
    ("Prime Video UK", "United Kingdom", ["Prime Video UK"], ["GB"]),
    ("Disney+ UK", "United Kingdom", ["Disney+ UK"], ["GB"]),
    ("Channel 4", "United Kingdom", ["Channel 4", "All 4"], ["GB"]),
    ("ITVX", "United Kingdom", ["ITVX"], ["GB"]),
    ("Sky Go", "United Kingdom", ["Sky Go", "NOW"], ["GB"]),
    ("Discovery+ UK", "United Kingdom", ["Discovery+ UK"], ["GB"]),
    ("BritBox", "United Kingdom", ["BritBox"], ["GB", "US", "CA", "AU"]),
    # Canada
    ("Netflix Canada", "Canada", ["Netflix Canada"], ["CA"]),
    ("Prime Video Canada", "Canada", ["Prime Video Canada"], ["CA"]),
    ("Disney+ Canada", "Canada", ["Disney+ Canada"], ["CA"]),
    ("Crave", "Canada", ["Crave"], ["CA"]),
    ("CBC Gem", "Canada", ["CBC Gem"], ["CA"]),
    # Australia
    ("Netflix Australia", "Australia", ["Netflix Australia"], ["AU"]),
    ("Stan", "Australia", ["Stan"], ["AU"]),
    ("BINGE", "Australia", ["BINGE"], ["AU"]),
    ("Foxtel Now", "Australia", ["Foxtel Now"], ["AU"]),
    ("ABC iview", "Australia", ["ABC iview"], ["AU"]),
    ("SBS On Demand", "Australia", ["SBS On Demand"], ["AU"]),
    # Germany
    ("Netflix Germany", "Germany", ["Netflix Germany"], ["DE"]),
    ("Prime Video Germany", "Germany", ["Prime Video Germany"], ["DE"]),
    ("Disney+ Germany", "Germany", ["Disney+ Germany"], ["DE"]),
    ("RTL+", "Germany", ["RTL+"], ["DE"]),
    ("Joyn", "Germany", ["Joyn"], ["DE", "AT", "CH"]),
    ("Sky Deutschland", "Germany", ["Sky Deutschland", "WOW"], ["DE", "AT"]),
    ("ZDF", "Germany", ["ZDF"], ["DE"]),
    # France
    ("Netflix France", "France", ["Netflix France"], ["FR"]),
    ("Prime Video France", "France", ["Prime Video France"], ["FR"]),
    ("Disney+ France", "France", ["Disney+ France"], ["FR"]),
    ("Canal+", "France", ["Canal+"], ["FR"]),
    ("OCS", "France", ["OCS"], ["FR"]),
    ("France.tv", "France", ["France.tv"], ["FR"]),
    # Japan
    ("Netflix Japan", "Japan", ["Netflix Japan"], ["JP"]),
    ("Prime Video Japan", "Japan", ["Prime Video Japan"], ["JP"]),
    ("Disney+ Japan", "Japan", ["Disney+ Japan"], ["JP"]),
    ("U-NEXT", "Japan", ["U-NEXT"], ["JP"]),
    ("dTV", "Japan", ["dTV", "Lemino"], ["JP"]),
    ("Hulu Japan", "Japan", ["Hulu Japan"], ["JP"]),
    # South Korea
    ("Netflix Korea", "South Korea", ["Netflix Korea"], ["KR"]),
    ("TVING", "South Korea", ["TVING"], ["KR"]),
    ("Wavve", "South Korea", ["Wavve", "WAVVE"], ["KR"]),
    ("Coupang Play", "South Korea", ["Coupang Play"], ["KR"]),
    ("Disney+ Korea", "South Korea", ["Disney+ Korea"], ["KR"]),
    ("Watcha", "South Korea", ["Watcha"], ["KR"]),
    # Brazil
    ("Netflix Brazil", "Brazil", ["Netflix Brazil"], ["BR"]),
    ("Prime Video Brazil", "Brazil", ["Prime Video Brazil"], ["BR"]),
    ("Disney+ Brazil", "Brazil", ["Disney+ Brazil"], ["BR"]),
    ("Globoplay", "Brazil", ["Globoplay"], ["BR", "PT", "US"]),
    ("Max Brazil", "Brazil", ["Max Brazil"], ["BR"]),
    ("Claro TV+", "Brazil", ["Claro TV+"], ["BR"]),
    # Mexico
    ("Netflix Mexico", "Mexico", ["Netflix Mexico"], ["MX"]),
    ("Prime Video Mexico", "Mexico", ["Prime Video Mexico"], ["MX"]),
    ("Disney+ Mexico", "Mexico", ["Disney+ Mexico"], ["MX"]),
    ("Max Mexico", "Mexico", ["Max Mexico"], ["MX"]),
    ("Claro Video", "Mexico", ["Claro Video"], ["MX"]),
    ("Blim", "Mexico", ["Blim", "Blim TV"], ["MX"]),
    ("VIX", "Mexico", ["VIX", "Vix+"], ["MX", "US", "BR"]),
    # MENA
    ("Netflix MENA", "Middle East (MENA)", ["Netflix MENA"], ["AE", "SA", "EG"]),
    ("Shahid VIP", "Middle East (MENA)", ["Shahid VIP", "Shahid"], ["AE", "SA", "EG"]),
    ("StarzPlay", "Middle East (MENA)", ["StarzPlay"], ["AE", "SA"]),
    ("Disney+ MENA", "Middle East (MENA)", ["Disney+ MENA"], ["AE", "SA"]),
    ("Prime Video MENA", "Middle East (MENA)", ["Prime Video MENA"], ["AE", "SA", "EG"]),
    ("OSN+", "Middle East (MENA)", ["OSN+"], ["AE", "SA", "EG"]),
    # Southeast Asia
    ("Netflix SEA", "Southeast Asia", ["Netflix SEA"], ["SG", "MY", "PH", "TH", "ID"]),
    ("Viu", "Southeast Asia", ["Viu"], ["SG", "MY", "PH", "HK", "TH", "ID", "AE"]),
    ("iQIYI", "Southeast Asia", ["iQIYI"], ["SG", "MY", "TH", "PH", "ID"]),
    ("WeTV", "Southeast Asia", ["WeTV"], ["TH", "ID", "PH", "MY", "SG"]),
    ("Disney+ Hotstar SEA", "Southeast Asia", ["Disney+ Hotstar SEA"], ["ID", "MY", "TH"]),
    ("Vidio", "Southeast Asia", ["Vidio"], ["ID"]),
    ("TVNZ+", "Oceania", ["TVNZ+"], ["NZ"]),
    ("U-Next Pacific", "Southeast Asia", ["U-Next Pacific"], ["SG"]),
    # Europe misc
    ("UKTV Play", "United Kingdom", ["UKTV Play"], ["GB"]),
    ("Viaplay", "Europe", ["Viaplay"], ["SE", "NO", "DK", "FI", "NL", "PL", "GB"]),
    ("Vice TV", "United States", ["Vice TV"], ["US", "GB"]),
    ("Videoland", "Europe", ["Videoland"], ["NL"]),
    ("Vimeo", "Global", ["Vimeo"], ["US", "GB"]),
    ("Virgin TV GO", "United Kingdom", ["Virgin TV GO"], ["GB"]),
    ("Watch HGTV", "United States", ["Watch HGTV"], ["US"]),
    ("Watch TCM", "United States", ["Watch TCM"], ["US"]),
    ("Wavve Global", "South Korea", ["Wavve Global"], ["KR", "US"]),
    ("WOW Presents Plus", "United States", ["WOW Presents Plus"], ["US", "GB"]),
    ("WWE Network", "United States", ["WWE Network"], ["US", "IN"]),
    ("Xumo Play", "United States", ["Xumo Play"], ["US", "CA"]),
    ("YouTube", "Global", ["YouTube"], ["US", "GB", "IN"]),
    ("ZDFmediathek", "Germany", ["ZDFmediathek", "ZDF Mediathek"], ["DE"]),
    ("Zee5 Global", "Global", ["Zee5 Global"], ["IN", "US", "GB", "AE"]),
    # Global (aliases repeat the qualified Global name: a bare alias like
    # "Netflix" would equal the US platform's name and first-wins resolution
    # would hide the Global entry)
    ("Netflix Global", "Global", ["Netflix Global"], ["US", "GB", "IN", "BR", "DE", "JP"]),
    ("Prime Video Global", "Global", ["Prime Video Global"], ["US", "GB", "IN", "DE", "JP", "BR"]),
    ("Disney+ Global", "Global", ["Disney+ Global"], ["US", "GB", "CA", "IN"]),
    ("Apple TV+ Global", "Global", ["Apple TV+ Global"], ["US", "GB", "IN"]),
]

seen = set()
plats = []
import sys as _sys2
for name, group, aliases, regions in PLATFORMS:
    key = slug(name)
    if key in seen:
        print(f"warning: dropping duplicate slug {key} ({name})", file=_sys2.stderr)
        continue
    seen.add(key)
    plats.append({"name": name, "slug": key, "group": group,
                  "aliases": aliases, "regions": regions,
                  "regions_count": len(regions)})

REGIONS = [
    ("IN", "India"), ("US", "United States"), ("GB", "United Kingdom"), ("CA", "Canada"),
    ("AU", "Australia"), ("DE", "Germany"), ("FR", "France"), ("JP", "Japan"),
    ("KR", "South Korea"), ("BR", "Brazil"), ("MX", "Mexico"), ("AE", "UAE"),
    ("SA", "Saudi Arabia"), ("EG", "Egypt"), ("SG", "Singapore"), ("MY", "Malaysia"),
    ("PH", "Philippines"), ("TH", "Thailand"), ("ID", "Indonesia"), ("HK", "Hong Kong"),
    ("NZ", "New Zealand"), ("ZA", "South Africa"), ("NG", "Nigeria"), ("KE", "Kenya"),
    ("TR", "Turkey"), ("RU", "Russia"), ("UA", "Ukraine"), ("PL", "Poland"),
    ("NL", "Netherlands"), ("SE", "Sweden"), ("NO", "Norway"), ("DK", "Denmark"),
    ("FI", "Finland"), ("ES", "Spain"), ("IT", "Italy"), ("PT", "Portugal"),
    ("IE", "Ireland"), ("AT", "Austria"), ("CH", "Switzerland"), ("BE", "Belgium"),
    ("GR", "Greece"), ("CZ", "Czechia"), ("HU", "Hungary"), ("RO", "Romania"),
    ("IL", "Israel"), ("QA", "Qatar"), ("KW", "Kuwait"), ("BH", "Bahrain"),
    ("OM", "Oman"), ("PK", "Pakistan"), ("BD", "Bangladesh"), ("LK", "Sri Lanka"),
    ("NP", "Nepal"), ("TW", "Taiwan"), ("VN", "Vietnam"), ("KH", "Cambodia"),
    ("LA", "Laos"), ("MM", "Myanmar"), ("AR", "Argentina"), ("CL", "Chile"),
    ("CO", "Colombia"), ("PE", "Peru"), ("VE", "Venezuela"), ("UY", "Uruguay"),
    ("PY", "Paraguay"), ("BO", "Bolivia"), ("EC", "Ecuador"), ("PA", "Panama"),
    ("CR", "Costa Rica"), ("GT", "Guatemala"), ("HN", "Honduras"), ("NI", "Nicaragua"),
    ("SV", "El Salvador"), ("DO", "Dominican Republic"), ("JM", "Jamaica"),
    ("TT", "Trinidad and Tobago"), ("BG", "Bulgaria"), ("HR", "Croatia"),
    ("RS", "Serbia"), ("SI", "Slovenia"), ("SK", "Slovakia"), ("LT", "Lithuania"),
    ("LV", "Latvia"), ("EE", "Estonia"), ("IS", "Iceland"), ("LU", "Luxembourg"),
    ("MT", "Malta"), ("CY", "Cyprus"), ("DZ", "Algeria"), ("MA", "Morocco"),
    ("TN", "Tunisia"), ("GH", "Ghana"), ("ET", "Ethiopia"), ("TZ", "Tanzania"),
    ("UG", "Uganda"), ("ZM", "Zambia"), ("ZW", "Zimbabwe"), ("MU", "Mauritius"),
    ("FJ", "Fiji"), ("PG", "Papua New Guinea"), ("KZ", "Kazakhstan"),
    ("UZ", "Uzbekistan"), ("AZ", "Azerbaijan"), ("GE", "Georgia"), ("AM", "Armenia"),
    ("BY", "Belarus"), ("MD", "Moldova"), ("NO2", "Norway (NO)"), ("WW", "Global"),
]
# normalize: drop the accidental NO2 duplicate label, keep real codes
clean = []
seen_c = set()
for code, name in REGIONS:
    if code == "NO2":
        continue
    if code in seen_c:
        continue
    seen_c.add(code)
    clean.append({"code": code, "name": name, "label": f"{name} ({code})"})

# Merge with any existing regions.json entries (e.g. extended ISO codes
# added later) so reruns never shrink the region list.
try:
    _existing = json.loads((OUT_DIR / "regions.json").read_text(encoding="utf-8"))
    _have = {r["code"] for r in clean}
    for r in _existing:
        if r.get("code") and r["code"] not in _have:
            clean.append({"code": r["code"], "name": r.get("name", r["code"]),
                          "label": r.get("label", f"{r.get('name', r['code'])} ({r['code']})")})
            _have.add(r["code"])
except Exception:
    pass

# INVARIANT (fail loud, never silent): every platform belongs to ≥1 region,
# every region code exists, no duplicate slugs/names, and no alias equals
# another platform's name (first-wins lookup would hide that platform).
import sys as _sys

_errors = []
_seen_slugs: set[str] = set()
_seen_names: set[str] = set()
_region_codes = {r["code"] for r in clean}
_name_lc = {p["name"].lower(): p["name"] for p in plats}
for _p in plats:
    if _p["slug"] in _seen_slugs:
        _errors.append(f"duplicate slug: {_p['slug']}")
    _seen_slugs.add(_p["slug"])
    if _p["name"] in _seen_names:
        _errors.append(f"duplicate name: {_p['name']}")
    _seen_names.add(_p["name"])
    if not _p.get("regions"):
        _errors.append(f"platform with no region (impossible): {_p['name']}")
    for _c in _p.get("regions", []):
        if _c not in _region_codes:
            _errors.append(f"dangling region code {_c} on {_p['name']}")
    for _a in _p.get("aliases", []) or []:
        _hit = _name_lc.get((_a or "").lower())
        if _hit and _hit != _p["name"]:
            _errors.append(f"alias collision: alias '{_a}' on {_p['name']} equals platform '{_hit}'")
if _errors:
    print("CATALOG INVARIANT VIOLATIONS:", file=_sys.stderr)
    for _e in _errors:
        print(f"  - {_e}", file=_sys.stderr)
    _sys.exit(1)

(OUT_DIR / "platforms.json").write_text(json.dumps(plats, indent=1, ensure_ascii=False), encoding="utf-8")
(OUT_DIR / "regions.json").write_text(json.dumps(clean, indent=1, ensure_ascii=False), encoding="utf-8")
print(f"wrote {len(plats)} platforms, {len(clean)} regions -> {OUT_DIR} (invariant holds)")
