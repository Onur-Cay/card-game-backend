import random
from .models import Card
from .game_manager import GameManager, PlayResult

class SimpleBot:
    def __init__(self, game_manager: GameManager):
        self.game_manager = game_manager

    def is_bot(self, player) -> bool:
        # You can set a flag on Player model (recommended), or use a naming convention as fallback
        return getattr(player, "is_bot", False) or player.name.startswith("Bot ")

    def take_turn(self, room_id: str, player_id: str):
        game_state = self.game_manager.get_game_state(room_id)
        player = next((p for p in game_state.players if p.id == player_id), None)
        if not player:
            return

        # 1. Try to play a random legal card from hand
        legal_hand = [card for card in player.hand if self.game_manager._check_legal_play(card, game_state.discard_pile)]
        if legal_hand:
            card = random.choice(legal_hand)
            self.game_manager.play_card(room_id, player_id, card, source="hand")
            return

        # 2. Try to play a random legal card from face_up
        legal_face_up = [card for card in player.face_up if self.game_manager._check_legal_play(card, game_state.discard_pile)]
        if legal_face_up:
            card = random.choice(legal_face_up)
            self.game_manager.play_card(room_id, player_id, card, source="face_up")
            return

        # 3. Play a random face down card (bot does not know which is which)
        if player.face_down:
            card_index = random.randrange(len(player.face_down))
            self.game_manager.play_face_down_card(room_id, player_id, card_index)
            return

        # If no moves possible, do nothing (should not happen in a well-designed game)



