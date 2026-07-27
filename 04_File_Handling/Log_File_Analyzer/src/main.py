from colorama import Fore
from colorama import Style
from colorama import init
from tabulate import tabulate

from analyzer import LogAnalyzer
from log_parser import LogParser
from report import ReportGenerator

init(autoreset=True)

def banner():

    print(Fore.CYAN + "=" * 60)
    print("             LOG FILE ANALYZER")
    print("=" * 60 + Style.RESET_ALL)

def main():

    banner()

    parser = LogParser()

    logs = parser.load_logs()

    if not logs:

        print("No log files found.")

        return

    analyzer = LogAnalyzer(logs)

    analyzer.analyze()

    summary = analyzer.summary()

    table = [
        [level, count]
        for level, count in summary.items()
    ]

    print()

    print(
        tabulate(
            table,
            headers=["Level", "Count"],
            tablefmt="grid"
        )
    )

    keyword = input("\nEnter keyword to search (Press Enter to skip): ").strip()

    if keyword:

        results = analyzer.search(keyword)

        print(f"\nFound {len(results)} matching log entries:\n")

        for line in results:

            print(line)

    ReportGenerator().generate(summary)


if __name__ == "__main__":
    main()