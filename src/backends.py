class MerchantNotFoundError(Exception):
    pass


COMPONENT_A_MERCHANTS = {
    "merchant-1001": "A",
    "merchant-1002": "I",
}

COMPONENT_B_ACCOUNTS = {
    "merchant-1001": True,
    "merchant-1002": False,
}


def call_component_a(request):
    merchant_id = request["merchant_id"]

    if merchant_id not in COMPONENT_A_MERCHANTS:
        raise MerchantNotFoundError("Merchant not found in Component A")

    return {
        "merchant_id": merchant_id,
        "status": COMPONENT_A_MERCHANTS[merchant_id],
    }


def call_component_b(request):
    account_reference = request["accountReference"]

    if account_reference not in COMPONENT_B_ACCOUNTS:
        raise MerchantNotFoundError("Merchant not found in Component B")

    return {
        "accountReference": account_reference,
        "enabled": COMPONENT_B_ACCOUNTS[account_reference],
    }
