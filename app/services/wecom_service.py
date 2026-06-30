from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from urllib.parse import quote

import httpx

from app.config import settings


logger = logging.getLogger(__name__)


@dataclass
class _AccessToken:
    value: str
    expires_at: float

    def is_valid(self) -> bool:
        return bool(self.value) and time.time() < self.expires_at


class WeComNotifier:
    def __init__(self) -> None:
        self._client = httpx.Client(timeout=10.0)
        self._lock = threading.Lock()
        self._access_token = _AccessToken("", 0.0)

    def send_text(self, message: str) -> None:
        if settings.wecom_webhook_url or settings.wecom_webhook_key:
            self._send_webhook_text(message)
            return
        self._send_app_text(message)

    def _send_webhook_text(self, message: str) -> None:
        webhook_url = settings.wecom_webhook_url or (
            self._normalize_base_url(settings.wecom_webhook_base_url)
            + "/cgi-bin/webhook/send?key="
            + quote(settings.wecom_webhook_key or "", safe="")
        )
        payload = {
            "msgtype": "text",
            "text": {"content": message},
        }
        self._send_json_request(webhook_url, payload, "WeCom send")

    def _send_app_text(self, message: str) -> None:
        payload: dict[str, object] = {
            "msgtype": "text",
            "agentid": int(settings.wecom_agent_id),
            "text": {"content": message},
            "safe": 0,
        }
        if settings.wecom_to_user:
            payload["touser"] = settings.wecom_to_user
        if settings.wecom_to_party:
            payload["toparty"] = settings.wecom_to_party
        if settings.wecom_to_tag:
            payload["totag"] = settings.wecom_to_tag

        message_url = (
            self._normalize_base_url(settings.wecom_api_base_url)
            + "/cgi-bin/message/send?access_token="
            + quote(self._get_access_token(), safe="")
        )
        self._send_json_request(message_url, payload, "WeCom send")

    def _get_access_token(self) -> str:
        current = self._access_token
        if current.is_valid():
            return current.value

        with self._lock:
            current = self._access_token
            if current.is_valid():
                return current.value

            token_url = (
                self._normalize_base_url(settings.wecom_api_base_url)
                + "/cgi-bin/gettoken?corpid="
                + quote(settings.wecom_corp_id, safe="")
                + "&corpsecret="
                + quote(settings.wecom_corp_secret, safe="")
            )
            response = self._client.get(token_url)
            payload = self._parse_and_validate_response(response, "WeCom gettoken")
            token = str(payload.get("access_token", "")).strip()
            expires_in = int(payload.get("expires_in", 7200))
            if not token:
                raise RuntimeError("WeCom gettoken response missing access_token")

            self._access_token = _AccessToken(token, time.time() + max(60, expires_in - 60))
            return token

    def _send_json_request(self, url: str, payload: dict[str, object], action: str) -> None:
        response = self._client.post(url, json=payload)
        self._parse_and_validate_response(response, action)

    @staticmethod
    def _parse_and_validate_response(response: httpx.Response, action: str) -> dict[str, object]:
        if response.status_code < 200 or response.status_code >= 300:
            raise RuntimeError(f"{action} failed with HTTP status {response.status_code}")
        payload = response.json()
        errcode = int(payload.get("errcode", -2**31))
        if errcode != 0:
            raise RuntimeError(f"{action} failed with errcode={errcode}, errmsg={payload.get('errmsg', '')}")
        return payload

    @staticmethod
    def _normalize_base_url(value: str) -> str:
        return value[:-1] if value.endswith("/") else value
