from pathlib import Path
H=Path("history.txt")
def save(r):
    with H.open("a") as f:f.write(r+"\n")
def show():
    return H.read_text() if H.exists() else "No history."
