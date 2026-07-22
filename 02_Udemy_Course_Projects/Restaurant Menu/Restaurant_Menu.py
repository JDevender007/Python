n=int(input())
for i in range(n):
  dish=input()
  price=int(input())
  dash=20-len(dish)-len(str(price))
  print(dish+('-'*dash)+"$"+str(price))