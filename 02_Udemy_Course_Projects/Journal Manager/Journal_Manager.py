filename = 'journal.txt'
def write_entry():
    entry = input('Enter your entry: ')
    with open(filename, 'a') as file:
        file.write(entry + '\n')
    print('Entry added successfully')

def read_entries():
    with open(filename, 'r') as file:
        print(file.read())

def search_entry():
    search = input('Enter the search term: ')
    with open(filename, 'r') as file:
        for line in file:
            if search in line:
                print(line)
    else:
        print('No entries found')

def exit_program():
    print('Exiting...')
    exit()

def main_menu():
    print('\n===== File Journal Manager =====')
    print('1. Add Entry')
    print('2. Read all Entries')
    print('3. Search an Entry')
    print('4. Exit')
    
    choice = int(input('Enter your choice: '))

    if choice == 1:
        write_entry()
    elif choice == 2:
        read_entries()
    elif choice == 3:
        search_entry()
    elif choice == 4:
        print('Exiting...')
        break
    else:
        print('Invalid choice')
if __name__ == '__main__':
    main_menu()
