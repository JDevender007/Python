<div align="center">

# 🗺️ Pathfinding Visualizer

### A polished Python desktop application for exploring graph traversal and shortest-path algorithms through interactive grid animations.

![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Tkinter](https://img.shields.io/badge/Tkinter-GUI-success?style=for-the-badge)
![Algorithms](https://img.shields.io/badge/Pathfinding-5%20Algorithms-blue?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Production%20Ready-success?style=for-the-badge)

</div>

---

## 📖 Project Overview

**Pathfinding Visualizer** is a Python 3.13 desktop application built with Tkinter. It demonstrates how common graph-search algorithms explore an unweighted two-dimensional grid and construct a route from a start node to an end node.

The interface is designed for learning, experimentation, and algorithm comparison. Users can draw obstacles, move endpoints, generate guaranteed-solvable random mazes, tune grid density and animation speed, and inspect live execution statistics and complexity information.

## ✨ Features

### Algorithms

- A* Search with Manhattan-distance heuristic
- Dijkstra's Algorithm
- Breadth-First Search (BFS)
- Depth-First Search (DFS)
- Greedy Best-First Search

### Interactive Grid

- Place or drag the start node
- Place or drag the destination node
- Left-click and drag to draw walls
- Right-click and drag to erase walls or endpoints
- Generate random mazes with a guaranteed open route
- Clear only the visualization or clear the complete grid
- Reset to default endpoint positions
- Resize the grid dynamically

### Visualization and Interface

- Smooth event-driven animation up to 60 FPS
- Separate visited-node and final-path animation phases
- Pause, resume, stop, clear, and reset controls
- Responsive resizable window
- Native fullscreen support
- Modern dark theme
- Scrollable control panel for smaller displays
- Live FPS counter
- Centralized logging with rotating log files

### Live Statistics

- Current algorithm
- Visited node count
- Path length
- Algorithm execution time
- Grid dimensions
- Current application status
- Animation FPS

### Complexity Panel

For the selected algorithm, the application displays:

- Best case
- Average case
- Worst case
- Space complexity
- A concise algorithm-specific note

## 🛠️ Technologies and Design

- Python 3.13
- Tkinter and ttk
- Object-oriented programming
- Modular architecture
- PEP 8-compatible formatting
- Type hints and docstrings
- Standard-library logging
- Defensive exception handling
- No third-party runtime dependencies

## 📂 Project Structure

```text
Pathfinding_Visualizer/
│
├── assets/
│   └── .gitkeep
│
├── algorithms/
│   ├── __init__.py
│   ├── astar.py
│   ├── dijkstra.py
│   ├── bfs.py
│   ├── dfs.py
│   └── greedy_best_first.py
│
├── src/
│   ├── __init__.py
│   ├── app.py
│   ├── grid.py
│   ├── node.py
│   ├── visualizer.py
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

## 🚀 Installation

### 1. Clone the repository

```bash
git clone https://github.com/JDevender007/Pathfinding_Visualizer.git
cd Pathfinding_Visualizer
```

### 2. Create a virtual environment

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

### 3. Install requirements

```bash
pip install -r requirements.txt
```

The project has no third-party Python dependencies. On Linux, Tkinter may need to be installed through the system package manager. For example, Debian- or Ubuntu-based systems commonly use `sudo apt install python3-tk`.

## ▶️ Run Instructions

From the project root, run:

```bash
python -m src.app
```

Direct script execution is also supported:

```bash
python src/app.py
```

## 🧭 How to Use

1. Choose an algorithm from the control panel.
2. Keep the default start and end nodes, or drag them to new cells.
3. Draw walls with the left mouse button. Erase with the right mouse button.
4. Adjust the grid size and animation speed sliders.
5. Select **Start visualization** or press **Space**.
6. Pause, resume, or stop the animation as needed.
7. Inspect the live statistics and complexity panel.

## 🧠 Algorithms

### A* Search

A* combines the exact cost from the start with a Manhattan-distance estimate to the destination. On this four-directional grid, the heuristic is admissible and consistent, so A* returns a shortest path while often exploring fewer nodes than uninformed searches.

### Dijkstra's Algorithm

Dijkstra expands the lowest known path cost first. Since every grid movement costs one unit, it guarantees a shortest path and provides a useful comparison with BFS and A*.

### Breadth-First Search

BFS explores the grid level by level using a queue. It guarantees a shortest path in an unweighted grid.

### Depth-First Search

DFS explores one branch deeply before backtracking. It can find a valid path but does not guarantee that the path is shortest.

### Greedy Best-First Search

Greedy Best-First Search prioritizes the node with the smallest heuristic distance to the destination. It often moves toward the target quickly but is neither complete in every graph formulation nor guaranteed to produce an optimal route. In this finite implementation, discovered nodes are tracked to prevent repeated exploration.

## 📊 Complexity Analysis

Let `V` be the number of traversable grid nodes and `E` the number of connections between neighboring nodes.

| Algorithm | Best Case | Average Case | Worst Case | Space |
|---|---:|---:|---:|---:|
| A* Search | O(1) | Heuristic-dependent | O((V + E) log V) | O(V) |
| Dijkstra | O(1) | O((V + E) log V) | O((V + E) log V) | O(V) |
| Breadth-First Search | O(1) | O(V + E) | O(V + E) | O(V) |
| Depth-First Search | O(1) | O(V + E) | O(V + E) | O(V) |
| Greedy Best-First Search | O(1) | Heuristic-dependent | O((V + E) log V) | O(V) |

The exact number of visited nodes depends on wall placement, endpoint positions, neighbor ordering, and heuristic guidance.

## ⌨️ Keyboard Shortcuts

| Key | Action |
|---|---|
| `Space` | Start visualization |
| `P` | Pause |
| `R` | Resume |
| `S` | Stop |
| `C` | Clear grid |
| `M` | Generate random maze |
| `F11` | Toggle fullscreen |
| `Escape` | Exit |

## 🧱 Architecture

The application separates responsibilities across focused modules:

- `src.node` defines individual grid cells and their visual states.
- `src.grid` owns topology, endpoints, walls, maze generation, and neighbor access.
- `algorithms` contains independent search implementations returning a shared immutable result type.
- `src.visualizer` handles drawing, mouse interaction, and Tkinter's non-blocking animation loop.
- `src.controls` owns controls, statistics, complexity information, and visual tuning.
- `src.app` coordinates application state and user actions.
- `src.logger`, `src.config`, `src.colors`, and `src.utils` provide reusable infrastructure.

This dependency direction avoids circular imports and keeps algorithm code independent from the graphical interface.

## 📝 Logging

At runtime, logs are written to:

```text
logs/pathfinding_visualizer.log
```

The file rotates automatically after reaching approximately 1 MB, with three backups retained. If file logging is unavailable, console logging remains active.

## 📈 Future Improvements

- Bidirectional search
- Jump Point Search
- Theta*
- Weighted terrain
- Optional diagonal movement
- Recursive-division and Prim-style maze generators
- Hexagonal grids
- Side-by-side performance comparison mode
- Import and export of grid layouts
- Theme switching
- Screenshot and animation export
- Automated GUI tests

## 🤝 Contributing

Contributions are welcome.

1. Fork the repository.
2. Create a feature branch.
3. Commit focused changes with descriptive messages.
4. Push the branch to your fork.
5. Open a pull request describing the behavior and validation performed.

## 👨‍💻 Author

**Devender J**  
Python Developer | Data Analytics Enthusiast | AI & Machine Learning Learner  
GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If this project helped you understand pathfinding, consider giving the repository a star.

</div>
