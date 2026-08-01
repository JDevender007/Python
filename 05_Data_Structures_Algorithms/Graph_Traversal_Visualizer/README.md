<div align="center">

# 🌐 Graph Traversal Visualizer

### A professional Python desktop application for visualizing graph traversal algorithms through interactive animations.

![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Tkinter](https://img.shields.io/badge/Tkinter-GUI-success?style=for-the-badge)
![Algorithms](https://img.shields.io/badge/Graph-Traversal-blue?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

## 📖 Project Overview

**Graph Traversal Visualizer** is a polished Python desktop application built with Tkinter. It demonstrates how graph traversal algorithms explore connected, undirected graphs through smooth, interactive animations.

Users can build graphs manually, reposition vertices, create weighted edges, generate connected random graphs, choose a start vertex, and visualize Breadth-First Search (BFS) or Depth-First Search (DFS). Live statistics, traversal order, edge animation, complexity information, keyboard shortcuts, responsive layout behavior, and fullscreen support make the application useful for students, educators, and developers.

The project uses only the Python standard library and follows an object-oriented, modular architecture with type hints, docstrings, logging, exception handling, and PEP 8-oriented code.

---

## ✨ Features

### Graph Traversal Algorithms

- Breadth-First Search (BFS)
- Depth-First Search (DFS)
- Deterministic neighbor ordering
- Configurable traversal start node
- Traversal events separated from GUI animation logic

### Interactive Graph Editor

- Add nodes
- Delete nodes
- Move nodes by dragging
- Add weighted edges
- Update existing edge weights
- Delete edges
- Set the traversal start node
- Double-click a node to make it the start node
- Right-click node context actions
- Connected random graph generator
- Clear graph
- Reset the graph to its most recently generated state

### Animation and Visualization

- Smooth node traversal
- Animated edge progress
- Current node highlighting
- Visited node highlighting
- Traversed path highlighting
- Traversal-order badges
- Weighted edge labels
- Pause, resume, stop, and reset controls
- Targeted 60 FPS animation loop
- Responsive normalized node positioning
- Fullscreen support
- Modern dark theme

### Live Statistics

- Current algorithm
- Start node
- Visited node count
- Traversal order
- Execution time
- Graph size
- Number of edges
- Current animation status
- FPS counter

### Complexity Panel

The interface displays:

- Best case
- Average case
- Worst case
- Space complexity

---

## 🛠 Technologies and Practices

- Python 3.13
- Tkinter and ttk
- Object-Oriented Programming
- Modular architecture
- Graph theory
- Event-driven GUI programming
- Type hints
- Docstrings
- Logging with rotating log files
- Exception handling
- Standard-library-only dependencies

---

## 📂 Project Structure

```text
Graph_Traversal_Visualizer/
│
├── assets/
│   └── .gitkeep
│
├── algorithms/
│   ├── __init__.py
│   ├── bfs.py
│   ├── dfs.py
│   ├── graph.py
│   └── traversal_utils.py
│
├── src/
│   ├── __init__.py
│   ├── app.py
│   ├── visualizer.py
│   ├── graph_canvas.py
│   ├── controls.py
│   ├── config.py
│   ├── colors.py
│   ├── complexity.py
│   ├── logger.py
│   └── utils.py
│
├── README.md
├── requirements.txt
└── .gitignore
```

### Module Responsibilities

| Module | Responsibility |
|---|---|
| `algorithms/graph.py` | Undirected weighted graph model and validation |
| `algorithms/bfs.py` | BFS traversal event generator |
| `algorithms/dfs.py` | DFS traversal event generator |
| `algorithms/traversal_utils.py` | Shared traversal events and validation |
| `src/app.py` | Application entry point and top-level error boundary |
| `src/visualizer.py` | Main layout, animation coordinator, statistics, shortcuts |
| `src/graph_canvas.py` | Interactive graph drawing and editing |
| `src/controls.py` | Algorithm, graph, animation, and editor controls |
| `src/config.py` | Typed application configuration |
| `src/colors.py` | Centralized dark-theme palette |
| `src/complexity.py` | Complexity metadata and display panel |
| `src/logger.py` | Console and rotating-file logging |
| `src/utils.py` | Geometry, easing, formatting, and window helpers |

---

## 🚀 Installation

Clone the repository:

```bash
git clone https://github.com/JDevender007/Graph_Traversal_Visualizer.git
cd Graph_Traversal_Visualizer
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Windows:

```bash
.venv\Scripts\activate
```

Activate it on Linux or macOS:

```bash
source .venv/bin/activate
```

Install the project requirements:

```bash
pip install -r requirements.txt
```

No third-party Python packages are required. On some minimal Linux installations, Tkinter must be installed through the operating system package manager. For example, Debian and Ubuntu users may need `python3-tk`.

---

## ▶️ Run Instructions

From the project root, run:

```bash
python -m src.app
```

The direct script form is also supported:

```bash
python src/app.py
```

---

## 🖱️ Using the Graph Editor

1. Select an editor mode from the left panel.
2. In **Add Node** mode, click an empty canvas location.
3. In **Move** mode, drag a node to reposition it.
4. In **Add Edge** mode, click a source node and then a destination node.
5. Set the new-edge weight with the numeric control before creating an edge.
6. In **Delete Node** or **Delete Edge** mode, click the item to remove it.
7. In **Set Start** mode, click the desired traversal start node.
8. A node can also be made the start node by double-clicking it or using its right-click menu.

Randomly generated graphs are connected and contain positive integer edge weights.

---

## 🔎 Traversal Algorithms

### Breadth-First Search

Breadth-First Search explores a graph level by level. It uses a queue to discover all immediate neighbors before progressing to vertices farther from the start node.

Typical uses include:

- Shortest paths in unweighted graphs
- Level-order exploration
- Connectivity checks
- Minimum-hop routing

### Depth-First Search

Depth-First Search follows one branch as far as possible before backtracking. Conceptually, it uses a stack; this implementation uses a generator-backed recursive walk to produce animation events.

Typical uses include:

- Cycle analysis
- Connected-component discovery
- Topological techniques
- Maze and path exploration

Both implementations are independent of Tkinter. They emit typed traversal steps that the GUI consumes, keeping algorithm logic reusable and testable.

---

## 📊 Complexity Analysis

| Algorithm | Best Case | Average Case | Worst Case | Space Complexity |
|---|---:|---:|---:|---:|
| Breadth-First Search | O(V + E) | O(V + E) | O(V + E) | O(V) |
| Depth-First Search | O(V + E) | O(V + E) | O(V + E) | O(V) |

Where:

- **V** is the number of vertices.
- **E** is the number of edges.

For adjacency-list graph representations, every reachable vertex and edge is examined at most a constant number of times.

---

## ⌨️ Keyboard Shortcuts

| Key | Action |
|---|---|
| `Space` | Start traversal |
| `P` | Pause traversal |
| `R` | Resume traversal |
| `S` | Stop traversal |
| `C` | Clear graph |
| `G` | Generate a random graph |
| `F11` | Toggle fullscreen |
| `Escape` | Exit the application |

---

## ⚙️ Configuration

Application defaults are centralized in `src/config.py` and include:

- Initial and minimum window size
- Node radius
- Edge widths
- Canvas padding
- Animation durations
- Speed range
- Target FPS
- Panel dimensions
- Fonts
- Node-count limits
- Default edge weight

Theme colors are centralized in `src/colors.py`.

---

## 🧾 Logging

The application writes informative lifecycle and traversal messages to the console. When the user directory is writable, rotating logs are also stored at:

```text
~/.graph_traversal_visualizer/application.log
```

The log file is capped and rotated automatically.

---

## 🎯 Learning Outcomes

This project demonstrates:

- Graph data structures
- Adjacency-list representation
- Breadth-First Search
- Depth-First Search
- Queue-based and recursive traversal
- Algorithm event generation
- Algorithm animation
- Object-oriented design
- Tkinter GUI development
- Canvas interaction
- Event-driven programming
- Time and space complexity analysis
- Modular Python architecture
- Type-safe application configuration

---

## 📈 Future Improvements

- Dijkstra's shortest-path algorithm
- A* search
- Minimum spanning tree visualization
- Topological sorting
- Strongly connected components
- Directed graph mode
- Graph import and export
- Custom node labels
- Edge-weight editing dialog
- Performance comparison mode
- Light theme and theme switching
- Undo and redo history
- Automated GUI test coverage

---

## 🤝 Contributing

Contributions are welcome.

1. Fork the repository.
2. Create a feature branch.
3. Commit your changes with a descriptive message.
4. Push the branch to your fork.
5. Open a pull request.

Please keep changes modular, typed, documented, and consistent with the existing architecture.

---

## 👨‍💻 Author

**Devender J**

Python Developer | Data Analytics Enthusiast | AI & Machine Learning Learner

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving it a star.

</div>
