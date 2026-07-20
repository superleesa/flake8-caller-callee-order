# flake8-caller-callee-order

This repo includes a flake8 plugin that enforces local definition/reference
order:

## Installation

```sh
pip install flake8-caller-callee-order
```

## Usage

```sh
uv run flake8 path/to/file.py
```

For example, with the default `callee-before-caller` order, this is reported:

```python
def main():
    helper()


def helper():
    print("helper")
```

```text
CCO001 `main` references `helper`, but `helper` is defined later at line 5
```

By default, `caller-callee-order = callee-before-caller`, and `CCO001` is
emitted when a local definition references another local definition that is
defined later in the same module scope. It also checks method references within
class scopes by method name, and it recursively checks nested definitions inside
functions and classes.

Supported definitions are:

- `def`
- `async def`
- `class`
- assignments like `name = value`
- annotated assignments like `name: type = value`
- imports like `import module` and `from module import name`

For now it checks simple local references like `helper()` or `CONFIG`, plus
method references like `self.helper()` and `cls.helper()` inside classes.
Attribute bases are still checked when they are local definitions, so
`Service.make()` can report a later-defined `Service`, but arbitrary attribute
resolution such as `module.helper` is not resolved to imported module members.
Class attributes are not ordered yet.

Nested function scopes check nested `def`, `async def`, and `class`
definitions. Local bindings such as arguments, assignments, imports, loop
targets, context-manager targets, exception names, walrus targets, and augmented
assignment targets are treated as local names so they do not produce false
positives against outer definitions.

Lambdas and comprehensions are skipped conservatively until their binding scopes
are modeled.

See [DESIGN.md](DESIGN.md) for the resolver design and intentionally deferred
edge cases.

To require callers before their callees instead, configure Flake8 with:

```ini
[flake8]
caller-callee-order = caller-before-callee
```

## Development

```sh
uv run flake8 .
uv run pytest
uv run ruff check
uv run ruff format
uv run mypy
```
