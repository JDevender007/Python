<div align="center">

# 🧱 Software Engineering Projects

### Five offline projects on writing Python that survives review: Gang-of-Four patterns with proven contracts, a plugin host with lifecycle hooks and failure isolation, a stdlib toolkit of decorators/generators/context managers, a legacy module refactored into typed Protocols, and a library API with a fluent builder, typed errors and additive versioning.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Stdlib](https://img.shields.io/badge/Runtime-Standard%20Library-lightgrey?style=for-the-badge)
![Projects](https://img.shields.io/badge/Projects-5-success?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

Software engineering is the part of programming that remains after the algorithm works: **how the pieces are allowed to talk to each other.** A pattern is only a pattern if its contract holds; a plugin system is only a plugin system if one bad plugin cannot take down the host; a type annotation is only useful if the runtime agrees with it; and an API only earns "backward compatible" if an old client's fields survive the new response.

This category builds each of those claims as executable code:

- **Design_Patterns_Showcase** implements Singleton, Factory, Observer, Strategy and Decorator with tests that assert each pattern's defining property — one instance, a registry lookup, subscriber isolation during notification, substitutable strategies, and a decorated call order that is observed rather than assumed.
- **Plugin_Architecture** discovers plugins from a directory, reads their metadata, resolves a dependency order, runs the `setup` / `process` / `teardown` hooks, and isolates a failing plugin so the rest of the host keeps working.
- **Pythonic_Toolkit** collects the idioms worth internalising: retry/timeout decorators, context managers for transactional state, generators for lazy pipelines, and class tricks (`__slots__`, `__post_init__`, descriptors) with their guarantees tested.
- **Type_Hints_Refactoring** starts from a permissive legacy module and refactors it into fully annotated, `Protocol`-based code with runtime validation — proving the new interface rejects what the old one silently accepted.
- **Api_Design_Playground** models a small library surface: an immutable record, a fluent query builder, a repository with a typed error hierarchy, and a v1/v2 wire format where v2 is a verified strict superset of v1.

Every project runs on bundled data, finishes its demo in about a second, and **asserts its own claims** — a Singleton whose second constructor call returns the identical object, a plugin with a broken `setup()` reported without aborting the others, and `set(v1) < set(v2)` with every v1 value unchanged.

---

# 🎯 Learning Objectives

- Implement Gang-of-Four patterns in the smallest form that still satisfies the contract
- Distinguish a pattern from a naming convention by testing the property it guarantees
- Design a plugin contract with metadata, capability checks and lifecycle hooks
- Resolve plugin dependencies topologically and detect cycles and missing plugins
- Isolate failures so one broken component does not abort a batch
- Write decorators that preserve metadata and support arguments
- Build re-entrant, exception-safe context managers
- Compose lazy generator pipelines and reason about when work actually happens
- Introduce `Protocol`-based structural typing without inheritance
- Validate typed inputs at runtime at the boundary and keep the core trusting
- Design fluent interfaces that return self and snapshot into immutable values
- Model failures as an exception hierarchy with codes and statuses
- Add API versions additively and prove the superset contract
- Write demos whose cross-checks can fail

---

# 📂 Projects

No. | Project | Description | Status
--: | --- | --- | :---:
01 | Design_Patterns_Showcase | Singleton, Factory, Observer, Strategy and Decorator, each with a runnable example and contract tests. | ✅
02 | Plugin_Architecture | Directory discovery, metadata, dependency ordering, lifecycle hooks and sandboxed failure handling. | ✅
03 | Pythonic_Toolkit | Retry/timeout decorators, transactional context managers, lazy generator pipelines and class idioms. | ✅
04 | Type_Hints_Refactoring | A permissive legacy module refactored into annotated, Protocol-based, runtime-validated code. | ✅
05 | Api_Design_Playground | Immutable records, a fluent query builder, a repository with typed errors, and additive v1/v2 versioning. | ✅

---

# 💡 Concepts Covered

- Creational patterns: Singleton and Factory, and why both need a contract test
- Behavioural patterns: Observer (subscribe/notify/unsubscribe) and Strategy (substitution)
- Structural patterns: Decorator, including stacked decorators and call order
- Plugin discovery, metadata parsing and capability declaration
- Dependency graphs, topological ordering and cycle detection
- Lifecycle hooks (`setup`, `process`, `teardown`) and ordering guarantees
- Failure isolation: catching one plugin's exception, reporting it, continuing
- Decorators with and without arguments, `functools.wraps` and metadata preservation
- Context managers, re-entrancy and exception-safe rollback
- Generators, lazy evaluation and pipeline composition
- `__slots__`, descriptors and validation in `__post_init__`
- Structural typing with `Protocol` and why inheritance is not required
- Runtime validation at a typed boundary versus static-only hints
- Fluent builders, immutable query objects and snapshot semantics
- Exception hierarchies with machine-readable codes and HTTP-ish statuses
- Additive API versioning and the strict-superset guarantee

---

# 📁 Repository Structure

```text
25_Software_Engineering/
│
├── Design_Patterns_Showcase/
├── Plugin_Architecture/
├── Pythonic_Toolkit/
├── Type_Hints_Refactoring/
├── Api_Design_Playground/
│
└── README.md
```

Each project contains:

```text
Project_Name/
├── src/              # main.py + library module(s)
├── tests/            # pytest test suite
├── data/             # bundled deterministic inputs
├── README.md
├── requirements.txt
└── .gitignore
```

`Plugin_Architecture` additionally ships a `plugins/` directory of sample plugins.

---

# 🛠 Technologies

- Python 3 (including `typing.Protocol`, `dataclasses`, `functools`, `contextlib`, `importlib`)
- Standard library only — no runtime dependencies
- pytest

No mypy, no pydantic, no dependency-injection framework, no network access.

---

# 📈 Progress

| Project | Status |
| --- | :---: |
| Design Patterns Showcase | ✅ |
| Plugin Architecture | ✅ |
| Pythonic Toolkit | ✅ |
| Type Hints Refactoring | ✅ |
| API Design Playground | ✅ |

**Completed:** **5 / 5 Projects** · 349 passing tests

---

# ▶️ Quick Start

```bash
cd 25_Software_Engineering/Api_Design_Playground

python src/main.py --demo     # offline, self-checking demo
python -m pytest tests/ -q    # run the tests
```

Each project follows the same shape: `python src/main.py --demo` for a self-checking offline run, `python -m pytest tests/ -q` for the suite. Every demo exits `0`, honours `--quiet`, and prints its cross-checks before `Demo completed successfully.`

---

# 📚 Skills Developed

- Turning design vocabulary into testable guarantees instead of diagrams
- Writing a plugin host that fails one plugin without failing the system
- Choosing between inheritance, protocols and composition, and defending the choice
- Keeping decorator metadata, signatures and exception behaviour intact
- Designing library surfaces that are hard to misuse and easy to version
- Treating error types as part of the API contract, not an afterthought
- Writing 44-145 pytest cases per project, including every error path and CLI flag

---

# 🚀 Key Learning Outcomes

- Implement five core design patterns and prove the property each one promises
- Build a plugin system with discovery, ordering, hooks and failure isolation
- Reach for the right Python idiom — decorator, generator, context manager — deliberately
- Refactor untyped code into annotated, validated, protocol-based code
- Design and version a small API so old clients cannot break

---

# 🔮 Future Enhancements

- Design_Patterns_Showcase: Command and Visitor, with an undo stack
- Plugin_Architecture: asynchronous plugin hooks and per-plugin resource limits
- Pythonic_Toolkit: an `async` retry decorator and structured concurrency examples
- Type_Hints_Refactoring: generate stubs from the typed module and check them with mypy in CI
- Api_Design_Playground: a v3 draft that stays a superset, plus an OpenAPI-style schema export

---

# 🤝 Contributions

Contributions, issues and feature requests are welcome. Feel free to open an issue or submit a pull request.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this category useful, consider giving this repository a star.

</div>
