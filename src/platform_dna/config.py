"""Slot checklist, query templates, scoring rubric (plan §4 Steps 1 & 5)."""
from __future__ import annotations

# slot -> (report section, best sources hint)
SLOTS: dict[str, tuple[str, str]] = {
    "content_hours": ("header", "Platform newsroom, Wikipedia, trade press"),
    "language_count": ("header", "Platform help pages, Wikipedia"),
    "originals_investment": ("header", "Parent filings, trade press"),
    "hub_deals": ("header", "Press releases, trade press"),
    "named_originals": ("header", "Wikipedia originals list, trade press"),
    "franchises": ("header", "Platform announcements, trade press"),
    "mau": ("audience", "Parent investor releases, Ormax, trade press"),
    "subscribers": ("audience", "Parent investor releases, trade press"),
    "segment_skews": ("audience", "Ormax, trade press"),
    "diaspora": ("audience", "Press releases, trade press"),
    "genre_mix": ("emotional", "Wikipedia, trade press"),
    "regulatory_ctx": ("emotional", "MIB notices, trade press"),
    "downloads": ("distribution", "Play Store, company statements"),
    "telecom_bundles": ("distribution", "Telecom plan pages, trade press"),
    "devices": ("distribution", "Platform help pages"),
    "linear_share": ("distribution", "BARC/company commentary, trade press"),
    "ctv_share": ("distribution", "Company data, trade press"),
    "dubbing": ("distribution", "Platform help pages, trade press"),
    "windows": ("distribution", "Trade press, platform announcements"),
    "revenue_annual": ("revenue", "Parent filings (PDFs)"),
    "revenue_quarterly": ("revenue", "Parent filings, earnings calls"),
    "ebitda": ("revenue", "Parent filings"),
    "pricing": ("revenue", "Pricing page, trade press"),
    "ad_products": ("revenue", "Press releases, trade press"),
    "sports_rights": ("revenue", "Trade press, press releases"),
    "mission": ("editorial", "Press releases, interviews"),
    "leadership": ("editorial", "Press releases, interviews"),
    "campaigns": ("editorial", "Trade press, press releases"),
    "share_trends": ("competitive", "JustWatch via press, Ormax"),
    "rival_gains": ("competitive", "JustWatch via press, Ormax"),
    "ownership": ("negotiation", "Press releases, trade press"),
    "ceo_structure": ("negotiation", "Press releases, trade press"),
    "approval_chain": ("negotiation", "Trade press, interviews"),
    "data_sharing": ("negotiation", "Trade press, privacy pages"),
}

QUERY_TEMPLATES: dict[str, list[str]] = {
    "_global": [
        "{platform} original series 2026",
        "{platform} price plans India",
        "{platform} subscribers revenue",
        "{platform} licensing deal",
        "{platform} regional language slate",
    ],
    "sports_rights": ["{platform} sports rights (news, past year)"],
    "trade": [
        "site:storyboard18.com {platform}",
        "site:exchange4media.com {platform}",
        "site:afaqs.com {platform}",
        "site:ormaxmedia.com {platform}",
    ],
    "wikipedia": ['"List of {platform} original programming"'],
}

REQUIRED_SLOTS_PER_SECTION: dict[str, list[str]] = {
    "content": ["content_hours", "language_count", "originals_investment", "hub_deals", "named_originals", "franchises"],
    "audience": ["mau", "subscribers", "segment_skews"],
    "emotional": ["genre_mix", "regulatory_ctx"],
    "distribution": ["downloads", "telecom_bundles", "devices", "windows"],
    "revenue": ["revenue_annual", "pricing", "ad_products"],
    "editorial": ["mission", "leadership"],
}

