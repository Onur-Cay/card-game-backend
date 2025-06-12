import requests
import websockets
import asyncio
import json

# REST API testing
def test_rest_api():
    # Create a room
    create_room_response = requests.post(
        "http://localhost:8000/rooms",
        json={
            "name": "Test Room",
            "host_id": "player1",
            "max_players": 4
        }
    )
    print("Create Room Response:", create_room_response.json())
    room_id = create_room_response.json()["id"]
    shareable_link = create_room_response.json()["shareable_link"]
    print(f"Shareable Link: {shareable_link}")

    # List rooms
    list_rooms_response = requests.get("http://localhost:8000/rooms")
    print("List Rooms Response:", list_rooms_response.json())

    # Join room using shareable link
    join_via_link_response = requests.get(
        f"{shareable_link}",
        params={"player_id": "player2"}
    )
    print("Join via Link Response:", join_via_link_response.json())

    # Join room using API endpoint
    join_room_response = requests.post(
        f"http://localhost:8000/rooms/{room_id}/join",
        params={"player_id": "player3"}
    )
    print("Join Room Response:", join_room_response.json())

    # Start game
    start_game_response = requests.post(f"http://localhost:8000/rooms/{room_id}/start")
    print("Start Game Response:", start_game_response.json())

    return room_id

# WebSocket testing
async def test_websocket(room_id: str, player_id: str):
    uri = f"ws://localhost:8000/ws/game/{room_id}/{player_id}?screen=lobby"
    async with websockets.connect(uri) as websocket:
        # Receive initial message
        response = await websocket.recv()
        print(f"Initial message: {response}")

        # Send screen transition
        await websocket.send(json.dumps({"screen": "game"}))
        response = await websocket.recv()
        print(f"Game screen message: {response}")

        # Send a game action
        await websocket.send(json.dumps({
            "action": "play_card",
            "card": {"suit": "hearts", "rank": "ace"}
        }))
        response = await websocket.recv()
        print(f"Action response: {response}")

async def main():
    # Test REST API
    room_id = test_rest_api()
    
    # Test WebSocket for two players
    await asyncio.gather(
        test_websocket(room_id, "player1"),
        test_websocket(room_id, "player2")
    )

if __name__ == "__main__":
    asyncio.run(main()) 