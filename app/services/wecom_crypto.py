from __future__ import annotations

import base64
import hashlib
import os
import struct
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from Crypto.Cipher import AES


@dataclass(frozen=True)
class WeComCallbackCrypto:
    token: str
    encoding_aes_key: str
    receive_id: str

    BLOCK_SIZE = 32

    def __post_init__(self) -> None:
        if not self.token:
            raise ValueError("token must not be blank")
        if len(self.encoding_aes_key) != 43:
            raise ValueError("encoding_aes_key must be a 43-character string")
        if not self.encoding_aes_key.isalnum():
            raise ValueError("encoding_aes_key must contain only English letters or digits")

    def verify_url(self, msg_signature: str, timestamp: str, nonce: str, encrypted_echo: str) -> str:
        self._verify_signature(msg_signature, timestamp, nonce, encrypted_echo)
        return self._decrypt(encrypted_echo)

    def decrypt_message(self, msg_signature: str, timestamp: str, nonce: str, request_body: str) -> str:
        encrypted = self._extract_xml_value(request_body, "Encrypt")
        self._verify_signature(msg_signature, timestamp, nonce, encrypted)
        return self._decrypt(encrypted)

    def encrypt(self, plain_text: str) -> str:
        message = plain_text.encode("utf-8")
        receive_id_bytes = self.receive_id.encode("utf-8")
        payload = (
            os.urandom(16)
            + struct.pack(">I", len(message))
            + message
            + receive_id_bytes
        )
        cipher = AES.new(self._aes_key, AES.MODE_CBC, self._iv)
        encrypted = cipher.encrypt(self._pkcs7_pad(payload))
        return base64.b64encode(encrypted).decode("utf-8")

    def sign(self, timestamp: str, nonce: str, payload: str) -> str:
        return self._sha1(self.token, timestamp, nonce, payload)

    @property
    def _aes_key(self) -> bytes:
        return base64.b64decode(self.encoding_aes_key + "=")

    @property
    def _iv(self) -> bytes:
        return self._aes_key[:16]

    def _verify_signature(self, msg_signature: str, timestamp: str, nonce: str, payload: str) -> None:
        expected = self._sha1(self.token, timestamp, nonce, payload)
        if expected != msg_signature:
            raise ValueError("WeCom callback signature verification failed")

    def _decrypt(self, encrypted: str) -> str:
        try:
            encrypted_bytes = base64.b64decode(encrypted)
            cipher = AES.new(self._aes_key, AES.MODE_CBC, self._iv)
            original = self._pkcs7_unpad(cipher.decrypt(encrypted_bytes))
            if len(original) < 20:
                raise ValueError("WeCom callback payload is too short")

            xml_length = struct.unpack(">I", original[16:20])[0]
            xml_start = 20
            xml_end = xml_start + xml_length
            if xml_length < 0 or xml_end > len(original):
                raise ValueError("WeCom callback payload length is invalid")

            message = original[xml_start:xml_end].decode("utf-8")
            actual_receive_id = original[xml_end:].decode("utf-8")
            if actual_receive_id != self.receive_id:
                raise ValueError("WeCom callback receiveId mismatch")
            return message
        except Exception as exc:  # noqa: BLE001
            raise ValueError("Failed to decrypt WeCom callback payload") from exc

    @classmethod
    def _extract_xml_value(cls, xml_body: str, tag_name: str) -> str:
        try:
            root = ET.fromstring(xml_body)
        except ET.ParseError as exc:
            raise ValueError("Failed to parse WeCom callback XML") from exc

        node = root.find(tag_name)
        if node is None or node.text is None or node.text.strip() == "":
            raise ValueError(f"WeCom callback XML missing {tag_name}")
        return node.text.strip()

    @classmethod
    def _pkcs7_pad(cls, payload: bytes) -> bytes:
        amount_to_pad = cls.BLOCK_SIZE - (len(payload) % cls.BLOCK_SIZE)
        if amount_to_pad == 0:
            amount_to_pad = cls.BLOCK_SIZE
        return payload + bytes([amount_to_pad] * amount_to_pad)

    @classmethod
    def _pkcs7_unpad(cls, payload: bytes) -> bytes:
        if not payload:
            raise ValueError("WeCom callback payload is empty")
        pad = payload[-1]
        if pad < 1 or pad > cls.BLOCK_SIZE or pad > len(payload):
            raise ValueError("WeCom callback PKCS7 padding is invalid")
        if payload[-pad:] != bytes([pad] * pad):
            raise ValueError("WeCom callback PKCS7 padding is invalid")
        return payload[:-pad]

    @staticmethod
    def _sha1(*parts: str) -> str:
        joined = "".join(sorted(parts))
        return hashlib.sha1(joined.encode("utf-8")).hexdigest()
