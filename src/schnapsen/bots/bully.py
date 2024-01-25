
import random
from typing import Optional
from schnapsen.game import (Bot, PlayerPerspective, Move, SchnapsenTrickScorer,
RegularMove, GameState, GamePlayEngine)
from schnapsen.deck import Card, Suit
from schnapsen.bots import RandBot
from schnapsen.bots.rdeep import FirstFixedMoveThenBaseBot



class BullyBot(Bot):
    def __init__(self, rand: random.Random, name: Optional[str] = None) -> None:
        super().__init__(name)
        self.rand = rand

    def __repr__(self) -> str:
        return f"BullyBot(rand={self.rand})"

    def get_move(self, perspective: PlayerPerspective, leader_move: Optional[Move], ) -> Move:
        my_valid_moves = perspective.valid_moves()
        trump_suit_moves: list[Move] = []

        trump_suit: Suit = perspective.get_trump_suit()

        for move in my_valid_moves:
            cards_of_move: list[Card] = move.cards
            card_of_move: Card = cards_of_move[0]

            if card_of_move.suit == trump_suit:
                trump_suit_moves.append(move)

        if len(trump_suit_moves) > 0:
            random_trump_suit_move = self.rand.choice(trump_suit_moves)
            return random_trump_suit_move

        if not perspective.am_i_leader():
            assert leader_move is not None
            leader_suit: Suit = leader_move.cards[0].suit
            leaders_suit_moves: list[Move] = []

            for move in my_valid_moves:
                cards_of_move = move.cards
                card_of_move = cards_of_move[0]

                if card_of_move.suit == leader_suit:
                    leaders_suit_moves.append(move)

            if len(leaders_suit_moves) > 0:
                random_leader_suit_move = self.rand.choice(leaders_suit_moves)
                return random_leader_suit_move

        my_hand_cards: list[Card] = perspective.get_hand().cards

        schnapsen_trick_scorer = SchnapsenTrickScorer()

        highest_card_score: int = -1
        card_with_highest_score: Optional[Card] = None
        for card in my_hand_cards:
            card_score = schnapsen_trick_scorer.rank_to_points(card.rank)
            if card_score > highest_card_score:
                highest_card_score = card_score
                card_with_highest_score = card

        assert card_with_highest_score is not None

        move_of_card_with_highest_score = RegularMove(card_with_highest_score)

        assert move_of_card_with_highest_score in my_valid_moves

        return move_of_card_with_highest_score

# class BullyBot

class RdeepBullyBot(Bot):
    """
    An RdeepBot that is biased toward aggressiveness when it plays and assume
    randoness for the opponent.
    """

    def __init__(self,
                 num_samples: int,
                 depth: int,
                 rand: random.Random,
                 name: Optional[str] = None,
                 aggressiveness: Optional[float] = 1.0) -> None:
        """
        Create a new rdeep bully bot.

        :param num_samples: how many samples to take per move
        :param depth: how deep to sample
        :param rand: the source of randomness for this Bot
        :param name: the name of this Bot
        :param aggressiveness: the probability to choose the bully strategy.
        """
        assert num_samples >= 1, f"we cannot work with less than one sample, got {num_samples}"
        assert depth >= 1, f"it does not make sense to use a dept <1. got {depth}"
        super().__init__(name)
        self.__num_samples = num_samples
        self.__depth = depth
        self.__rand = rand
        self._bully_prob: float = aggressiveness
        self.bully_counter: int = 0  # number of times it uses BullyBot
        self.rand_counter: int = 0  # number of times it uses RandBot
    # __init__


    # copied from RdeepBot because the __evaluate is private
    def get_move(self, perspective: PlayerPerspective, leader_move: Optional[Move]) -> Move:
        # get the list of valid moves, and shuffle it such
        # that we get a random move of the highest scoring
        # ones if there are multiple highest scoring moves.
        moves = perspective.valid_moves()
        self.__rand.shuffle(moves)

        best_score = float('-inf')
        best_move = None
        for move in moves:
            sum_of_scores = 0.0
            for _ in range(self.__num_samples):
                gamestate = perspective.make_assumption(leader_move=leader_move, rand=self.__rand)
                score = self.__evaluate(gamestate, perspective.get_engine(), leader_move, move)
                sum_of_scores += score
            average_score = sum_of_scores / self.__num_samples
            if average_score > best_score:
                best_score = average_score
                best_move = move
        assert best_move is not None
        return best_move

    # get_move

    def __evaluate(self, gamestate: GameState, engine: GamePlayEngine, leader_move: Optional[Move], my_move: Move) -> float:
        """
        Evaluates the value of the given state for the given player
        :param state: The state to evaluate
        :param player: The player for whom to evaluate this state (1 or 2)
        :return: A float representing the value of this state for the given player. The higher the value, the better the
                state is for the player.
        """

        # Code from RdeepBot, with changes in choosing the next bot.
        me: Bot
        leader_bot: Bot
        follower_bot: Bot

        # use less in order to have no chance to have BullyBot when prob is 0
        bully: bool = self.__rand.random() < self._bully_prob
        me_bot: Bot = BullyBot(rand=self.__rand) if bully else RandBot(rand=self.__rand)

        # update counters
        if bully:
            self.bully_counter += 1
        else:
            self.rand_counter += 1

        # Simulation
        if leader_move:
            # we know what the other bot played
            leader_bot = FirstFixedMoveThenBaseBot(RandBot(rand=self.__rand), leader_move)
            # I am the follower
            me = follower_bot = FirstFixedMoveThenBaseBot(me_bot, my_move)
        else:
            # I am the leader bot
            me = leader_bot = FirstFixedMoveThenBaseBot(me_bot, my_move)
            # We assume the other bot just random
            follower_bot = RandBot(self.__rand)

        new_game_state, _ = engine.play_at_most_n_tricks(game_state=gamestate, new_leader=leader_bot, new_follower=follower_bot, n=self.__depth)

        if new_game_state.leader.implementation is me:
            my_score = new_game_state.leader.score.direct_points
            opponent_score = new_game_state.follower.score.direct_points
        else:
            my_score = new_game_state.follower.score.direct_points
            opponent_score = new_game_state.leader.score.direct_points

        heuristic = my_score / (my_score + opponent_score)
        return heuristic
    # __evaluate

