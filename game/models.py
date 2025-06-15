from enum import Enum
from typing import List, Optional, Dict
from pydantic import BaseModel

class CardSuit(str, Enum):
    SPADES = "spades"
    HEARTS = "hearts"
    DIAMONDS = "diamonds"
    CLUBS = "clubs"

class CardRank(str, Enum):
    ACE = "ace"
    TWO = "2"
    THREE = "3"
    FOUR = "4"
    FIVE = "5"
    SIX = "6"
    SEVEN = "7"
    EIGHT = "8"
    NINE = "9"
    TEN = "10"
    JACK = "jack"
    QUEEN = "queen"
    KING = "king"

class Card(BaseModel):
    suit: CardSuit
    rank: CardRank

    def to_dict(self) -> Dict:
        return {
            "suit": self.suit,
            "rank": self.rank
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Card':
        return cls(suit=data["suit"], rank=data["rank"])
    

class Player(BaseModel):
    id: str
    name: str
    hand: List[Card] = []
    face_up: List[Card] = [] 
    face_down: List[Card] = []
    is_bot: bool = False
    is_ready: bool = False


    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "hand": [card.to_dict() for card in self.hand],
            "face_up": [card.to_dict() for card in self.face_up],
            "face_down": [None]*len(self.face_down),  # Players cannot see face-down cards,
            "is_bot": self.is_bot,
            "is_ready": self.is_ready
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Player':
        return cls(
            id=data["id"],
            name=data["name"],
            hand=[Card.from_dict(card) for card in data.get("hand", [])],
            is_bot=data.get("is_bot", False),
            is_ready=data.get("is_ready", False),
        )

class GameStatus(str, Enum):
    WAITING = "waiting"
    SWAPPING = "swapping"
    PLAYING = "playing"
    ENDED = "ended"

class GameState(BaseModel):
    players: List[Player]
    current_player_index: int
    deck: List[Card]
    discard_pile: List[Card]
    game_status: GameStatus
    room_id: str

    def to_dict(self) -> Dict:
        return {
            "players": [player.to_dict() for player in self.players],
            "current_player_index": self.current_player_index,
            "deck": [card.to_dict() for card in self.deck],
            "discard_pile": [card.to_dict() for card in self.discard_pile],
            "game_status": self.game_status.value,
            "room_id": self.room_id
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'GameState':
        return cls(
            players=[Player.from_dict(player) for player in data["players"]],
            current_player_index=data["current_player_index"],
            deck=[Card.from_dict(card) for card in data["deck"]],
            discard_pile=[Card.from_dict(card) for card in data["discard_pile"]],
            game_status=GameStatus(data["game_status"]),
            room_id=data["room_id"]
        ) 