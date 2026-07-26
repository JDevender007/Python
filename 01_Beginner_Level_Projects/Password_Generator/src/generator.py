import secrets
import string


class PasswordGenerator:
    """Generate secure random passwords."""

    def __init__(self, length: int) -> None:
        self.length = length

    def generate(self) -> str:
        characters = (
            string.ascii_uppercase
            + string.ascii_lowercase
            + string.digits
            + string.punctuation
        )

        password = [secrets.choice(string.ascii_uppercase)]
        password.append(secrets.choice(string.ascii_lowercase))
        password.append(secrets.choice(string.digits))
        password.append(secrets.choice(string.punctuation))

        while len(password) < self.length:
            password.append(secrets.choice(characters))

        secrets.SystemRandom().shuffle(password)

        return "".join(password[: self.length])