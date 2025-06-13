
#General Imports
import argparse
import uuid
import diceware
import json
from urllib.parse import urljoin
from typing import List, Optional

# FastAPI Imports
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel


#Database Imports
from sqlalchemy.orm import Session
from database.database import( 
get_db, create_room, get_room, list_rooms, join_room, start_game, get_game_state, update_game_state
)

# Game Imports
from game.models import Player, GameState

# Configuration
from constants import BASE_URL, ROOM_ID_WORDS

router = APIRouter()

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
@router.post("/rooms", response_model=RoomResponse)
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

@router.get("/rooms", response_model=List[RoomResponse])
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

@router.get("/join/{room_id}")
def join_room_via_link(room_id: str, player_id: str, db: Session = Depends(get_db)):
    """Endpoint for joining a room via shareable link."""
    if not join_room(db, room_id, player_id):
        raise HTTPException(status_code=400, detail="Could not join room")
    return {"status": "success", "room_id": room_id}

@router.post("/rooms/{room_id}/join")
def join_game_room(room_id: str, player_id: str, db: Session = Depends(get_db)):
    if not join_room(db, room_id, player_id):
        raise HTTPException(status_code=400, detail="Could not join room")
    return {"status": "success"}

@router.post("/rooms/{room_id}/start")
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
