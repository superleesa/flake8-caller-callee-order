# flake8-caller-callee-order

This repo includes a flake8 plugin that enforces local definition/reference
order:

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
class scopes by method name.

Supported definitions are:

- `def`
- `async def`
- `class`
- assignments like `name = value`
- annotated assignments like `name: type = value`
- imports like `import module` and `from module import name`

For now it checks simple local references like `helper()` or `CONFIG`, plus
method references like `self.helper()` and `cls.helper()` inside classes. Other
attribute references like `module.helper()` are ignored. Class attributes and
definitions inside function bodies are not ordered yet.

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
