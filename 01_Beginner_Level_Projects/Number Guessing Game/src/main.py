"""
main.py

Entry point of the Number Guessing Game.
"""

from game import NumberGuessingGame
from validator import InputValidator
from score import ScoreManager
from statistics import StatisticsManager
from utils import Console


def main():

    Console.clear()
    Console.title("NUMBER GUESSING GAME")

    difficulty = InputValidator.get_menu_choice()

    if difficulty == 1:
        minimum = 1
        maximum = 50
        name = "Easy"

    elif difficulty == 2:
        minimum = 1
        maximum = 100
        name = "Medium"

    else:
        minimum = 1
        maximum = 500
        name = "Hard"

    game = NumberGuessingGame(
        minimum,
        maximum,
    )

    attempts = 0

    while True:

        guess = InputValidator.get_guess(
            minimum,
            maximum,
        )

        attempts += 1

        result = game.check_guess(
            guess,
        )

        if result == "high":

            Console.info("Too High!")

        elif result == "low":

            Console.info("Too Low!")

        else:

            Console.success("Correct!")

            print(f"\nYou guessed the number in {attempts} attempts.")

            best = ScoreManager.load_best_score()

            if ScoreManager.save_best_score(attempts):

                Console.success("New Best Score!")

            else:

                print(f"\nBest Score: {best}")

            StatisticsManager.save(
                name,
                attempts,
                game.reveal(),
            )

            break


if __name__ == "__main__":
    main()