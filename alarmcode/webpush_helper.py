#!/usr/bin/env python3
"""Web Push (VAPID / RFC 8291 / RFC 8292) helper for AlarmPI browser push notifications."""

import base64
import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger('alarmpi')

try:
    import pywebpush
    from py_vapid import Vapid
    from cryptography.hazmat.primitives import serialization
    HAS_WEBPUSH = True
except ImportError:
    HAS_WEBPUSH = False
    logger.warning("pywebpush or py_vapid not available. Browser Web Push notifications will be disabled.")


def get_or_create_vapid_keys(wd: str, server_json: Optional[Dict[str, Any]] = None) -> Tuple[Optional[str], Optional[str]]:
    """Ensure VAPID keypair exists on disk and return (private_pem_path, public_key_b64url)."""
    if not HAS_WEBPUSH:
        return None, None

    config_dir = os.path.join(wd, "config")
    os.makedirs(config_dir, exist_ok=True)
    vapid_pem_path = os.path.join(config_dir, "vapid_private.pem")
    server_json_path = os.path.join(config_dir, "server.json")

    public_key_b64 = None
    if server_json is not None:
        public_key_b64 = server_json.get("vapid_public_key")

    if os.path.exists(vapid_pem_path):
        try:
            with open(vapid_pem_path, "rb") as f:
                vapid = Vapid.from_pem(f.read())
            pub_bytes = vapid.public_key.public_bytes(
                encoding=serialization.Encoding.X962,
                format=serialization.PublicFormat.UncompressedPoint
            )
            public_key_b64 = base64.urlsafe_b64encode(pub_bytes).decode('utf-8').rstrip('=')
            if server_json is not None and server_json.get("vapid_public_key") != public_key_b64:
                server_json["vapid_public_key"] = public_key_b64
                try:
                    with open(server_json_path, "w") as f:
                        json.dump(server_json, f, sort_keys=True, indent=4)
                except Exception:
                    pass
            return vapid_pem_path, public_key_b64
        except Exception:
            logger.exception("Error loading existing VAPID key from %s, regenerating:", vapid_pem_path)

    # Generate new VAPID keys
    try:
        vapid = Vapid()
        vapid.generate_keys()
        with open(vapid_pem_path, "wb") as f:
            f.write(vapid.private_pem())
        try:
            os.chmod(vapid_pem_path, 0o600)
        except Exception:
            pass

        pub_bytes = vapid.public_key.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint
        )
        public_key_b64 = base64.urlsafe_b64encode(pub_bytes).decode('utf-8').rstrip('=')

        if server_json is not None:
            server_json["vapid_public_key"] = public_key_b64
            try:
                with open(server_json_path, "w") as f:
                    json.dump(server_json, f, sort_keys=True, indent=4)
            except Exception:
                pass

        logger.info("Generated new VAPID keypair for Browser Web Push.")
        return vapid_pem_path, public_key_b64
    except Exception:
        logger.exception("Failed to generate VAPID keys for Web Push:")
        return None, None


def send_webpush_to_all(
    vapid_pem_path: str,
    subscriptions: List[Dict[str, Any]],
    payload: Dict[str, Any],
    is_alarm: bool = False
) -> Tuple[int, List[str]]:
    """Send web push notification to a list of browser subscriptions.
    
    Returns (delivered_count, dead_endpoints_list).
    """
    if not HAS_WEBPUSH or not vapid_pem_path or not os.path.exists(vapid_pem_path):
        logger.warning("Web Push not configured or VAPID key missing.")
        return 0, []

    if not subscriptions:
        logger.debug("No browser webpush subscriptions registered.")
        return 0, []

    payload_str = json.dumps(payload)
    vapid_claims = {"sub": "mailto:admin@alarmpi.local"}
    ttl = 3600 if is_alarm else 300

    delivered = 0
    dead_endpoints = []

    for item in subscriptions:
        sub_info = item.get("subscription", item) if isinstance(item, dict) else item
        if not isinstance(sub_info, dict):
            continue
        endpoint = sub_info.get("endpoint")
        if not endpoint:
            continue

        try:
            pywebpush.webpush(
                subscription_info=sub_info,
                data=payload_str,
                vapid_private_key=vapid_pem_path,
                vapid_claims=vapid_claims,
                ttl=ttl
            )
            delivered += 1
            logger.debug("Delivered web push to %s", endpoint[:40] + "...")
        except Exception as e:
            resp = getattr(e, 'response', None)
            status_code = getattr(resp, 'status_code', None)
            if status_code in (404, 410):
                logger.info("Browser push subscription expired or revoked (status %s): %s", status_code, endpoint[:40])
                dead_endpoints.append(endpoint)
            else:
                logger.warning("WebPush send failed for %s: %s", endpoint[:40], e)

    return delivered, dead_endpoints
