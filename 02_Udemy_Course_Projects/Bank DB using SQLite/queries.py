import sqlite3

def show_customers():
    conn = sqlite3.connect("bank.db")
    cursor = conn.cursor()
    result = cursor.execute("SELECT * FROM customers")
    for row in result:
        print(row)
    conn.close()

def show_accounts():
    conn = sqlite3.connect("bank.db")
    cursor = conn.cursor()
    result = cursor.execute("""
        SELECT accounts.acc_id, customers.name, accounts.acc_type, accounts.balance
        FROM accounts JOIN customers ON accounts.cust_id = customers.cust_id
    """)

    for row in result:
        print(row)
    conn.close()

def show_transactions():
    conn = sqlite3.connect("bank.db")
    cursor = conn.cursor()
    result = cursor.execute("""
        SELECT * FROM transactions
    """)
    for row in result:
        print(row)
    conn.close()

if __name__ == "__main__":
    print("\nCustomers")
    show_customers()
    print("\nAccounts")
    show_accounts()
    print("\nTransactions")
    show_transactions()