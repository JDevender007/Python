from colorama import Fore, Style, init

from organizer import FileOrganizer

init(autoreset=True)

def banner():

    print(Fore.CYAN + "=" * 50)
    print("         FILE ORGANIZER")
    print("=" * 50 + Style.RESET_ALL)

def main():

    banner()

    organizer = FileOrganizer()
    organizer.organize()

if __name__ == "__main__":
    main()