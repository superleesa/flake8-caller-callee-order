# Design Notes

This checker is intentionally a small AST-based resolver, not a complete Python
name-resolution engine.

## Code Layout

The flake8 entry point is intentionally thin. `plugin.py` owns option parsing
and flake8 result formatting, while `checker.py` owns the recursive ordering
walk and emits checker-native violations.

The checker delegates local policies to smaller modules:

- `definitions.py` discovers names that can participate in ordering.
- `collectors.py` contains AST visitors for shallow references and local
  shadowing bindings.
- `frames.py` builds scope frames, including method receiver bindings.
- `resolver.py` resolves references through a stack of scope frames.
- `diagnostics.py` formats `CCO001` messages.

## Core Model

The checker separates three concepts:

- **Definitions** are names whose relative order can be checked.
- **Bindings** are names that resolve locally and can hide outer definitions.
- **References** are use sites that may resolve to a definition.

Each checked body creates a scope frame. References are resolved by searching
scope frames from innermost to outermost. A local binding stops lookup, while an
ordered binding resolves to a definition that can be compared against the
containing definition.

## Recursive Bodies

`_check_body` is the recursive entry point. It checks one body, then explicitly
recurses into nested `def`, `async def`, and `class` bodies. Control-flow suites
such as `if`, loops, `with`, `try`, and `match` are traversed without creating a
new scope frame, because they do not create Python lexical scopes.

Reference collection is deliberately shallow at each level. Nested scope bodies
are not flattened into the parent body; they are checked by recursive
`_check_body` calls with their own scope context.

## Method Resolution

Class bodies order direct methods by method name. Method calls are resolved
through the method receiver binding, so names like `self`, `cls`, or a custom
first parameter such as `instance` all work the same way:

```python
class Service:
    def run(instance):
        instance.helper()

    def helper(self):
        pass
```

Static methods do not receive a receiver binding. Class attributes are not
ordered, and class-body bindings are not treated as lexical parents of method
bodies.

## Conservative Deferrals

Some Python features are intentionally left unresolved to avoid false positives:

- arbitrary attribute resolution such as `module.helper`
- receiver aliases such as `other = self`
- `super()`
- class-name-qualified method calls such as `Service.helper(self)`
- lambdas and comprehensions
- `global` and `nonlocal`
- duplicate definitions and ambiguous reassignments
- match-pattern capture bindings

When behavior is ambiguous, the checker should prefer not emitting `CCO001`.
