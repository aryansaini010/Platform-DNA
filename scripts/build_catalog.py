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
    ("Max", "United States", ["Max", "HBO Max"], ["US", "GB", "BR", "MX", "AU"]),
    ("Prime Video", "United States", ["Prime Video", "Amazon Prime Video"], ["US", "GB", "IN", "DE", "JP", "BR"]),
    ("Apple TV+", "United States", ["Apple TV+"], ["US", "GB", "CA", "AU", "IN", "DE", "FR", "JP"]),
    ("Peacock", "United States", ["Peacock"], ["US", "GB"]),
    ("Paramount+", "United States", ["Paramount+"], ["US", "GB", "CA", "AU", "DE", "BR", "MX"]),
    ("Tubi", "United States", ["Tubi"], ["US", "CA", "AU", "MX"]),
    ("The Roku Channel", "United States", ["The Roku Channel", "Roku"], ["US", "GB", "CA", "MX"]),
    ("Acorn TV (Via Amazon Prime)", "United States", ["Acorn TV"], ["US", "GB", "CA", "AU"]),
    ("AMC+", "United States", ["AMC+"], ["US", "GB", "CA", "AU"]),
    ("Shudder", "United States", ["Shudder"], ["US", "GB", "CA", "AU"]),
    ("Crunchyroll", "United States", ["Crunchyroll"], ["US", "GB", "CA", "IN", "BR", "MX", "FR", "DE", "AU", "JP"]),
    ("YouTube Premium", "Global", ["YouTube Premium"], ["US", "GB", "IN", "DE", "BR", "JP", "AU", "CA"]),
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
    ("Netflix MENA", "Middle East (MENA)", ["Netflix MENA"], ["AE", "SA", "EG", "QA", "KW", "BH", "OM"]),
    ("Shahid VIP", "Middle East (MENA)", ["Shahid VIP", "Shahid"], ["AE", "SA", "EG", "QA", "KW", "BH", "OM"]),
    ("StarzPlay", "Middle East (MENA)", ["StarzPlay"], ["AE", "SA", "EG", "QA", "KW", "BH", "OM"]),
    ("Disney+ MENA", "Middle East (MENA)", ["Disney+ MENA"], ["AE", "SA", "EG", "QA", "KW", "BH", "OM"]),
    ("Prime Video MENA", "Middle East (MENA)", ["Prime Video MENA"], ["AE", "SA", "EG", "QA", "KW", "BH", "OM"]),
    ("OSN+", "Middle East (MENA)", ["OSN+"], ["AE", "SA", "EG", "QA", "KW", "BH", "OM"]),
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
    ("YouTube", "Global", ["YouTube"], ["US", "GB", "IN", "AU", "CA"]),
    ("ZDFmediathek", "Germany", ["ZDFmediathek", "ZDF Mediathek"], ["DE"]),
    ("Zee5 Global", "Global", ["Zee5 Global"], ["IN", "US", "GB", "AE"]),
    # Global (aliases repeat the qualified Global name: a bare alias like
    # "Netflix" would equal the US platform's name and first-wins resolution
    # would hide the Global entry)
    ("Netflix Global", "Global", ["Netflix Global"], ["US", "GB", "IN", "BR", "DE", "JP"]),
    ("Prime Video Global", "Global", ["Prime Video Global"], ["US", "GB", "IN", "DE", "JP", "BR"]),
    ("Disney+ Global", "Global", ["Disney+ Global"], ["US", "GB", "CA", "IN"]),
    ("Apple TV+ Global", "Global", ["Apple TV+ Global"], ["US", "GB", "IN"]),
    # Australia: locals + BVOD + sport (aliases stay qualified — bare names
    # like "Disney+" belong to the US entries and must not be reused)
    ("Prime Video Australia", "Australia", ["Prime Video Australia"], ["AU"]),
    ("Disney+ Australia", "Australia", ["Disney+ Australia"], ["AU"]),
    ("Apple TV+ Australia", "Australia", ["Apple TV+ Australia"], ["AU"]),
    ("Paramount+ Australia", "Australia", ["Paramount+ Australia"], ["AU"]),
    ("Kayo Sports", "Australia", ["Kayo Sports", "Kayo"], ["AU"]),
    ("7plus", "Australia", ["7plus", "7+"], ["AU"]),
    ("9Now", "Australia", ["9Now"], ["AU"]),
    ("10 Play", "Australia", ["10 Play"], ["AU"]),
    ("Optus Sport", "Australia", ["Optus Sport"], ["AU"]),
    ("DocPlay", "Australia", ["DocPlay"], ["AU"]),
    ("Hayu Australia", "Australia", ["Hayu Australia", "Hayu"], ["AU"]),
    ("Fetch TV", "Australia", ["Fetch TV"], ["AU"]),
    # United States: majors + FAST + vMVPD
    ("ESPN+", "United States", ["ESPN+"], ["US"]),
    ("Discovery+ US", "United States", ["Discovery+ US"], ["US"]),
    ("Starz", "United States", ["Starz"], ["US"]),
    ("MGM+", "United States", ["MGM+"], ["US"]),
    ("BET+", "United States", ["BET+"], ["US"]),
    ("Philo", "United States", ["Philo"], ["US"]),
    ("DirecTV Stream", "United States", ["DirecTV Stream"], ["US"]),
    ("Pluto TV", "United States", ["Pluto TV"], ["US", "GB", "CA", "DE", "AU", "BR", "MX"]),
    # United Kingdom
    ("My5", "United Kingdom", ["My5", "Channel 5"], ["GB"]),
    ("STV Player", "United Kingdom", ["STV Player"], ["GB"]),
    ("Paramount+ UK", "United Kingdom", ["Paramount+ UK"], ["GB"]),
    ("Apple TV+ UK", "United Kingdom", ["Apple TV+ UK"], ["GB"]),
    # Canada
    ("Paramount+ Canada", "Canada", ["Paramount+ Canada"], ["CA"]),
    ("Apple TV+ Canada", "Canada", ["Apple TV+ Canada"], ["CA"]),
    ("Club Illico", "Canada", ["Club Illico"], ["CA"]),
    # Germany (+ DACH where served)
    ("MagentaTV", "Germany", ["MagentaTV"], ["DE"]),
    ("DAZN", "Germany", ["DAZN"], ["DE", "AT", "CH", "IT", "ES", "JP", "CA", "GB"]),
    ("Apple TV+ Germany", "Germany", ["Apple TV+ Germany"], ["DE"]),
    ("Paramount+ Germany", "Germany", ["Paramount+ Germany"], ["DE"]),
    # France
    ("Molotov TV", "France", ["Molotov TV", "Molotov"], ["FR"]),
    ("TF1+", "France", ["TF1+"], ["FR"]),
    ("M6+", "France", ["M6+", "6play"], ["FR"]),
    ("Max France", "France", ["Max France"], ["FR"]),
    ("Apple TV+ France", "France", ["Apple TV+ France"], ["FR"]),
    ("Paramount+ France", "France", ["Paramount+ France"], ["FR"]),
    # Japan
    ("AbemaTV", "Japan", ["AbemaTV", "Abema"], ["JP"]),
    ("Paravi", "Japan", ["Paravi"], ["JP"]),
    ("FOD", "Japan", ["FOD"], ["JP"]),
    ("TVer", "Japan", ["TVer"], ["JP"]),
    # South Korea
    ("Kocowa", "South Korea", ["Kocowa", "KOCOWA"], ["KR", "US"]),
    # Brazil
    ("Telecine Play", "Brazil", ["Telecine Play", "Telecine"], ["BR"]),
    # Mexico + Spanish-speaking LatAm
    ("Cinepolis Klic", "Mexico", ["Cinepolis Klic", "Cinépolis Klic"], ["MX"]),
    ("DirecTV GO", "Mexico", ["DirecTV GO", "DIRECTV GO"], ["MX", "AR", "CL", "CO", "PE"]),
    ("Flow Argentina", "Latin America", ["Flow Argentina", "Flow"], ["AR"]),
    ("Movistar Play", "Latin America", ["Movistar Play"], ["AR", "CL", "CO", "PE"]),
    # India: sport + aggregation
    ("FanCode", "India", ["FanCode"], ["IN"]),
    ("Tata Play Binge", "India", ["Tata Play Binge"], ["IN"]),
    # India: national aggregators / telco bundles / transactional
    ("Airtel Xstream Play", "India", ["Airtel Xstream Play", "Airtel Xstream"], ["IN"]),
    ("JioTV", "India", ["JioTV", "JioTV+"], ["IN"]),
    ("Vi Movies & TV", "India", ["Vi Movies & TV"], ["IN"]),
    ("Google TV India", "India", ["Google TV India", "Google TV"], ["IN"]),
    # India: national SVOD gaps
    ("Lionsgate Play India", "India", ["Lionsgate Play India"], ["IN"]),
    ("MUBI India", "India", ["MUBI India", "MUBI"], ["IN"]),
    ("EPIC ON", "India", ["EPIC ON"], ["IN"]),
    ("DocuBay", "India", ["DocuBay"], ["IN", "US", "GB"]),
    ("CuriosityStream India", "India", ["CuriosityStream India", "CuriosityStream"], ["IN"]),
    # India: language majors missing from the core block
    ("ETV Win", "India", ["ETV Win"], ["IN"]),
    ("ManoramaMAX", "India", ["ManoramaMAX", "Manorama Max"], ["IN", "US", "GB", "AE"]),
    ("Planet Marathi", "India", ["Planet Marathi"], ["IN"]),
    # India: regional services (Tamil / Bengali / Punjabi / Gujarati /
    # Malayalam / Odia / Assamese / Kannada)
    ("Tentkotta", "India", ["Tentkotta"], ["IN", "US", "GB", "SG"]),
    ("Simply South", "India", ["Simply South"], ["IN", "US", "GB", "SG", "CA", "AU"]),
    ("Addatimes", "India", ["Addatimes"], ["IN"]),
    ("Klikk", "India", ["Klikk"], ["IN"]),
    ("PTC Play", "India", ["PTC Play"], ["IN", "CA"]),
    ("Oho Gujarati", "India", ["Oho Gujarati", "Oho"], ["IN"]),
    ("Saina Play", "India", ["Saina Play"], ["IN"]),
    ("Tarang Plus", "India", ["Tarang Plus"], ["IN"]),
    ("AAO NXT", "India", ["AAO NXT"], ["IN"]),
    ("Reeldrama", "India", ["Reeldrama"], ["IN"]),
    ("NammaFlix", "India", ["NammaFlix"], ["IN"]),
    # MENA: sport + Israel + Turkey
    ("TOD", "Middle East (MENA)", ["TOD", "TOD TV"], ["AE", "SA", "QA", "KW", "BH", "OM", "EG"]),
    ("Cellcom TV", "Israel", ["Cellcom TV"], ["IL"]),
    ("BluTV", "Turkey", ["BluTV"], ["TR"]),
    ("puhutv", "Turkey", ["puhutv"], ["TR"]),
    ("Exxen", "Turkey", ["Exxen"], ["TR"]),
    ("Gain", "Turkey", ["Gain"], ["TR"]),
    ("Netflix Turkey", "Turkey", ["Netflix Turkey"], ["TR"]),
    # Southeast Asia + East Asia
    ("meWATCH", "Southeast Asia", ["meWATCH"], ["SG"]),
    ("Astro GO", "Southeast Asia", ["Astro GO", "Astro"], ["MY"]),
    ("TrueID", "Southeast Asia", ["TrueID", "True ID"], ["TH"]),
    ("CatchPlay", "Asia", ["CatchPlay", "CATCHPLAY"], ["TW", "ID"]),
    ("POPS", "Asia", ["POPS"], ["VN", "TH"]),
    ("Tapmad", "Asia", ["Tapmad"], ["PK"]),
    ("Chorki", "Asia", ["Chorki"], ["BD"]),
    # Oceania
    ("ThreeNow", "Oceania", ["ThreeNow"], ["NZ"]),
    ("Neon", "Oceania", ["Neon", "Neon NZ"], ["NZ"]),
    # Nordics: public broadcasters + TV4
    ("SVT Play", "Europe", ["SVT Play"], ["SE"]),
    ("NRK TV", "Europe", ["NRK TV", "NRK"], ["NO"]),
    ("DR TV", "Europe", ["DR TV", "DRTV"], ["DK"]),
    ("Yle Areena", "Europe", ["Yle Areena"], ["FI"]),
    ("TV4 Play", "Europe", ["TV4 Play"], ["SE"]),
    # Spain
    ("Netflix Spain", "Europe", ["Netflix Spain"], ["ES"]),
    ("Prime Video Spain", "Europe", ["Prime Video Spain"], ["ES"]),
    ("Disney+ Spain", "Europe", ["Disney+ Spain"], ["ES"]),
    ("Movistar Plus+", "Europe", ["Movistar Plus+", "Movistar+"], ["ES"]),
    ("Atresplayer", "Europe", ["Atresplayer"], ["ES"]),
    ("Mitele", "Europe", ["Mitele"], ["ES"]),
    ("RTVE Play", "Europe", ["RTVE Play"], ["ES"]),
    # Italy
    ("Netflix Italy", "Europe", ["Netflix Italy"], ["IT"]),
    ("Prime Video Italy", "Europe", ["Prime Video Italy"], ["IT"]),
    ("Disney+ Italy", "Europe", ["Disney+ Italy"], ["IT"]),
    ("RaiPlay", "Europe", ["RaiPlay", "Rai Play"], ["IT"]),
    ("Mediaset Infinity", "Europe", ["Mediaset Infinity"], ["IT"]),
    ("TIMvision", "Europe", ["TIMvision"], ["IT"]),
    ("NOW Italy", "Europe", ["NOW Italy"], ["IT"]),
    # Netherlands / Poland / Portugal / Ireland / Austria / Switzerland
    ("Netflix Netherlands", "Europe", ["Netflix Netherlands"], ["NL"]),
    ("Disney+ Netherlands", "Europe", ["Disney+ Netherlands"], ["NL"]),
    ("NPO Start", "Europe", ["NPO Start", "NPO"], ["NL"]),
    ("Netflix Poland", "Europe", ["Netflix Poland"], ["PL"]),
    ("Player.pl", "Europe", ["Player.pl"], ["PL"]),
    ("TVP VOD", "Europe", ["TVP VOD"], ["PL"]),
    ("Netflix Portugal", "Europe", ["Netflix Portugal"], ["PT"]),
    ("RTE Player", "Europe", ["RTE Player", "RTÉ Player"], ["IE"]),
    ("Netflix Ireland", "Europe", ["Netflix Ireland"], ["IE"]),
    ("ORF ON", "Europe", ["ORF ON"], ["AT"]),
    ("SRF Play", "Europe", ["SRF Play"], ["CH"]),
    # Africa
    ("Netflix South Africa", "Africa", ["Netflix South Africa"], ["ZA"]),
    ("Showmax", "Africa", ["Showmax"], ["ZA", "NG", "KE", "GH"]),
    ("DStv Stream", "Africa", ["DStv Stream"], ["ZA"]),
    ("eVOD", "Africa", ["eVOD"], ["ZA"]),
    ("iROKOtv", "Africa", ["iROKOtv"], ["NG", "GH"]),
    # United States: broadcaster BVOD + niche + sport + TVOD/FAST
    ("PBS", "United States", ["PBS", "PBS Passport"], ["US"]),
    ("The CW App", "United States", ["The CW App", "The CW"], ["US"]),
    ("Fox Nation", "United States", ["Fox Nation", "FOX Now"], ["US"]),
    ("Criterion Channel", "United States", ["Criterion Channel", "Criterion"], ["US"]),
    ("MUBI US", "United States", ["MUBI US"], ["US"]),
    ("Hallmark+", "United States", ["Hallmark+"], ["US"]),
    ("NFL+", "United States", ["NFL+"], ["US"]),
    ("NBA League Pass US", "United States", ["NBA League Pass US"], ["US"]),
    ("Fandango at Home", "United States", ["Fandango at Home"], ["US"]),
    ("Plex US", "United States", ["Plex US", "Plex"], ["US"]),
    # United Kingdom: Sky OTT + sport + FAST + nations
    ("NOW UK", "United Kingdom", ["NOW UK"], ["GB"]),
    ("TNT Sports UK", "United Kingdom", ["TNT Sports UK"], ["GB"]),
    ("Eurosport UK", "United Kingdom", ["Eurosport UK"], ["GB"]),
    ("Hayu UK", "United Kingdom", ["Hayu UK"], ["GB"]),
    ("MUBI UK", "United Kingdom", ["MUBI UK"], ["GB"]),
    ("Amazon Freevee UK", "United Kingdom", ["Amazon Freevee UK"], ["GB"]),
    ("S4C Clic", "United Kingdom", ["S4C Clic"], ["GB"]),
    ("U UK", "United Kingdom", ["U UK"], ["GB"]),
    # Canada: broadcaster BVOD (EN/FR) + sport + aggregation
    ("CTV", "Canada", ["CTV"], ["CA"]),
    ("ICI TOU.TV", "Canada", ["ICI TOU.TV"], ["CA"]),
    ("TVA+", "Canada", ["TVA+"], ["CA"]),
    ("Noovo", "Canada", ["Noovo"], ["CA"]),
    ("TSN+", "Canada", ["TSN+"], ["CA"]),
    ("Sportsnet+", "Canada", ["Sportsnet+"], ["CA"]),
    ("StackTV Canada", "Canada", ["StackTV Canada", "StackTV"], ["CA"]),
    ("Hayu Canada", "Canada", ["Hayu Canada"], ["CA"]),
    # Germany: public broadcasters + sport + SVOD
    ("ARD Mediathek", "Germany", ["ARD Mediathek"], ["DE"]),
    ("ARTE Germany", "Germany", ["ARTE Germany", "ARTE"], ["DE"]),
    ("Discovery+ Germany", "Germany", ["Discovery+ Germany"], ["DE"]),
    ("Max Germany", "Germany", ["Max Germany"], ["DE"]),
    ("MagentaSport", "Germany", ["MagentaSport"], ["DE"]),
    ("DYN Germany", "Germany", ["DYN Germany", "DYN"], ["DE"]),
    ("MUBI Germany", "Germany", ["MUBI Germany"], ["DE"]),
    ("Amazon Freevee Germany", "Germany", ["Amazon Freevee Germany"], ["DE"]),
    # France: public + BVOD + sport
    ("ARTE France", "France", ["ARTE France"], ["FR"]),
    ("RMC BFM Play", "France", ["RMC BFM Play"], ["FR"]),
    ("L'Equipe France", "France", ["L'Equipe France", "L'Équipe"], ["FR"]),
    ("beIN Sports Connect France", "France", ["beIN Sports Connect France"], ["FR"]),
    ("Eurosport France", "France", ["Eurosport France"], ["FR"]),
    ("MUBI France", "France", ["MUBI France"], ["FR"]),
    # Japan: broadcaster BVOD + premium + anime + sport + TVOD
    ("NHK+", "Japan", ["NHK+"], ["JP"]),
    ("WOWOW On Demand", "Japan", ["WOWOW On Demand", "WOWOW"], ["JP"]),
    ("DMM TV", "Japan", ["DMM TV"], ["JP"]),
    ("Telasa Japan", "Japan", ["Telasa Japan", "Telasa"], ["JP"]),
    ("d Anime Store Japan", "Japan", ["d Anime Store Japan"], ["JP"]),
    ("J Sports On Demand", "Japan", ["J Sports On Demand"], ["JP"]),
    ("SPOTV NOW Japan", "Japan", ["SPOTV NOW Japan"], ["JP"]),
    ("Rakuten TV Japan", "Japan", ["Rakuten TV Japan"], ["JP"]),
    # South Korea: broadcaster BVOD + telco + anime
    ("KBS+", "South Korea", ["KBS+"], ["KR"]),
    ("SBS Play Korea", "South Korea", ["SBS Play Korea"], ["KR"]),
    ("SPOTV NOW Korea", "South Korea", ["SPOTV NOW Korea"], ["KR"]),
    ("LG U+ Mobile TV", "South Korea", ["LG U+ Mobile TV"], ["KR"]),
    ("Laftel Korea", "South Korea", ["Laftel Korea", "Laftel"], ["KR"]),
    ("MUBI Korea", "South Korea", ["MUBI Korea"], ["KR"]),
    # Brazil: broadcaster BVOD + sport + telco + local SVOD
    ("+SBT", "Brazil", ["+SBT", "SBT"], ["BR"]),
    ("PlayPlus Brazil", "Brazil", ["PlayPlus Brazil", "PlayPlus"], ["BR"]),
    ("BandPlay", "Brazil", ["BandPlay"], ["BR"]),
    ("Premiere Brazil", "Brazil", ["Premiere Brazil", "Premiere"], ["BR"]),
    ("Combate", "Brazil", ["Combate"], ["BR"]),
    ("Vivo Play Brazil", "Brazil", ["Vivo Play Brazil", "Vivo Play"], ["BR"]),
    ("Looke Brazil", "Brazil", ["Looke Brazil", "Looke"], ["BR"]),
    # Mexico: broadcaster BVOD + telco + sport + SVOD
    ("TV Azteca App", "Mexico", ["TV Azteca App"], ["MX"]),
    ("Las Estrellas Mexico", "Mexico", ["Las Estrellas Mexico"], ["MX"]),
    ("Imagen TV Mexico", "Mexico", ["Imagen TV Mexico"], ["MX"]),
    ("izzi Go Mexico", "Mexico", ["izzi Go Mexico", "izzi Go"], ["MX"]),
    ("TUDN Mexico", "Mexico", ["TUDN Mexico", "TUDN"], ["MX"]),
    ("ESPN Mexico", "Mexico", ["ESPN Mexico"], ["MX"]),
    ("Apple TV+ Mexico", "Mexico", ["Apple TV+ Mexico"], ["MX"]),
    # MENA: Arabic SVOD + sport + nationals
    ("Watch It MENA", "Middle East (MENA)", ["Watch It MENA", "Watch It"], ["EG", "SA", "AE", "QA", "KW", "BH", "OM"]),
    ("Yango Play MENA", "Middle East (MENA)", ["Yango Play MENA", "Yango Play"], ["AE", "SA", "EG"]),
    ("beIN Connect MENA", "Middle East (MENA)", ["beIN Connect MENA"], ["AE", "SA", "EG", "QA", "KW", "BH", "OM"]),
    ("Apple TV+ MENA", "Middle East (MENA)", ["Apple TV+ MENA"], ["AE", "SA"]),
    ("ADTV", "Middle East (MENA)", ["ADTV", "Abu Dhabi TV"], ["AE"]),
    ("Dubai Now", "Middle East (MENA)", ["Dubai Now"], ["AE"]),
    # Southeast Asia: nationals + regional SVOD
    ("Disney+ Singapore", "Southeast Asia", ["Disney+ Singapore"], ["SG"]),
    ("HBO Go Asia", "Southeast Asia", ["HBO Go Asia", "HBO Go"], ["SG", "MY", "PH", "TH", "ID", "TW", "VN", "HK"]),
    ("iWantTFC Philippines", "Southeast Asia", ["iWantTFC Philippines", "iWantTFC"], ["PH"]),
    ("Vivamax Philippines", "Southeast Asia", ["Vivamax Philippines", "Vivamax"], ["PH"]),
    ("Tonton Malaysia", "Southeast Asia", ["Tonton Malaysia", "Tonton"], ["MY"]),
    ("AIS Play Thailand", "Southeast Asia", ["AIS Play Thailand", "AIS Play"], ["TH"]),
    ("Vision+ Indonesia", "Southeast Asia", ["Vision+ Indonesia", "Vision+"], ["ID"]),
    ("Viki Asia", "Southeast Asia", ["Viki Asia", "Viki"], ["SG", "MY", "PH", "TH", "ID", "TW", "VN"]),
    # New Zealand: pay-TV BVOD + nationals + sport
    ("Sky Sport Now NZ", "Oceania", ["Sky Sport Now NZ"], ["NZ"]),
    ("Sky Go NZ", "Oceania", ["Sky Go NZ"], ["NZ"]),
    ("Maori+ NZ", "Oceania", ["Maori+ NZ", "Māori+"], ["NZ"]),
    ("Netflix NZ", "Oceania", ["Netflix NZ"], ["NZ"]),
    ("Disney+ NZ", "Oceania", ["Disney+ NZ"], ["NZ"]),
    ("Prime Video NZ", "Oceania", ["Prime Video NZ"], ["NZ"]),
    ("Apple TV+ NZ", "Oceania", ["Apple TV+ NZ"], ["NZ"]),
    ("NZR+", "Oceania", ["NZR+"], ["NZ"]),
    # Nordics: JV SVOD + regional variants + nationals
    ("SkyShowtime Nordics", "Europe", ["SkyShowtime Nordics", "SkyShowtime"], ["SE", "NO", "DK", "FI"]),
    ("Max Nordics", "Europe", ["Max Nordics"], ["SE", "NO", "DK", "FI"]),
    ("Netflix Nordics", "Europe", ["Netflix Nordics"], ["SE", "NO", "DK", "FI"]),
    ("Disney+ Nordics", "Europe", ["Disney+ Nordics"], ["SE", "NO", "DK", "FI"]),
    ("TV2 Play Norway", "Europe", ["TV2 Play Norway"], ["NO"]),
    ("TV2 Play Denmark", "Europe", ["TV2 Play Denmark"], ["DK"]),
    ("MTV Katsomo Finland", "Europe", ["MTV Katsomo Finland"], ["FI"]),
    ("Ruutu Finland", "Europe", ["Ruutu Finland", "Ruutu"], ["FI"]),
    # Spain: local SVOD + JV + sport
    ("Filmin Spain", "Europe", ["Filmin Spain", "Filmin"], ["ES"]),
    ("FlixOle Spain", "Europe", ["FlixOle Spain", "FlixOlé"], ["ES"]),
    ("SkyShowtime Spain", "Europe", ["SkyShowtime Spain"], ["ES"]),
    ("Max Spain", "Europe", ["Max Spain"], ["ES"]),
    ("Apple TV+ Spain", "Europe", ["Apple TV+ Spain"], ["ES"]),
    ("Paramount+ Spain", "Europe", ["Paramount+ Spain"], ["ES"]),
    ("LaLiga+ Spain", "Europe", ["LaLiga+ Spain", "LaLiga+"], ["ES"]),
    # Italy: SVOD + pay-TV BVOD + TVOD
    ("Paramount+ Italy", "Europe", ["Paramount+ Italy"], ["IT"]),
    ("Apple TV+ Italy", "Europe", ["Apple TV+ Italy"], ["IT"]),
    ("Max Italy", "Europe", ["Max Italy"], ["IT"]),
    ("SkyShowtime Italy", "Europe", ["SkyShowtime Italy"], ["IT"]),
    ("Sky Go Italy", "Europe", ["Sky Go Italy"], ["IT"]),
    ("Chili Italy", "Europe", ["Chili Italy", "Chili"], ["IT"]),
    ("MUBI Italy", "Europe", ["MUBI Italy"], ["IT"]),
    # Netherlands: nationals + aggregator + SVOD + sport
    ("Kijk Netherlands", "Europe", ["Kijk Netherlands", "Kijk"], ["NL"]),
    ("NLZIET Netherlands", "Europe", ["NLZIET Netherlands", "NLZIET"], ["NL"]),
    ("Prime Video Netherlands", "Europe", ["Prime Video Netherlands"], ["NL"]),
    ("Apple TV+ Netherlands", "Europe", ["Apple TV+ Netherlands"], ["NL"]),
    ("Paramount+ Netherlands", "Europe", ["Paramount+ Netherlands"], ["NL"]),
    ("Max Netherlands", "Europe", ["Max Netherlands"], ["NL"]),
    ("SkyShowtime Netherlands", "Europe", ["SkyShowtime Netherlands"], ["NL"]),
    ("ESPN Netherlands", "Europe", ["ESPN Netherlands"], ["NL"]),
    # Poland: nationals + SVOD + sport
    ("Polsat Box Go Poland", "Europe", ["Polsat Box Go Poland", "Polsat Box Go"], ["PL"]),
    ("Canal+ Poland", "Europe", ["Canal+ Poland"], ["PL"]),
    ("Max Poland", "Europe", ["Max Poland"], ["PL"]),
    ("Disney+ Poland", "Europe", ["Disney+ Poland"], ["PL"]),
    ("Prime Video Poland", "Europe", ["Prime Video Poland"], ["PL"]),
    ("Apple TV+ Poland", "Europe", ["Apple TV+ Poland"], ["PL"]),
    ("SkyShowtime Poland", "Europe", ["SkyShowtime Poland"], ["PL"]),
    ("CDA Premium Poland", "Europe", ["CDA Premium Poland", "CDA Premium"], ["PL"]),
    ("Eleven Sports Poland", "Europe", ["Eleven Sports Poland"], ["PL"]),
    # Africa: national BVOD + sport + regional variants
    ("SABC+ South Africa", "Africa", ["SABC+ South Africa", "SABC+"], ["ZA"]),
    ("SuperSport Africa", "Africa", ["SuperSport Africa", "SuperSport"], ["ZA", "NG", "KE", "GH"]),
    ("Disney+ South Africa", "Africa", ["Disney+ South Africa"], ["ZA"]),
    ("Prime Video Africa", "Africa", ["Prime Video Africa"], ["ZA", "NG", "KE", "GH"]),
    ("Apple TV+ Africa", "Africa", ["Apple TV+ Africa"], ["ZA", "NG", "KE"]),
    ("NTA Nigeria", "Africa", ["NTA Nigeria"], ["NG"]),
    ("Citizen Digital Kenya", "Africa", ["Citizen Digital Kenya"], ["KE"]),
    ("TV3 Ghana", "Africa", ["TV3 Ghana"], ["GH"]),
    # Turkey: national BVOD + sport + telco + SVOD
    ("TRT Tabii Turkey", "Turkey", ["TRT Tabii Turkey", "TRT Tabii"], ["TR"]),
    ("beIN Connect Turkey", "Turkey", ["beIN Connect Turkey"], ["TR"]),
    ("S Sport+ Turkey", "Turkey", ["S Sport+ Turkey"], ["TR"]),
    ("Disney+ Turkey", "Turkey", ["Disney+ Turkey"], ["TR"]),
    ("Prime Video Turkey", "Turkey", ["Prime Video Turkey"], ["TR"]),
    ("Apple TV+ Turkey", "Turkey", ["Apple TV+ Turkey"], ["TR"]),
    ("MUBI Turkey", "Turkey", ["MUBI Turkey"], ["TR"]),
    ("TV+ Turkey", "Turkey", ["TV+ Turkey"], ["TR"]),
    # Israel: commercial + national + pay-TV + sport + SVOD
    ("Mako Israel", "Israel", ["Mako Israel", "Mako"], ["IL"]),
    ("Reshet 13 Israel", "Israel", ["Reshet 13 Israel"], ["IL"]),
    ("Kan Box Israel", "Israel", ["Kan Box Israel"], ["IL"]),
    ("HOT Play Israel", "Israel", ["HOT Play Israel"], ["IL"]),
    ("Yes+ Israel", "Israel", ["Yes+ Israel"], ["IL"]),
    ("Partner TV Israel", "Israel", ["Partner TV Israel"], ["IL"]),
    ("Netflix Israel", "Israel", ["Netflix Israel"], ["IL"]),
    ("Disney+ Israel", "Israel", ["Disney+ Israel"], ["IL"]),
    ("Sport5 Israel", "Israel", ["Sport5 Israel", "Sport5"], ["IL"]),
    # Latin America: broadcaster BVOD + sport
    ("MiTelefe Argentina", "Latin America", ["MiTelefe Argentina", "MiTelefe"], ["AR"]),
    ("eltrece TV Argentina", "Latin America", ["eltrece TV Argentina", "eltrece TV"], ["AR"]),
    ("Mega Go Chile", "Latin America", ["Mega Go Chile", "Mega Go"], ["CL"]),
    ("13GO Chile", "Latin America", ["13GO Chile"], ["CL"]),
    ("Caracol Play Colombia", "Latin America", ["Caracol Play Colombia", "Caracol Play"], ["CO"]),
    ("RCN Colombia", "Latin America", ["RCN Colombia", "Canal RCN"], ["CO"]),
    ("America TVGO Peru", "Latin America", ["America TVGO Peru"], ["PE"]),
    ("Latina Play Peru", "Latin America", ["Latina Play Peru", "Latina Play"], ["PE"]),
    ("Win Sports+ Colombia", "Latin America", ["Win Sports+ Colombia"], ["CO"]),
    ("TNT Sports Argentina", "Latin America", ["TNT Sports Argentina"], ["AR"]),
    # Asia: telco + national BVOD + local SVOD
    ("Tamasha Pakistan", "Asia", ["Tamasha Pakistan", "Tamasha"], ["PK"]),
    ("ARY Zap Pakistan", "Asia", ["ARY Zap Pakistan", "ARY Zap"], ["PK"]),
    ("Bongo Bangladesh", "Asia", ["Bongo Bangladesh", "Bongo"], ["BD"]),
    ("Toffee Bangladesh", "Asia", ["Toffee Bangladesh", "Toffee"], ["BD"]),
    ("Bioscope Bangladesh", "Asia", ["Bioscope Bangladesh", "Bioscope"], ["BD"]),
    ("friDay Video Taiwan", "Asia", ["friDay Video Taiwan", "friDay Video"], ["TW"]),
    ("MyVideo Taiwan", "Asia", ["MyVideo Taiwan", "MyVideo"], ["TW"]),
    ("FPT Play Vietnam", "Asia", ["FPT Play Vietnam", "FPT Play"], ["VN"]),
    ("VieON Vietnam", "Asia", ["VieON Vietnam", "VieON"], ["VN"]),
    ("Galaxy Play Vietnam", "Asia", ["Galaxy Play Vietnam", "Galaxy Play"], ["VN"]),
    # Zero-coverage nationals: first catalogued service for their region
    ("Kinopoisk", "Russia", ["Kinopoisk"], ["RU"]),
    ("Megogo", "Ukraine", ["Megogo"], ["UA", "KZ"]),
    ("Kyivstar TV", "Ukraine", ["Kyivstar TV"], ["UA"]),
    ("Namava", "Iran", ["Namava"], ["IR"]),
    ("Filimo", "Iran", ["Filimo"], ["IR"]),
    ("Dialog ViU", "Sri Lanka", ["Dialog ViU"], ["LK"]),
    ("NetTV", "Nepal", ["NetTV"], ["NP"]),
    ("Streamz", "Belgium", ["Streamz"], ["BE"]),
    ("GoPlay", "Belgium", ["GoPlay"], ["BE"]),
    ("VRT MAX", "Belgium", ["VRT MAX"], ["BE"]),
    ("RTBF Auvio", "Belgium", ["RTBF Auvio"], ["BE"]),
    ("ANT1+", "Greece", ["ANT1+"], ["GR"]),
    ("ERTFLIX", "Greece", ["ERTFLIX"], ["GR"]),
    ("Voyo", "Europe", ["Voyo"], ["CZ", "SK", "BG"]),
    ("RTL+ Hungary", "Europe", ["RTL+ Hungary"], ["HU"]),
    ("Voyo Romania", "Europe", ["Voyo Romania"], ["RO"]),
    ("Go3", "Europe", ["Go3"], ["LT", "LV", "EE"]),
    ("RUV", "Europe", ["RUV", "RÚV"], ["IS"]),
    ("Siminn Premium", "Europe", ["Siminn Premium", "Síminn Premium"], ["IS"]),
    ("OPTO", "Europe", ["OPTO"], ["PT"]),
    ("Virgin Media Play", "Europe", ["Virgin Media Play"], ["IE"]),
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
    ("BY", "Belarus"), ("MD", "Moldova"), ("IQ", "Iraq"), ("IR", "Iran"),
    ("JO", "Jordan"), ("LB", "Lebanon"), ("PS", "Palestine"),
    ("SY", "Syria"), ("YE", "Yemen"), ("NO2", "Norway (NO)"), ("WW", "Global"),
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

