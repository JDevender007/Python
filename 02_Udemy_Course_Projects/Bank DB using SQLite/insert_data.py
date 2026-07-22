import sqlite3

conn = sqlite3.connect("bank.db")
cursor = conn.cursor()

cursor.execute("""
INSERT INTO customers VALUES
(110, 'Anil', 'Mumbai', 'anil@gmail.com'),
(111, 'Smith', 'Delhi', 'smith@gmail.com'),
(112, 'Ramesh', 'Mumbai', 'ramesh@gmail.com'),
(113, 'Khan', 'Delhi', 'khan@gmail.com')
""")

cursor.execute("""
INSERT INTO accounts VALUES
(101, 110, 'Savings', 2500.00),
(102, 111, 'Checking', 1200.50),
(103, 112, 'Savings', 1500.00),
(104, 113, 'Checking', 1700.00)
""")

cursor.execute("""
INSERT INTO transactions VALUES
(1001, 101, 'Deposit', 500.00),
(1002, 102, 'Withdrawal', 300.00),
(1003, 103, 'Deposit', 800.00),
(1004, 104, 'Withdrawal', 200.00)
""")

conn.commit()
conn.close()

print("Records inserted successfully.")