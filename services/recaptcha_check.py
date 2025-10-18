import json
import requests

def verify_recaptcha(site_key: str, api_key: str, project_id: str, token: str, action: str = "REGISTER") -> dict:

    url = f"https://recaptchaenterprise.googleapis.com/v1/projects/{project_id}/assessments?key={api_key}"

    request_data = {
        "event": {
            "token": token,
            "expectedAction": action,
            "siteKey": site_key
        }
    }

    headers = {
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, headers=headers, json=request_data)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        return {
            "success": False,
            "error": str(e),
            "status_code": response.status_code if 'response' in locals() else None
        }
