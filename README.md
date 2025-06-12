# Card Game Backend

This is the backend server for the card game, built with FastAPI and WebSocket support. It provides both REST API endpoints for room management and WebSocket connections for real-time game updates.

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the server:
```bash
python main.py
```

The server will start on `http://localhost:8000`

## API Endpoints

### REST API

- `POST /rooms` - Create a new game room
  - Request body: `{ "name": string, "host_id": string, "max_players": number }`
  - Response: Room details including room_id

- `GET /rooms` - List available rooms
  - Query params: `status` (optional) - Filter by room status
  - Response: List of room details

- `POST /rooms/{room_id}/join` - Join a game room
  - Query params: `player_id` - ID of the player joining
  - Response: Success status

- `POST /rooms/{room_id}/start` - Start the game in a room
  - Response: Success status

### WebSocket

- `ws://localhost:8000/ws/game/{room_id}/{player_id}` - WebSocket connection for real-time game updates
  - `room_id`: The ID of the game room
  - `player_id`: The ID of the player connecting

## Game State

The game state is managed through WebSocket connections. When a player connects:
1. They receive the current game state
2. They can send game actions through the WebSocket
3. All players in the room receive updates when the game state changes

## Development

The project structure:
```
my_card_game_backend/
├── .gitignore
├── requirements.txt
├── main.py              # FastAPI application and WebSocket handling
├── database.py          # Database models and operations
├── game/
│   ├── __init__.py
│   ├── models.py        # Game state models
│   └── game_manager.py  # Game logic (to be implemented)
└── README.md
```


