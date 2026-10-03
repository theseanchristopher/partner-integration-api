def to_component_request(request):
    """Translate the unified request into the selected backend format."""
    component = request["component"]
    merchant_id = request["merchantId"]

    if component == "COMPONENT_A":
        return {"merchant_id": merchant_id}

    if component == "COMPONENT_B":
        return {"accountReference": merchant_id}

    raise ValueError("Unsupported component")


def to_unified_response(component, response):
    """Normalize a backend response into the unified format."""
    if component == "COMPONENT_A":
        status = response["status"]
        if status not in ("A", "I"):
            raise ValueError("Invalid Component A status")

        merchant_id = response["merchant_id"]
        active = status == "A"

    elif component == "COMPONENT_B":
        enabled = response["enabled"]
        if not isinstance(enabled, bool):
            raise ValueError("Component B enabled must be a boolean")

        merchant_id = response["accountReference"]
        active = enabled

    else:
        raise ValueError("Unsupported component")

    return {
        "merchantId": merchant_id,
        "component": component,
        "eligible": active,
        "status": "ACTIVE" if active else "INACTIVE",
    }
