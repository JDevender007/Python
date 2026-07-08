from calculator.operations import*
from calculator.validator import is_number
from calculator.history import save, show

operations = {
    "1": ("+", add),
    "2": ("-", subtract),
    "3": ("*", multiply),
    "4": ("/", divide),
    "5": ("%", modulus),
    "6": ("^", power),
}

def display_menu():
    print("\n" + "=" * 35)
    print("PYTHON CLI CALCULATOR")
    print("=" * 35)
    print("1. Addition")
    print("2. Subtraction")
    print("3. Multiplication")
    print("4. Division")
    print("5. Modulus")
    print("6. Power")
    print("7. Show History")
    print("8. Exit")
    print("=" * 35)

def main():
    while True:
        display_menu()
        choice = input("Enter your choice: ").strip()

        if choice == "8":
            print("\nThank you for using Python Calculator!")
            break
        elif choice == "7":
            print("\nCalculation History")
            print("-" * 35)
            print(show())
            continue
        elif choice not in operations:
            print("Invalid choice. Please try again.")
            continue
        first = input("Enter first number: ").strip()
        second = input("Enter second number: ").strip()
        if not is_number(first) or not is_number(second):
            print("Invalid input. Please enter numeric values.")
            continue
        first = float(first)
        second = float(second)
        symbol, function = operations[choice]
        
        try:
            answer = function(first, second)
            record = f"{first} {symbol} {second} = {answer}"
            save(record)
            print("\nResult")
            print("-" * 35)
            print(record)
        except Exception as error:
            print(f"Error: {error}")

if __name__ == "__main__":
    main()