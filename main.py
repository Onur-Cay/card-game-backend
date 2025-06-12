from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import json
import uuid
from typing import Dict, List, Optional
from pydantic import BaseModel
import diceware
import argparse
from urllib.parse import urljoin

from database import get_db, create_room, get_room, list_rooms, join_room, start_game, get_game_state, update_game_state
from game.models import GameState, Player, Card

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your Flutter app's domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
BASE_URL = "http://localhost:8000"  # Change this in production
ROOM_ID_WORDS = 3  # Number of words in room ID

def generate_room_id() -> str:
    """Generate a memorable room ID using diceware words.
    
    Security considerations:
    - 4 words from EFF wordlist (4096 possibilities per word)
    - Random selection ensures uniqueness
    - Uppercase letters add complexity but may reduce usability
    - Room IDs are temporary and not meant to be secret
    """
    try:
        # Create an argparse.Namespace object with the desired configuration
        options = argparse.Namespace(
            num=ROOM_ID_WORDS,
            delimiter='-',
            caps=True,  # Keep uppercase letters for additional complexity
            specials=0,  # No special characters
            randomsource="system",
            wordlist=["en_eff"],  # Use EFF's English word list
            dice_sides=6,
            verbose=0,
            infile=None
        )
        
        # Generate the room ID using diceware
        room_id = diceware.get_passphrase(options)
        return room_id  # Keep the original case
        
    except Exception as e:
        # Fallback to UUID if diceware fails
        print(f"Diceware error: {e}")
        return str(uuid.uuid4())

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}  # room_id -> list of connections
        self.player_screens: Dict[str, str] = {}  # player_id -> current_screen

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
        # Find the player's connection and send message
        for room_id, connections in self.active_connections.items():
            for connection in connections:
                if player_id in self.player_screens:
                    await connection.send_json(message)
                    break

manager = ConnectionManager()

# Pydantic models for request/response
class CreateRoomRequest(BaseModel):
    name: str
    host_id: str
    max_players: int = 4

class RoomResponse(BaseModel):
    id: str
    name: str
    host_id: str
    players: List[str]
    status: str
    max_players: int
    shareable_link: str

# REST API endpoints
@app.post("/rooms", response_model=RoomResponse)
def create_new_room(request: CreateRoomRequest, db: Session = Depends(get_db)):
    # Generate a memorable room ID
    room_id = generate_room_id()
    
    # Create the room
    room = create_room(db, room_id, request.name, request.host_id, request.max_players)
    
    # Generate shareable link
    shareable_link = urljoin(BASE_URL, f"/join/{room_id}")
    
    return RoomResponse(
        id=room.id,
        name=room.name,
        host_id=room.host_id,
        players=json.loads(room.players),
        status=room.status,
        max_players=room.max_players,
        shareable_link=shareable_link
    )

@app.get("/rooms", response_model=List[RoomResponse])
def get_available_rooms(status: Optional[str] = None, db: Session = Depends(get_db)):
    rooms = list_rooms(db, status)
    return [
        RoomResponse(
            id=room.id,
            name=room.name,
            host_id=room.host_id,
            players=json.loads(room.players),
            status=room.status,
            max_players=room.max_players,
            shareable_link=urljoin(BASE_URL, f"/join/{room.id}")
        )
        for room in rooms
    ]

@app.get("/join/{room_id}")
def join_room_via_link(room_id: str, player_id: str, db: Session = Depends(get_db)):
    """Endpoint for joining a room via shareable link."""
    if not join_room(db, room_id, player_id):
        raise HTTPException(status_code=400, detail="Could not join room")
    return {"status": "success", "room_id": room_id}

@app.post("/rooms/{room_id}/join")
def join_game_room(room_id: str, player_id: str, db: Session = Depends(get_db)):
    if not join_room(db, room_id, player_id):
        raise HTTPException(status_code=400, detail="Could not join room")
    return {"status": "success"}

@app.post("/rooms/{room_id}/start")
def start_game_room(room_id: str, db: Session = Depends(get_db)):
    room = get_room(db, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    # Create initial game state
    players = [Player(id=pid, name=f"Player {i+1}") for i, pid in enumerate(json.loads(room.players))]
    game_state = GameState(
        players=players,
        current_player_index=0,
        deck=[],  # TODO: Initialize with shuffled deck
        discard_pile=[],
        game_status="playing",
        room_id=room_id
    )
    
    if not start_game(db, room_id, game_state):
        raise HTTPException(status_code=400, detail="Could not start game")
    return {"status": "success"}

# WebSocket endpoint
@app.websocket("/ws/game/{room_id}/{player_id}")
async def websocket_endpoint(
    websocket: WebSocket, 
    room_id: str, 
    player_id: str, 
    screen: str,  # Current screen name
    db: Session = Depends(get_db)
):
    await manager.connect(websocket, room_id, player_id, screen)
    try:
        # Send initial game state
        game_state = get_game_state(db, room_id)
        if game_state:
            # Include screen-specific data in the response
            response = {
                "type": "game_state",
                "screen": screen,
                "data": game_state.to_dict()
            }
            await websocket.send_json(response)
        
        while True:
            data = await websocket.receive_json()
            
            # Handle screen transitions
            if "screen" in data:
                manager.player_screens[player_id] = data["screen"]
                # Send screen-specific data
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
            
            # Handle game actions
            if "action" in data:
                # TODO: Implement game action handling
                pass
            
            # Broadcast updates to all players in the room
            await manager.broadcast_to_room({
                "type": "update",
                "screen": screen,
                "data": data
            }, room_id)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id, player_id)
        # Notify other players about disconnection
        await manager.broadcast_to_room({
            "type": "player_disconnected",
            "screen": "game",
            "data": {"player_id": player_id}
        }, room_id)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 