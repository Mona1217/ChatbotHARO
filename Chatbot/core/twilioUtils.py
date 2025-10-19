import os
from twilio.rest import Client
from dotenv import load_dotenv

_client = None
_WHATSAPP_FROM = None

def _get_env(varname: str) -> str:
    val = os.environ.get(varname)
    if val is None or str(val).strip() == "":
        raise RuntimeError(f"Falta variable de entorno: {varname}")
    return val.strip()

def _get_client() -> Client:
    global _client, _WHATSAPP_FROM
    if _client is not None:
        return _client

    account_sid = _get_env("ACc6e2844889d7e4c8b7257924b91fba79")
    auth_token  = _get_env("0a25d3b3b498606c522974aa5abf9740")
    _WHATSAPP_FROM = _get_env("+14155238886")
    if not _WHATSAPP_FROM.startswith("whatsapp:"):
        _WHATSAPP_FROM = f"whatsapp:{_WHATSAPP_FROM}"

    _client = Client(account_sid, auth_token)
    return _client

def send_whatsapp(to_number: str, body: str):
    client = _get_client()
    if not to_number.startswith("whatsapp:"):
        to_number = f"whatsapp:{to_number}"
    client.messages.create(from_=_WHATSAPP_FROM, to=to_number, body=body)