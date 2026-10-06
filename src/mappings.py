import re


def to_component_request(request):
    """Translate the unified request into the selected backend format."""
    component = request["component"]
    merchant_id = request["merchantId"]

    if component == "COMPONENT_A":
        return {"merchant_id": merchant_id}

    if component == "COMPONENT_B":
        return {"accountReference": merchant_id}

    raise ValueError("Unsupported component")


def validate_country(country):
    if not isinstance(country, str) or re.fullmatch(r"[A-Z]{2}", country) is None:
        raise ValueError("Country must be a two-letter uppercase code")
    return country


def validate_requirements(requirements):
    if not isinstance(requirements, list) or any(
        not isinstance(item, str) or not item.strip()
        for item in requirements
    ):
        raise ValueError("Onboarding requirements must be nonempty strings")
    return list(requirements)


def to_unified_response(component, response):
    """Normalize native status, capabilities, and onboarding fields."""
    if not isinstance(response, dict):
        raise ValueError("Component response must be an object")

    if component == "COMPONENT_A":
        status = response["status"]
        if status not in ("A", "I"):
            raise ValueError("Invalid Component A status")

        merchant_id = response["merchant_id"]
        active = status == "A"
        country = validate_country(response["country_code"])

        codes = response["capability_codes"]
        if not isinstance(codes, list) or any(
            not isinstance(code, str) or code != "CARD"
            for code in codes
        ):
            raise ValueError("Invalid Component A capability codes")
        capabilities = ["CARD_ACCEPTANCE"] if "CARD" in codes else []

        onboarding_code = response["onboarding_code"]
        if onboarding_code not in ("C", "P"):
            raise ValueError("Invalid Component A onboarding code")
        complete = onboarding_code == "C"
        requirements = validate_requirements(response["required_items"])

    elif component == "COMPONENT_B":
        enabled = response["enabled"]
        if not isinstance(enabled, bool):
            raise ValueError("Component B enabled must be a boolean")

        merchant_id = response["accountReference"]
        active = enabled

        profile = response["profile"]
        native_capabilities = response["capabilities"]
        onboarding = response["onboarding"]
        if not all(
            isinstance(value, dict)
            for value in (profile, native_capabilities, onboarding)
        ):
            raise ValueError("Component B profile fields must be objects")

        country = validate_country(profile["country"])

        card_acceptance = native_capabilities["cardAcceptance"]
        if not isinstance(card_acceptance, bool):
            raise ValueError("Component B cardAcceptance must be a boolean")
        capabilities = ["CARD_ACCEPTANCE"] if card_acceptance else []

        complete = onboarding["complete"]
        if not isinstance(complete, bool):
            raise ValueError("Component B onboarding complete must be a boolean")
        requirements = validate_requirements(onboarding["requirements"])

    else:
        raise ValueError("Unsupported component")

    if (
        not isinstance(merchant_id, str)
        or re.fullmatch(r"[A-Za-z0-9_-]{1,64}", merchant_id) is None
    ):
        raise ValueError("Invalid merchant identifier in component response")

    if complete and requirements:
        raise ValueError("Completed onboarding cannot have outstanding requirements")

    return {
        "merchantId": merchant_id,
        "component": component,
        "eligible": active,
        "status": "ACTIVE" if active else "INACTIVE",
        "country": country,
        "capabilities": capabilities,
        "onboarding": {
            "status": "COMPLETE" if complete else "PENDING",
            "requirements": requirements,
        },
    }
