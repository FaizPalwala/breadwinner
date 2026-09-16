# Contributing to Breadwinner

Contributions are welcome. Please follow the instructions below to submit bug fixes, templates, or new profile adapters.

## Getting Started

1. Fork and clone the repository.
2. Create a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e .[dev]
   ```
3. Run tests to ensure everything is green:
   ```bash
   pytest tests/ -v
   ```

## Contribution Areas

### 1. Adding New Templates
New resume templates can be added under `src/breadwinner/templates/resume/`:
- Ensure single-column formatting.
- Include print CSS with `@page { size: A4; margin: 12mm; }`.
- Test against `tests/test_renderer.py`.

### 2. Adding New Personas
Create a new YAML file in `src/breadwinner/personas/<slug>.yaml` defining:
- `name`: Display name.
- `slug`: Command-line identifier.
- `description`: Target role category.
- `tone`: Voice directives.
- `system_directives`: Hard tailoring rules.
- `cover_letter_directives`: Letter structure instructions.

### 3. Adding New Profile Source Adapters
Implement `BaseProfileSource` in `src/breadwinner/core/portfolio.py` to support new CMSs or resume formats (e.g. LinkedIn PDF exports, Hugo, Jekyll).

## Code Style & Testing

- Type hints are required for all core functions.
- Run `pytest` before opening a pull request.
- Keep secrets and personal data out of git commits.
