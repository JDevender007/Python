from __future__ import annotations

import threading
import time


class BackupScheduler:

    def __init__(self):

        self.running = False

        self.thread = None

    def start(
        self,
        interval,
        callback,
    ):

        if self.running:

            return

        self.running = True

        self.thread = threading.Thread(
            target=self.worker,
            args=(
                interval,
                callback,
            ),
            daemon=True,
        )

        self.thread.start()

    def worker(
        self,
        interval,
        callback,
    ):

        while self.running:

            time.sleep(interval)

            callback()

    def stop(self):

        self.running = False

    def is_running(self):

        return self.running