# Targeted re-search queries per slot (plan Step D: coverage check).
# Each run uses at most the first 2 per missing slot.
SLOT_QUERIES: dict[str, list[str]] = {
    "content_hours": ["{platform} content hours library catalogue", "{platform} lakh hours catalogue"],
    "language_count": ["{platform} languages Tamil Telugu originals", "{platform} regional language slate"],
    "originals_investment": ["{platform} content investment crore originals", "{platform} slate investment commitment"],
    "hub_deals": ["{platform} licensing deal studio partnership", "{platform} exclusive streaming deal"],
    "named_originals": ["{platform} original series slate", "{platform} new shows films announced"],
    "franchises": ["{platform} franchise season renewal", "{platform} reality show new season"],
    "mau": ["{platform} MAU monthly active users", "{platform} users downloads crore"],
    "subscribers": ["{platform} paying subscribers", "{platform} subscriber base million"],
    "segment_skews": ["{platform} audience youth metro tier-2", "{platform} viewers demographic"],
    "genre_mix": ["{platform} genres crime reality shows slate"],
    "regulatory_ctx": ["{platform} IT Rules self-regulation MIB", "{platform} OTT regulation compliance"],
    "downloads": ["{platform} app downloads Play Store", "{platform} installs crore"],
    "telecom_bundles": ["{platform} Jio Airtel recharge bundle plan", "{platform} telecom bundled subscription"],
    "devices": ["{platform} connected TV smart TV devices", "{platform} CTV viewing"],
    "linear_share": ["{platform} TV viewership share BARC", "{platform} broadcast network share"],
    "ctv_share": ["{platform} connected TV audience", "{platform} large screen viewing"],
    "dubbing": ["{platform} dubbed multi-language release", "{platform} Hindi Tamil Telugu dubbed"],
    "windows": ["{platform} theatrical OTT release window", "{platform} streaming premiere date"],
    "revenue_annual": ["{platform} revenue crore earnings", "{platform} profit loss financial year"],
    "revenue_quarterly": ["{platform} quarterly results revenue", "{platform} quarter revenue growth"],
    "ebitda": ["{platform} EBITDA margin profit"],
    "pricing": ["{platform} subscription price plans monthly yearly", "{platform} plan price"],
    "ad_products": ["{platform} advertising revenue ads", "{platform} ad sales brand partnerships"],
    "sports_rights": ["{platform} sports rights cricket IPL", "{platform} ICC BCCI media rights"],
    "mission": ["{platform} mission vision leadership interview"],
    "leadership": ["{platform} CEO content head appointed", "{platform} leadership team"],
    "campaigns": ["{platform} brand campaign launch marketing"],
    "share_trends": ["{platform} JustWatch market share SVOD", "{platform} Ormax OTT audience report"],
    "rival_gains": ["{platform} rivals subscriber growth competition"],
    "ownership": ["{platform} stake joint venture ownership", "{platform} parent company"],
    "ceo_structure": ["{platform} CEO structure digital broadcast", "{platform} top management"],
    "approval_chain": ["{platform} greenlit commissioned approval", "{platform} content approval"],
    "data_sharing": ["{platform} viewership data transparency", "{platform} audience data sharing"],
    "diaspora": ["{platform} international launch UK US", "{platform} global expansion"],
}

RUBRIC = """90-100: defining leader, near-zero gaps. 70-89: strong with minor gaps.
50-69: mixed, material gaps. Under 50: weak/absent."""

# Calibration anchors from the JioHotstar example (structure reference only).
CALIBRATION_ANCHORS = {
    "distribution": "87 in example: distribution is the product, near-zero structural gaps",
    "emotional": "54 in example: no consistent register",
    "content": "68 in example: breadth without originals-engagement leadership",
}

SAMPLING_THRESHOLD = 150
STALENESS_MONTHS = 18
CONFLICT_PCT = 0.25

SECTION_SLOTS: dict[str, tuple[str, ...]] = {
    "content": ("content_hours", "language_count", "originals_investment",
                "hub_deals", "named_originals", "franchises"),
    "audience": ("mau", "subscribers", "segment_skews", "diaspora"),
    "emotional": ("genre_mix", "regulatory_ctx"),
    "distribution": ("downloads", "telecom_bundles", "devices", "linear_share",
                     "ctv_share", "dubbing", "windows"),
    "revenue": ("revenue_annual", "revenue_quarterly", "ebitda", "pricing",
                "ad_products", "sports_rights"),
    "editorial": ("mission", "leadership", "campaigns", "ceo_structure",
                  "ownership"),
}
