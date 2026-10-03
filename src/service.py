import re

from backends import call_component_a, call_component_b
from mappings import to_component_request, to_unified_response


class InvalidRequestError(Exception):
    pass


def validate_request(request):
    if not isinstance(request, dict):
        raise InvalidRequestError("Request must be a JSON object")

    expected_fields = {"merchantId", "component"}
    if set(request) != expected_fields:
        raise InvalidRequestError(
            "Request must contain only merchantId and component"
        )

    merchant_id = request["merchantId"]
    if (
        not isinstance(merchant_id, str)
        or not 1 <= len(merchant_id) <= 64
        or re.fullmatch(r"[A-Za-z0-9_-]+", merchant_id) is None
    ):
        raise InvalidRequestError(
            "merchantId must be 1-64 letters, numbers, underscores, or hyphens"
        )

    component = request["component"]
    if not isinstance(component, str) or component not in (
        "COMPONENT_A", "COMPONENT_B"
    ):
        raise InvalidRequestError(
            "component must be COMPONENT_A or COMPONENT_B"
        )


def check_eligibility(request):
    validate_request(request)
    backend_request = to_component_request(request)

    if request["component"] == "COMPONENT_A":
        backend_response = call_component_a(backend_request)
    else:
        backend_response = call_component_b(backend_request)

    return to_unified_response(request["component"], backend_response)
