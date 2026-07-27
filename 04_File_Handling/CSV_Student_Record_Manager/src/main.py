from colorama import Fore
from colorama import Style
from colorama import init

from student_manager import StudentManager
from report import ReportGenerator

init(autoreset=True)

def banner():

    print(Fore.CYAN + "=" * 60)
    print("         CSV STUDENT RECORD MANAGER")
    print("=" * 60 + Style.RESET_ALL)

def menu():

    print("\n1. Add Student")
    print("2. View Students")
    print("3. Search Student")
    print("4. Update Student")
    print("5. Delete Student")
    print("6. Sort By Name")
    print("7. Sort By Marks")
    print("8. Average Marks")
    print("9. Generate Report")
    print("0. Exit")

def main():

    manager = StudentManager()

    banner()

    while True:

        menu()

        choice = input("\nEnter Choice : ")

        if choice == "1":

            manager.add_student()

        elif choice == "2":

            manager.view_students()

        elif choice == "3":

            manager.search_student()

        elif choice == "4":

            manager.update_student()

        elif choice == "5":

            manager.delete_student()

        elif choice == "6":

            manager.sort_by_name()

        elif choice == "7":

            manager.sort_by_marks()

        elif choice == "8":

            manager.average_marks()

        elif choice == "9":

            ReportGenerator().generate(
                manager.load_students()
            )

        elif choice == "0":

            print("\nThank you for using Student Record Manager.")

            break

        else:

            print("Invalid Choice.")

if __name__ == "__main__":

    main()