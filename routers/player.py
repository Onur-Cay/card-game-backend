import uuid
from fastapi import APIRouter

router = APIRouter()

@router.get("/player_id")
def create_player_id():
    """Generate and return a new player ID."""
    player_id = str(uuid.uuid4())
    return {"player_id": player_id}