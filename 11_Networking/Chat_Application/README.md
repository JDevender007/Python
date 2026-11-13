<div align="center">

# 💬 Chat Application

### A threaded TCP chat server and client with nicknames, rooms, broadcast messaging, and a member list.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Chat Application is a small rooms-based chat system built on raw TCP sockets. A threaded server accepts multiple clients, each registers a nickname, joins a room, and exchanges newline-delimited messages with everyone else in that room.

It demonstrates socket programming, thread-per-client servers, a simple text protocol, and buffered stream reading.

---

# ✨ Features

- Threaded server supporting many concurrent clients
- Nickname registration with duplicate rejection
- Rooms: join, leave, auto-lobby, per-room broadcast
- `WHO` command returning the current member list
- Clean disconnect handling that frees nicknames and room slots
- Buffered protocol reader (survives messages split across packets)
- Localhost by default
- Demo mode that runs a server and two clients with no input
- 13 passing pytest tests

---

# 📂 Folder Structure

```text
Chat_Application/
│
├── src/
│   ├── main.py         # CLI: demo, server mode, interactive client mode
│   ├── server.py       # ChatServer, Client, protocol handling
│   └── client.py       # ChatClient, background reader, demo
│
├── tests/
│   └── test_chat.py
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 11_Networking/Chat_Application

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: local server + two clients, exchanges messages
python src/main.py --demo

# Terminal 1: start the server
python src/main.py server --port 9000

# Terminal 2: connect
python src/main.py client --port 9000 --nick alice

# Inside the client
hello everyone
/join projects
/who
/leave
/quit
```

---

# 📡 Protocol

Messages are UTF-8, newline-terminated, fields separated by `\x1e`:

| Direction | Message | Meaning |
| --- | --- | --- |
| C → S | `NICK\x1e<name>` | register nickname (first message) |
| S → C | `OK\x1e<name>` / `ERR\x1e<reason>` | handshake result |
| C → S | `MSG\x1e<text>` | chat message to current room |
| C → S | `JOIN\x1e<room>` / `LEAVE` | switch rooms |
| C → S | `WHO` / `QUIT` | member list / disconnect |
| S → C | `MSG\x1e<text>` | broadcast |
| S → C | `LIST\x1e<name\x1fname...>` | member list reply |

---

# 🛠 Technologies

- Python
- socket
- threading
- argparse
- logging

---

# 📚 Concepts Covered

- TCP socket programming (bind, listen, accept)
- Thread-per-client server design
- Application-layer protocol design
- Buffered stream framing with delimiters
- Shared state guarded by locks
- Graceful disconnect and cleanup
- Non-blocking client reads with a reader thread
- Test-driven development with live sockets

---

# ⚠️ Network Use

Binds to `127.0.0.1` by default. Only expose it to networks you own or control — there is no encryption or authentication beyond the nickname.

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**13 tests passed** covering handshake, duplicate nicknames, broadcasting, room isolation, membership, leave/join, disconnect cleanup, unknown commands, and CLI modes.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
