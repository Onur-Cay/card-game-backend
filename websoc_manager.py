import json
from fastapi import WebSocket, WebSocketDisconnect, Depends
from typing import Dict, List
from sqlalchemy.orm import Session
from urllib.parse import urljoin

from database.database import get_db, get_game_state, get_room
from constants import BASE_URL

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.player_screens: Dict[str, str] = {}

    async def connect(self, websocket: WebSocket, room_id: str, player_id: str, screen: str):
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = []
        self.active_connections[room_id].append(websocket)
        self.player_screens[player_id] = screen

    def disconnect(self, websocket: WebSocket, room_id: str, player_id: str):
        if room_id in self.active_connections:
            self.active_connections[room_id].remove(websocket)
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]
        if player_id in self.player_screens:
            del self.player_screens[player_id]

    async def broadcast_to_room(self, message: dict, room_id: str):
        if room_id in self.active_connections:
            for connection in self.active_connections[room_id]:
                await connection.send_json(message)

    async def send_to_player(self, message: dict, player_id: str):
        for room_id, connections in self.active_connections.items():
            for connection in connections:
                if player_id in self.player_screens:
                    await connection.send_json(message)
                    break

manager = ConnectionManager()

async def websocket_endpoint(
    websocket: WebSocket, 
    room_id: str, 
    player_id: str, 
    screen: str,  
    db: Session = Depends(get_db)
):
    await manager.connect(websocket, room_id, player_id, screen)
    try:
        game_state = get_game_state(db, room_id)
        if game_state:
            response = {
                "type": "game_state",
                "screen": screen,
                "data": game_state.to_dict()
            }
            await websocket.send_json(response)
        
        while True:
            data = await websocket.receive_json()
            if "screen" in data:
                manager.player_screens[player_id] = data["screen"]
                if data["screen"] == "game":
                    game_state = get_game_state(db, room_id)
                    await websocket.send_json({
                        "type": "game_state",
                        "screen": "game",
                        "data": game_state.to_dict()
                    })
                elif data["screen"] == "lobby":
                    room = get_room(db, room_id)
                    await websocket.send_json({
                        "type": "room_info",
                        "screen": "lobby",
                        "data": {
                            "id": room.id,
                            "name": room.name,
                            "players": json.loads(room.players),
                            "status": room.status,
                            "shareable_link": urljoin(BASE_URL, f"/join/{room_id}")
                        }
                    })
            if "action" in data:
                # TODO: Implement game action handling
                pass
            await manager.broadcast_to_room({
                "type": "update",
                "screen": screen,
                "data": data
            }, room_id)
    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id, player_id)
        await manager.broadcast_to_room({
            "type": "player_disconnected",
            "screen": "game",
            "data": {"player_id": player_id}
        }, room_id)