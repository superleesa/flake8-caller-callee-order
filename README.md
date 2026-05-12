# flake8-caller-callee-order

This repo includes a flake8 plugin that enforces top-level caller/callee
definition order:

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
CCO001 `main` calls `helper`, but `helper` is defined later at line 5
```

By default, `caller-callee-order = callee-before-caller`, and `CCO001` is
emitted when a top-level function calls another top-level function that is
defined later in the same file. For now it only checks simple function calls
like `helper()`; method and attribute calls like `self.helper()` or
`module.helper()` are ignored. It only orders top-level `def` and `async def`
functions; variables, classes, and other declarations are not checked yet.

To require callers before their callees instead, configure Flake8 with:

```ini
[flake8]
caller-callee-order = caller-before-callee
```

## Development

```sh
uv run pytest
uv run ruff check
uv run ruff format
uv run mypy
```
