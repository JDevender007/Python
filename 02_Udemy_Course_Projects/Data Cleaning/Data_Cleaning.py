scan = 'These+notes#reveal9Newton seeking-out an{underlying structure to/the\pyramid}'
clean = ''

for i in scan:
    if i.isalpha or i.isspace():
        clean=clean+i
    else:
        clean=clean+1
        
print(clean)
