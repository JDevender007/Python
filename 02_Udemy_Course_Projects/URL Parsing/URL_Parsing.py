url = 'https://www.kaggle.com/datasets'

protocol_pos = url.find(":")
dot1 = url.find(".")
dot2 = url.find(".", dot1 + 1)

protocol = url[:protocol_pos]
domain = url[dot1 + 1:dot2]

slash = url.find("/", dot2)
page = url[slash:]

print("Protocol:", protocol)
print("Domain:", domain)
print("Page:", page)