"""WebSocket connection manager and live-metrics endpoint."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.security import decode_access_token

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """Tracks active WebSocket clients and broadcasts JSON payloads to all."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    @property
    def active_count(self) -> int:
        return len(self._connections)

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)
        logger.info("WebSocket connected (%d active)", self.active_count)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(websocket)
        logger.info("WebSocket disconnected (%d active)", self.active_count)

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Send a JSON message to every connected client; drop dead sockets."""
        if not self._connections:
            return
        async with self._lock:
            targets = list(self._connections)
        stale: list[WebSocket] = []
        for connection in targets:
            try:
                await connection.send_json(message)
            except Exception:  # noqa: BLE001 - connection broke mid-send
                stale.append(connection)
        if stale:
            async with self._lock:
                for connection in stale:
                    self._connections.discard(connection)


manager = ConnectionManager()


@router.websocket("/ws/metrics")
async def metrics_websocket(websocket: WebSocket) -> None:
    """Stream live system metrics.

    Authentication is optional but supported: pass `?token=<JWT>` as a query
    param. If a token is supplied it must be valid.
    """
    token = websocket.query_params.get("token")
    if token is not None and decode_access_token(token) is None:
        await websocket.close(code=4401)  # Custom: unauthorized
        return

    await manager.connect(websocket)
    try:
        while True:
            # We don't require client messages, but receiving keeps the
            # connection healthy and lets clients send ping/commands.
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as exc:  # noqa: BLE001
        logger.warning("WebSocket error: %s", exc)
        await manager.disconnect(websocket)
