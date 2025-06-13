from typing import Dict, Optional, List
from .models import GameState,Card, Player, GameStatus, CardRank
from enum import Enum

class PlayResult(Enum):
    SUCCESS = "success"
    ILLEGAL_CARD = "illegal_card"
    MUST_PICKUP = "must_pickup"
    GAME_OVER = "game_over"

class GameManager:
    def __init__(self):
        self.game_states: Dict[str, GameState] = {}  # Maps room_id to GameState
        

    def create_game_state(self, room_id: str, players: List[Player]) -> GameState:
        game_state = GameState(
            players=players,
            current_player_index=0,
            deck=[],
            discard_pile=[],
            game_status=GameStatus.WAITING,
            room_id=room_id
        )
        self.game_states[room_id] = game_state
        return game_state

    def get_game_state(self, room_id: str) -> Optional[GameState]:
        return self.game_states.get(room_id)
    
    def _update_game_state(self, room_id: str, game_state: GameState) -> bool:
        try:
            self.game_states[room_id] = game_state
            return True
        except KeyError:
            return False
    def _delete_game_state(self, room_id: str) -> bool:
        if room_id in self.game_states:
            del self.game_states[room_id]
            return True
        return False
    def play_card(self, room_id: str, player_id: str, card: Card, source: str = "hand") -> PlayResult:
        """
        Play a card from 'hand' or 'face_up'.
        """
        game_state = self.get_game_state(room_id)
        if game_state.game_status != GameStatus.PLAYING:
            return PlayResult.ILLEGAL_CARD

        player = next((p for p in game_state.players if p.id == player_id), None)
        if not player:
            return PlayResult.ILLEGAL_CARD

        # Select the correct pile
        if source == "hand":
            pile = player.hand
        elif source == "face_up":
            pile = player.face_up
        else:
            return PlayResult.ILLEGAL_CARD

        if card not in pile:
            return PlayResult.ILLEGAL_CARD

        # Check if the played card is legal
        if not self._check_legal_play(card, game_state.discard_pile):
            has_legal = any(
                self._check_legal_play(c, game_state.discard_pile)
                for c in pile
            )
            if has_legal:
                return PlayResult.ILLEGAL_CARD
            else:
                self._pickup_discard_pile(room_id, player_id)
                return PlayResult.MUST_PICKUP

        # Card is legal, play it
        pile.remove(card)
        game_state.discard_pile.append(card)
        self._update_game_state(room_id, game_state)

        # Check for game over
        winner = self._check_game_over(room_id)
        if winner:
            return PlayResult.GAME_OVER

        return PlayResult.SUCCESS

    def play_face_down_card(self, room_id: str, player_id: str, card_index: int) -> PlayResult:
        """
        Reveal and attempt to play a face-down card at the given index.
        """
        game_state = self.get_game_state(room_id)
        if game_state.game_status != GameStatus.PLAYING:
            return PlayResult.ILLEGAL_CARD

        player = next((p for p in game_state.players if p.id == player_id), None)
        if not player or not (0 <= card_index < len(player.face_down)):
            return PlayResult.ILLEGAL_CARD

        # Reveal the chosen face-down card
        card = player.face_down.pop(card_index)

        # Try to play it using the same rules as play_card
        if not self._check_legal_play(card, game_state.discard_pile):
            # If not legal, player must pick up the discard pile and the revealed card goes to their hand
            player.hand.append(card)
            self._pickup_discard_pile(room_id, player_id)
            self._update_game_state(room_id, game_state)
            return PlayResult.MUST_PICKUP

        # Card is legal, play it
        game_state.discard_pile.append(card)
        self._update_game_state(room_id, game_state)

        # Check for game over
        winner = self._check_game_over(room_id)
        if winner:
            return PlayResult.GAME_OVER

        return PlayResult.SUCCESS

    def _check_legal_play(self,card: Card,discard_pile:List) -> bool:
        SPECIAL_RANKS = {CardRank.TWO, CardRank.THREE, CardRank.TEN}
        RANK_ORDER = {
            CardRank.THREE: 3, CardRank.FOUR: 4, CardRank.FIVE: 5, CardRank.SIX: 6,
            CardRank.SEVEN: 7, CardRank.EIGHT: 8, CardRank.NINE: 9, CardRank.TEN: 10,
            CardRank.JACK: 11, CardRank.QUEEN: 12, CardRank.KING: 13, CardRank.ACE: 14, CardRank.TWO: 2
        }

        if card.rank in SPECIAL_RANKS:
            return True
        idx = -1
        while discard_pile and discard_pile[idx].rank == CardRank.THREE:
            idx -= 1
            if abs(idx) > len(discard_pile):
                # All cards are 3s, treat as empty pile
                return True
        top_card = discard_pile[idx] if discard_pile else None
        if not top_card:
            return True

        # 3. If top card is 7, only 7 or lower can be played
        if top_card.rank == CardRank.SEVEN:
            return RANK_ORDER[card.rank] <= RANK_ORDER[CardRank.SEVEN]

        # 4. Otherwise, card must be equal or higher in rank
        return RANK_ORDER[card.rank] >= RANK_ORDER[top_card.rank]
    
    def _draw_card(self, room_id: str, player_id: str) -> bool:
        game_state = self.get_game_state(room_id)

        player = next((p for p in game_state.players if p.id == player_id), None)
        if not player:
            return False

        # Remove the top card from the deck and add to player's hand
        card = game_state.deck.pop(0)  # Assuming deck[0] is the top card
        player.hand.append(card)

        self.update_game_state(room_id, game_state)
        return True
    
    def _pickup_discard_pile(self, room_id: str, player_id: str) -> bool:
        game_state = self.get_game_state(room_id)

        player = next((p for p in game_state.players if p.id == player_id), None)
        if not player or not game_state.discard_pile:
            return False

        # Add the top card from the discard pile to the player's hand
        player.hand.extend(game_state.discard_pile)
        game_state.discard_pile.clear()
        self.update_game_state(room_id, game_state)
        return True
    def _check_game_over(self, room_id: str) -> Optional[str]:
        game_state = self.get_game_state(room_id)
        if not game_state:
            return False

        # Check if any player has no cards left
        for player in game_state.players:
            if not player.hand and not player.face_up and not player.face_down:
                game_state.game_status = GameStatus.GAME_OVER
                self._update_game_state(room_id, game_state)
                return player.id
        return None
    
    def _advance_turn(self, room_id: str):
        """
        Advances the turn to the next player in the room.
        """
        game_state = self.get_game_state(room_id)
        if not game_state or len(game_state.players) == 0:
            return

        # Move to the next player (wrap around if at the end)
        game_state.current_player_index = (game_state.current_player_index + 1) % len(game_state.players)
        self._update_game_state(room_id, game_state)
