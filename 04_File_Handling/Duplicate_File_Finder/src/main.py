from colorama import Fore, Style, init

from duplicate_finder import DuplicateFinder
from report import ReportGenerator

init(autoreset=True)

def banner():

    print(Fore.CYAN + "=" * 60)
    print("          DUPLICATE FILE FINDER")
    print("=" * 60 + Style.RESET_ALL)

def main():

    banner()

    finder = DuplicateFinder()

    finder.scan_files()

    finder.display_duplicates()

    report = ReportGenerator()

    report.generate(finder)

if __name__ == "__main__":
    main()