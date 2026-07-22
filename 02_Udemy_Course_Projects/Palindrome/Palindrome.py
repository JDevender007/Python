S1 = 'python'

S2 =S1.replace(' ','')

rev =S2[::-1]

if S2.casefold() == rev.casefold():
    print(S1)
else:
    palindrome =S2.casefold()+rev.casefold()
    print(palindrome)
