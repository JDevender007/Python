from __future__ import annotations

import smtplib
import ssl

from email.message import EmailMessage

from src.logger import logger

from src.config import (
    SMTP_SERVER,
    SMTP_PORT,
)


class EmailSender:

    def __init__(self):

        self.server = None

    def connect(
        self,
        email: str,
        password: str,
    ):

        context = ssl.create_default_context()

        self.server = smtplib.SMTP(
            SMTP_SERVER,
            SMTP_PORT,
        )

        self.server.starttls(
            context=context,
        )

        self.server.login(
            email,
            password,
        )

        logger.info("SMTP connection established.")

    def send_email(
        self,
        sender: str,
        recipients: list[str],
        subject: str,
        body: str,
        attachments: list[str] | None = None,
    ):

        message = EmailMessage()

        message["From"] = sender

        message["To"] = ", ".join(recipients)

        message["Subject"] = subject

        message.set_content(body)

        if attachments:

            for file in attachments:

                with open(file, "rb") as attachment:

                    data = attachment.read()

                message.add_attachment(
                    data,
                    maintype="application",
                    subtype="octet-stream",
                    filename=file.split("\\")[-1],
                )

        self.server.send_message(message)

        logger.info(
            "Email sent to %s",
            ", ".join(recipients),
        )

    def disconnect(self):

        if self.server:

            self.server.quit()

            logger.info("SMTP connection closed.")
