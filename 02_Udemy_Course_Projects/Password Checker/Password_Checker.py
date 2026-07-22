pwd1 = 'myPass'
pwd2 = 'myPass'

if pwd1==pwd2:
    print("Password Changed")
elif pwd1.casefold()==pwd2.casefold():
    print("Please check cases and try again")
else:
    print("Password do not match")