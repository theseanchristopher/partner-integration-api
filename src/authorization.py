import json
import os


class UnauthenticatedError(Exception):
    pass


class ForbiddenError(Exception):
    pass


def authorize_request(event, request):
    try:
        claims = event["requestContext"]["authorizer"]["jwt"]["claims"]
        client_id = claims["client_id"]
    except (KeyError, TypeError):
        raise UnauthenticatedError("Authenticated client identity is required")

    if not isinstance(client_id, str) or not client_id:
        raise UnauthenticatedError("Authenticated client identity is required")

    access_map = json.loads(os.environ.get("PARTNER_ACCESS_MAP", "{}"))
    if not isinstance(access_map, dict):
        raise RuntimeError("Invalid authorization configuration")

    permissions = access_map.get(client_id, {})
    allowed_components = permissions.get(request["merchantId"], [])

    if request["component"] not in allowed_components:
        raise ForbiddenError("Access to this merchant or component is denied")
