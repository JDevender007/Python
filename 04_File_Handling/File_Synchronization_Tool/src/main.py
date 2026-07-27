from colorama import Fore
from colorama import Style
from colorama import init

from synchronizer import FileSynchronizer
from report import ReportGenerator

init(autoreset=True)

def banner():

    print(Fore.CYAN + "=" * 60)
    print("        FILE SYNCHRONIZATION TOOL")
    print("=" * 60 + Style.RESET_ALL)

def main():

    banner()

    synchronizer = FileSynchronizer()

    synchronizer.synchronize()

    report = ReportGenerator()

    report.generate(synchronizer)

if __name__ == "__main__":
    main()