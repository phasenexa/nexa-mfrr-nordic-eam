# Contributing to nexa-mfrr-nordic-eam

Thanks for your interest in contributing. This document covers how to get set up,
the conventions we follow, and the process for getting changes merged.

## Getting started

### Prerequisites

- Python 3.11+
- [Poetry](https://python-poetry.org/docs/#installation) for dependency management
- Make (for common tasks)
- A GitHub account

### Setup

```bash
# Clone the repo
git clone https://github.com/phasenexa/nexa-mfrr-nordic-eam.git
cd nexa-mfrr-nordic-eam

# Install dependencies (including dev extras)
make install

# Verify everything works
make ci
```

### Project structure

```
src/nexa_mfrr_eam/    # library source
tests/                 # test suite
tests/fixtures/        # example XML files and XSD schemas
```

See `CLAUDE.md` for a full breakdown of the code layout and domain context,
including the CIM XML schema details, TSO-specific rules, and implementation order.

## Development workflow

We use **trunk-based development**. The `main` branch is protected and all changes
go through pull requests with squash merges.

### 1. Create a feature branch

```bash
git checkout main && git pull
git checkout -b feat/your-feature-name
```

Branch naming conventions:

| Prefix      | Use for                        |
|-------------|--------------------------------|
| `feat/`     | New features                   |
| `fix/`      | Bug fixes                      |
| `refactor/` | Refactoring (no new behaviour) |
| `docs/`     | Documentation updates          |
| `test/`     | Test improvements              |
| `chore/`    | Maintenance (deps, config)     |

### 2. Make your changes

Write code, write tests. See the code style section below. Commit as you go
with focused, atomic commits.

When implementing a new module, follow the implementation order in `CLAUDE.md`
and update the status table in `README.md` when done.

### 3. Run the checks

Before opening a PR, run the full check suite locally:

```bash
# Everything in one command
make ci

# Or individually:
make lint       # ruff check + format check
make typecheck  # mypy strict
make test       # pytest with coverage
```

### 4. Open a pull request

```bash
git push -u origin feat/your-feature-name
gh pr create --title "feat: short description" --body "Why this change is needed."
```

PR requirements:

- Clear title describing the change
- Description explaining the motivation
- All CI checks pass
- Code coverage meets or exceeds 80%
- At least 1 approving review (when branch protection is enabled)

### 5. After merge

Delete your feature branch. CI handles the rest.

## Code style

### Python conventions

- **Python 3.11+** with type hints on all public API
- **Pydantic v2** for all data models — every bid, document, and time series is a `BaseModel`
- **Ruff** for linting and formatting (handles both lint and format)
- **mypy** in strict mode for type checking
- **Google-style docstrings** on all public classes and methods
- **Fluent builder pattern** for bid and document construction — see `CLAUDE.md` for the design rationale

### Data handling

- **`decimal.Decimal`** for all prices and volumes. Never `float`.
- **Timezone-aware datetimes only**. Never naive. Use `datetime` with `timezone.utc` or `zoneinfo.ZoneInfo`.
- All XML element names follow the XSD, not the implementation guide prose — see `CLAUDE.md` for known discrepancies.

### XML serialization

- Element order in `BidTimeSeries` is mandatory — follow the exact sequence defined in `CLAUDE.md`.
- Both namespace URIs must be handled during deserialization (NBM XSD namespace and Statnett example namespace).
- Use `lxml` for all XML generation and parsing.

### Testing

- **pytest** with descriptive test names
- Example XML files go in `tests/fixtures/` — strip any sensitive data before committing
- Aim for >80% coverage, but prioritise meaningful tests over chasing the number
- XML round-trip tests are required for any serializer/deserializer change: build model → serialize → validate against XSD → deserialize → compare

### Dependencies

Keep them minimal. Core dependencies are:

- `pydantic` for data models
- `lxml` for XML
- `pandas` (optional extra)

Everything else needs a good justification.

## Commit messages

Use conventional commits:

```
feat: add simple bid builder with fluent API
fix: correct element order in BidTimeSeries serializer
refactor: extract TSO validation into strategy objects
docs: document Statnett period shift bid type
test: add XML round-trip test for multipart bids
chore: update lxml to 5.x
```

The first line should be short (under 72 characters). Add a body if the "why"
is not obvious from the title.

## Domain context

This library targets BSP developers connecting to the Nordic mFRR Energy Activation
Market. Key concepts:

- **MTU** — 15-minute Market Time Unit (96 per day, 92/100 on DST transitions)
- **BSP** — Balancing Service Provider (the entity submitting bids)
- **TSO** — Transmission System Operator (Statnett, Fingrid, Energinet, Svenska kraftnat)
- **ECP/EDX** — the messaging infrastructure; this library produces the XML documents that travel over it
- **MARI** — future European platform; the library supports both pre-MARI and post-MARI modes

Read `CLAUDE.md` thoroughly before contributing. The domain rules are non-trivial
and TSO-specific behaviour must be implemented correctly.

## Reporting issues

Open a GitHub issue. Include:

- What you were trying to do
- What happened instead
- Which TSO or document type was involved
- Python version and OS
- Minimal reproduction if possible

## Licence

By contributing, you agree that your contributions will be licensed under
the MIT Licence.
