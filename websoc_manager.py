import json
from fastapi import WebSocket, WebSocketDisconnect, Depends
from typing import Dict, List
from sqlalchemy.orm import Session
from urllib.parse import urljoin

from database.database import get_db, get_game_state, get_room
from constants import BASE_URL

from game.game_manager import GameManager
from game.models import Card
gameManager = GameManager()

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}
        self.player_screens: Dict[str, str] = {}
       
    async def connect(self, room_id: str, player_id: str, websocket: WebSocket):
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = {}
        self.active_connections[room_id][player_id] = websocket

    def disconnect(self, room_id: str, player_id: str):
        if room_id in self.active_connections:
            self.active_connections[room_id].pop(player_id, None)
            if not self.active_connections[room_id]:
                self.active_connections.pop(room_id)

    async def broadcast_to_room(self, message: dict, room_id: str):
        if room_id in self.active_connections:
            for connection in self.active_connections[room_id]:
                await connection.send_json(message)

    async def send_to_player(self, message: dict, player_id: str, room_id: str):
        ws = self.active_connections.get(room_id, {}).get(player_id)
        if ws:
            await ws.send_json(message)

manager = ConnectionManager()

async def websocket_endpoint(
    websocket: WebSocket, 
    room_id: str, 
    player_id: str, 
    screen: str,  
    db: Session = Depends(get_db)
):
    await manager.connect(room_id, player_id, websocket)
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
            if data.get("screen"):
                manager.player_screens[player_id] = data.get("screen")
                if data.get("screen") == "game":
                    game_state = get_game_state(db, room_id)
                    await websocket.send_json({
                        "type": "game_state",
                        "screen": "game",
                        "data": game_state.to_dict()
                    })
                elif data.get("screen") == "lobby":
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
            if data.get("action"):
                action = data.get("action")
                result = None
                if action == "play_card":
                    card_data = data.get("card")
                    source = data.get("source", "hand")
                    result = gameManager.play_card(room_id, player_id, Card.from_dict(card_data), source=source)
                elif action == "play_face_down_card":
                    card_index = data.get("card_index")
                    result = gameManager.play_face_down_card(room_id, player_id, card_index)
                elif action == "player_ready":
                    new_hand = [Card.from_dict(card) for card in data.get("hand", [])]
                    new_face_up = [Card.from_dict(card) for card in data.get("face_up", [])]
                    validation = gameManager.swap_and_ready(
                        room_id, 
                        player_id, 
                        new_hand=new_hand, 
                        new_face_up=new_face_up
                    )
                    if not validation:
                        await websocket.send_json({"error": "Cards are not valid for swapping."})
                        continue
                    all_ready = gameManager.all_players_ready(room_id)
                    result = "all_ready" if all_ready else "waiting"
                game_state = gameManager.get_game_state(room_id)
                if not game_state:
                    await websocket.send_json({
                        "error": "Game not found or ended."})
                    continue
                for player in game_state.players:
                    player_view = gameManager.get_player_view(room_id, player.id)
                    await manager.send_to_player({
                        "type": "game_state",
                        "screen": "game",
                        "data": player_view,
                        "result": getattr(result, "value", result)
                    }, player.id, room_id)
            continue
    except WebSocketDisconnect:
        manager.disconnect(room_id, player_id)
        await manager.broadcast_to_room({
            "type": "player_disconnected",
            "screen": "game",
            "data": {"player_id": player_id}
        }, room_id)