# Global availability overlays: services genuinely usable worldwide (or
# across a wide footprint) get every region they serve, instead of
# hand-listing ~190 codes per entry. Foreign services used in-region count
# as channels of that region. Sanctioned/withdrawn markets stay excluded
# (KP/RU/SY/IR/BY/TM). Sets intersected with merged codes, so a code typo
# can never trip the invariant below.
_ALL = {r["code"] for r in clean}
_EX = lambda *codes: set(codes)  # noqa: E731
_OVERLAYS: dict[str, set] = {
    "Netflix": _ALL - _EX("KP", "RU", "SY", "IR"),
    "Prime Video": _ALL - _EX("KP", "RU", "SY", "IR"),
    "YouTube": _ALL - _EX("KP", "IR", "TM"),
    "Crunchyroll": _ALL - _EX("KP", "RU", "BY", "SY", "IR"),
    "YouTube Premium": _EX(
        "US", "GB", "CA", "AU", "DE", "FR", "IN", "JP", "KR", "BR", "MX",
        "ES", "IT", "NL", "PL", "SE", "NO", "DK", "FI", "IS", "PT", "IE",
        "AT", "CH", "BE", "LU", "CZ", "SK", "HU", "GR", "TR", "IL", "ZA",
        "NG", "AR", "CL", "CO", "PE", "TW", "HK", "SG", "MY", "PH", "TH",
        "ID", "NZ", "AE", "SA", "EG", "WW"),
    "Disney+": _EX(
        "US", "GB", "CA", "AU", "DE", "FR", "IN", "IE", "AT", "CH", "IT",
        "ES", "PT", "NL", "BE", "LU", "SE", "NO", "DK", "FI", "IS", "PL",
        "CZ", "SK", "HU", "SI", "HR", "GR", "TR", "IL", "ZA", "NZ", "JP",
        "KR", "TW", "HK", "SG", "MY", "PH", "BR", "MX", "AR", "CL", "CO",
        "PE", "UY", "EC", "PA", "CR", "GT", "DO", "JM", "TT", "WW"),
    "Apple TV+": _EX(
        "US", "GB", "CA", "AU", "DE", "FR", "IN", "JP", "IE", "AT", "CH",
        "IT", "ES", "PT", "NL", "BE", "LU", "SE", "NO", "DK", "FI", "IS",
        "PL", "GR", "TR", "IL", "ZA", "MX", "BR", "AR", "CL", "CO", "PE",
        "KR", "TW", "SG", "MY", "TH", "PH", "NZ", "AE", "SA", "WW"),
    "Max": _EX("AR", "CL", "CO", "PE", "VE", "UY", "EC", "PA", "CR", "GT", "DO", "TT"),
    "Paramount+": _EX("FR", "IT", "IE", "AT", "CH", "AR", "CL", "CO", "PE"),
    "Peacock": _EX("IE", "DE", "AT"),
    "Tubi": _EX("GB"),
    "Pluto TV": _EX("FR", "IT", "ES"),
    "DAZN": _EX("US", "BR", "FR", "MX", "PT"),
    "VIX": _EX("AR", "CL", "CO", "PE", "VE", "UY", "EC", "GT", "CR", "DO"),
    "Claro Video": _EX("CO", "PE", "EC", "GT", "CR", "DO", "PR"),
    "DirecTV GO": _EX("VE", "UY", "EC", "PY", "BO", "PA", "CR", "GT", "DO", "PR", "TT", "JM", "BB"),
    "Movistar Play": _EX("VE", "UY", "EC"),
    "Viu": _EX("SA", "EG", "ZA", "QA", "KW", "BH", "OM"),
    "iQIYI": _EX("TW", "VN"),
    "WeTV": _EX("TW", "VN"),
    "SonyLIV": _EX("CA", "AU"),
    "Hoichoi": _EX("CA", "AU", "SG"),
    "Sun NXT": _EX("CA", "AU", "AE"),
    "Eros Now": _EX("CA", "AU"),
    "ShemarooMe": _EX("CA", "AU"),
    "aha Video": _EX("AU"),
    "Simply South": _EX("AE"),
    "Tentkotta": _EX("CA", "AU"),
    "ManoramaMAX": _EX("CA", "AU"),
    "Showmax": _EX("UG", "TZ", "MU"),
    "Shahid VIP": _EX("DZ", "MA", "TN", "IQ", "JO", "LB", "PS"),
    "StarzPlay": _EX("DZ", "MA", "TN", "IQ", "JO", "LB", "PS"),
    "OSN+": _EX("DZ", "MA", "TN", "IQ", "JO", "LB", "PS"),
    "TOD": _EX("DZ", "MA", "TN", "IQ", "JO"),
}
for _p in plats:
    _extra = _OVERLAYS.get(_p["name"])
    if _extra:
        _p["regions"] = sorted(set(_p["regions"]) | (_extra & _ALL))
        _p["regions_count"] = len(_p["regions"])

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
