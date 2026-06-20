import requests
from django.conf import settings

MC_BASE_URL = "https://cpaas.messagecentral.com"


def send_otp(mobile_number, otp_length=6):
    """Calls Message Central send API. Returns verificationId."""
    url = f"{MC_BASE_URL}/verification/v3/send"
    params = {
        "countryCode": "91",
        "flowType": "SMS",
        "mobileNumber": mobile_number,
        "otpLength": otp_length,
        "customerId": settings.MESSAGE_CENTRAL_CUSTOMER_ID,
    }
    headers = {"authToken": settings.MESSAGE_CENTRAL_AUTH_TOKEN}

    resp = requests.post(url, params=params, headers=headers, timeout=10)
    data = resp.json()

    if data.get("responseCode") == 200:
        return data["data"]["verificationId"]
    raise Exception(data.get("message", "Failed to send OTP"))


def validate_otp(verification_id, code):
    """Calls Message Central validate API. Returns True/False."""
    url = f"{MC_BASE_URL}/verification/v3/validateOtp"
    params = {"verificationId": verification_id, "code": code}
    headers = {"authToken": settings.MESSAGE_CENTRAL_AUTH_TOKEN}

    resp = requests.get(url, params=params, headers=headers, timeout=10)
    data = resp.json()

    return (
        data.get("responseCode") == 200
        and data.get("data", {}).get("verificationStatus") == "VERIFICATION_COMPLETED"
    )