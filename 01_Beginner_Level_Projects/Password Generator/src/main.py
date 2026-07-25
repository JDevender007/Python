from generator import PasswordGenerator
from validator import InputValidator
from strength import PasswordStrength
from history import PasswordHistory
from clipboard import ClipboardManager
from utils import Console


def main() -> None:

    Console.clear()
    Console.title("PASSWORD GENERATOR")

    try:
        length = InputValidator.get_password_length()

        generator = PasswordGenerator(length)

        password = generator.generate()

        score, rating = PasswordStrength.calculate(password)

        PasswordHistory.save(password)

        Console.line()

        print(f"Generated Password : {password}")
        print(f"Password Length    : {len(password)}")
        print(f"Strength Score     : {score}/6")
        print(f"Strength Rating    : {rating}")

        Console.line()

        if ClipboardManager.copy(password):
            Console.success("Password copied to clipboard.")
        else:
            Console.error("Unable to copy password.")

    except Exception as error:
        Console.error(str(error))


if __name__ == "__main__":
    main()