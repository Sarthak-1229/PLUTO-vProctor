"""Media transport abstraction layer supporting WebRTC P2P + STUN/TURN and SFU extensibility."""
from __future__ import annotations

import abc
from typing import Any, Dict, List, Optional
from backend.app.config import settings


class MediaTransportAdapter(abc.ABC):
    """Abstract contract for live media session establishment and negotiation."""

    @abc.abstractmethod
    def get_transport_type(self) -> str:
        """Return the transport mode identifier ('p2p' or 'sfu')."""
        raise NotImplementedError

    @abc.abstractmethod
    def get_ice_servers(self) -> List[Dict[str, Any]]:
        """Return configured STUN and TURN server credentials for WebRTC ICE negotiation."""
        raise NotImplementedError

    @abc.abstractmethod
    def generate_join_credentials(
        self,
        *,
        room_id: str,
        user_id: str,
        user_name: str,
        role: str,
    ) -> Dict[str, Any]:
        """Generate client-side session credentials or tokens for joining media."""
        raise NotImplementedError

    @abc.abstractmethod
    def validate_signal_payload(self, signal_type: str, payload: Dict[str, Any]) -> bool:
        """Validate signaling message payload schema before relaying."""
        raise NotImplementedError


class P2PMediaTransportAdapter(MediaTransportAdapter):
    """Browser-to-browser WebRTC Peer-to-Peer media with WebSocket signaling."""

    def get_transport_type(self) -> str:
        return "p2p"

    def get_ice_servers(self) -> List[Dict[str, Any]]:
        ice: List[Dict[str, Any]] = []
        for stun_url in settings.STUN_SERVERS:
            if stun_url.strip():
                ice.append({"urls": stun_url.strip()})

        for turn_url in settings.TURN_SERVER_URLS:
            if turn_url.strip():
                server_dict: Dict[str, Any] = {"urls": turn_url.strip()}
                if settings.TURN_USERNAME:
                    server_dict["username"] = settings.TURN_USERNAME
                if settings.TURN_CREDENTIAL:
                    server_dict["credential"] = settings.TURN_CREDENTIAL
                ice.append(server_dict)
        return ice

    def generate_join_credentials(
        self,
        *,
        room_id: str,
        user_id: str,
        user_name: str,
        role: str,
    ) -> Dict[str, Any]:
        return {
            "transport": "p2p",
            "room_id": room_id,
            "user_id": user_id,
            "user_name": user_name,
            "role": role,
            "ice_servers": self.get_ice_servers(),
        }

    def validate_signal_payload(self, signal_type: str, payload: Dict[str, Any]) -> bool:
        if not isinstance(payload, dict):
            return False
        if signal_type in ("offer", "answer"):
            sdp = payload.get("sdp")
            type_field = payload.get("type")
            return bool(sdp and type_field in ("offer", "answer"))
        elif signal_type == "ice_candidate":
            candidate = payload.get("candidate")
            return bool(candidate is not None)
        return True


class SFUMediaTransportAdapter(MediaTransportAdapter):
    """Extensible Selective Forwarding Unit (e.g. LiveKit) adapter boundary."""

    def __init__(self, sfu_url: Optional[str] = None):
        self.sfu_url = sfu_url or settings.SFU_URL

    def get_transport_type(self) -> str:
        return "sfu"

    def get_ice_servers(self) -> List[Dict[str, Any]]:
        return []  # SFU coordinates ICE directly

    def generate_join_credentials(
        self,
        *,
        room_id: str,
        user_id: str,
        user_name: str,
        role: str,
    ) -> Dict[str, Any]:
        return {
            "transport": "sfu",
            "sfu_url": self.sfu_url,
            "room_id": room_id,
            "user_id": user_id,
            "user_name": user_name,
            "role": role,
            "token": f"sfu_token_{room_id}_{user_id}",
        }

    def validate_signal_payload(self, signal_type: str, payload: Dict[str, Any]) -> bool:
        return True


def get_media_transport_adapter() -> MediaTransportAdapter:
    """Factory resolving configured media transport adapter."""
    if settings.MEDIA_TRANSPORT_MODE == "sfu":
        return SFUMediaTransportAdapter()
    return P2PMediaTransportAdapter()

