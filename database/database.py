from sqlalchemy import create_engine, Column, String, Integer, JSON, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func
import json
from typing import List, Optional
from datetime import datetime, timedelta
from game.models import GameState, Player

Base = declarative_base()

class Room(Base):
    __tablename__ = "rooms"
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    host_id = Column(String, nullable=False)
    players = Column(JSON, nullable=False)  # List of player IDs
    status = Column(String, nullable=False)  # waiting, playing, ended
    max_players = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=func.now())
    last_activity = Column(DateTime, default=func.now())
    expires_at = Column(DateTime, nullable=False)

class GameInstance(Base):
    __tablename__ = "game_instances"
    
    id = Column(String, primary_key=True)
    game_state = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=func.now())
    last_activity = Column(DateTime, default=func.now())

# Create SQLite database
engine = create_engine('sqlite:///game_data.db')
Base.metadata.create_all(engine)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_room(db, room_id: str, name: str, host_id: str, max_players: int) -> Room:
    """Create a new room with expiration time."""
    try:
        # Set room to expire in 24 hours
        expires_at = datetime.now() + timedelta(hours=24)
        
        room = Room(
            id=room_id,
            name=name,
            host_id=host_id,
            players=json.dumps([host_id]),
            status="waiting",
            max_players=max_players,
            expires_at=expires_at
        )
        db.add(room)
        db.commit()
        db.refresh(room)
        return room
    except Exception as e:
        db.rollback()
        raise Exception(f"Failed to create room: {str(e)}")

def get_room(db, room_id: str) -> Optional[Room]:
    """Get a room by ID, checking if it's expired."""
    room = db.query(Room).filter(Room.id == room_id).first()
    if room and room.expires_at < datetime.now():
        # Room has expired, mark it as ended
        room.status = "ended"
        db.commit()
        return None
    return room

def list_rooms(db, status: Optional[str] = None) -> List[Room]:
    """List all active (non-expired) rooms."""
    query = db.query(Room).filter(Room.expires_at > datetime.now())
    if status:
        query = query.filter(Room.status == status)
    return query.all()

def join_room(db, room_id: str, player_id: str) -> bool:
    """Join a room, checking for expiration and capacity."""
    try:
        room = get_room(db, room_id)
        if not room:
            return False
        
        players = json.loads(room.players)
        if len(players) >= room.max_players or player_id in players:
            return False
        
        players.append(player_id)
        room.players = json.dumps(players)
        room.last_activity = datetime.now()
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        raise Exception(f"Failed to join room: {str(e)}")

def start_game(db, room_id: str, game_state: GameState) -> bool:
    """Start a game in a room."""
    try:
        room = get_room(db, room_id)
        if not room or room.status != "waiting":
            return False
        
        # Create game instance
        game_instance = GameInstance(
            id=room_id,
            game_state=game_state.to_dict()
        )
        db.add(game_instance)
        
        # Update room status
        room.status = "playing"
        room.last_activity = datetime.now()
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        raise Exception(f"Failed to start game: {str(e)}")

def get_game_state(db, room_id: str) -> Optional[GameState]:
    """Get the current game state for a room."""
    try:
        game_instance = db.query(GameInstance).filter(GameInstance.id == room_id).first()
        if not game_instance:
            return None
        game_instance.last_activity = datetime.now()
        db.commit()
        return GameState.from_dict(game_instance.game_state)
    except Exception as e:
        db.rollback()
        raise Exception(f"Failed to get game state: {str(e)}")

def update_game_state(db, room_id: str, game_state: GameState) -> bool:
    """Update the game state for a room."""
    try:
        game_instance = db.query(GameInstance).filter(GameInstance.id == room_id).first()
        if not game_instance:
            return False
        
        game_instance.game_state = game_state.to_dict()
        game_instance.last_activity = datetime.now()
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        raise Exception(f"Failed to update game state: {str(e)}")

def cleanup_expired_rooms(db) -> int:
    """Clean up expired rooms and return the number of rooms cleaned up."""
    try:
        expired_rooms = db.query(Room).filter(Room.expires_at < datetime.now()).all()
        count = len(expired_rooms)
        
        for room in expired_rooms:
            # Delete associated game instance if it exists
            db.query(GameInstance).filter(GameInstance.id == room.id).delete()
            # Delete the room
            db.delete(room)
        
        db.commit()
        return count
    except Exception as e:
        db.rollback()
        raise Exception(f"Failed to cleanup rooms: {str(e)}")

def update_room_activity(db, room_id: str) -> bool:
    """Update the last activity timestamp for a room."""
    try:
        room = get_room(db, room_id)
        if not room:
            return False
        
        room.last_activity = datetime.now()
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        raise Exception(f"Failed to update room activity: {str(e)}") 