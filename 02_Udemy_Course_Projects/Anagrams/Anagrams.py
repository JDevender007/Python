S1 = 'snooze alarms'
S2 = "alas, no more Z's"

S1 = S1.lower()
S2 = S2.lower()

for i in S1:
    if i.isalpha():
        if S1.count(i)!=S2.count(i):
            print("Not Anagrams")
            break
else:
    print('Anagrams')
