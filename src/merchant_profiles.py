"""Simulated native merchant profiles for the two component APIs."""

COMPONENT_A_PROFILES = {
    "merchant-1001": {
        "country_code": "US",
        "capability_codes": ["CARD"],
        "onboarding_code": "C",
        "required_items": [],
    },
    "merchant-1002": {
        "country_code": "US",
        "capability_codes": [],
        "onboarding_code": "P",
        "required_items": ["BUSINESS_VERIFICATION"],
    },
}

COMPONENT_B_PROFILES = {
    "merchant-1001": {
        "profile": {"country": "US"},
        "capabilities": {"cardAcceptance": True},
        "onboarding": {
            "complete": True,
            "requirements": [],
        },
    },
    "merchant-1002": {
        "profile": {"country": "US"},
        "capabilities": {"cardAcceptance": False},
        "onboarding": {
            "complete": False,
            "requirements": ["BUSINESS_VERIFICATION"],
        },
    },
}
