from Book_Manager import *
def show_menu():
  while True:
    print('library management system')
    print('1. Add a book')
    print('2. View all books')
    print('3. Search a book')
    print('4. delete a book')
    print('5. exit')
    choice = int(input('Enter your choice: '))
    if choice == 1:
      add_book()
    elif choice == 2:
      view_books()
    elif choice == 3:
      search_book()
    elif choice == 4:
      delete_book()
    elif choice == 5:
      break
    else:
      print('Invalid choice')
    input('Press Enter to continue...')
if __name__ == '__main__':
  show_menu()
  