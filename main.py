from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.rooms import router as rooms_router
from routers.player import router as player_router
from websoc_manager import websocket_endpoint

from constants import WEB_URL

app = FastAPI()

# CORS middleware (keep this in main.py)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[WEB_URL],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register REST routers
app.include_router(rooms_router)
app.include_router(player_router)

# Register WebSocket endpoint
app.add_api_websocket_route(
    "/ws/game/{room_id}/{player_id}",
    websocket_endpoint
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)