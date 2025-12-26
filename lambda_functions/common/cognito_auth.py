import json
import os
import base64
import boto3

cognito = boto3.client("cognito-idp")
USER_POOL_ID = os.environ["USER_POOL_ID"]

def get_user_id_from_event(event):
    try:
        headers = event.get("headers") or {}
        auth = headers.get("Authorization") or headers.get("authorization")

        if not auth:
            raise Exception("Authorization header missing")

        token = auth.replace("Bearer ", "")
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)

        decoded = json.loads(base64.b64decode(payload).decode("utf-8"))
        return decoded["sub"]

    except Exception as e:
        raise Exception(f"Unauthorized: {str(e)}")
