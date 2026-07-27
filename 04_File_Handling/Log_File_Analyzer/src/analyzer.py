from collections import Counter

from logger import logger

class LogAnalyzer:

    def __init__(self, logs):

        self.logs = logs

        self.counter = Counter()

    def analyze(self):

        for line in self.logs:

            upper = line.upper()

            if "INFO" in upper:
                self.counter["INFO"] += 1

            elif "WARNING" in upper:
                self.counter["WARNING"] += 1

            elif "ERROR" in upper:
                self.counter["ERROR"] += 1

            elif "CRITICAL" in upper:
                self.counter["CRITICAL"] += 1

            else:
                self.counter["UNKNOWN"] += 1

        logger.info("Log analysis completed.")

    def search(self, keyword):

        keyword = keyword.lower()

        return [
            line
            for line in self.logs
            if keyword in line.lower()
        ]

    def summary(self):

        return self.counter