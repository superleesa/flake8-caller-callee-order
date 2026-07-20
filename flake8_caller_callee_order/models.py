from __future__ import annotations

import ast
from enum import Enum
from typing import NamedTuple


class CallerCalleeOrder(str, Enum):
    CALLEE_BEFORE_CALLER = "callee-before-caller"
    CALLER_BEFORE_CALLEE = "caller-before-callee"


class BodyCheckMode(str, Enum):
    MODULE = "module"
    CLASS_BODY = "class-body"
    FUNCTION_BODY = "function-body"


class BindingKind(str, Enum):
    ORDERED = "ordered"
    SHADOW = "shadow"
    RECEIVER = "receiver"


class Definition(NamedTuple):
    name: str
    node: ast.stmt
    lineno: int
    col_offset: int


class Reference(NamedTuple):
    name: str
    lineno: int
    col_offset: int
    base_name: str | None = None


class Binding(NamedTuple):
    kind: BindingKind
    definition: Definition | None = None
    receiver_namespace: dict[str, Definition] | None = None


class ScopeFrame(NamedTuple):
    bindings: dict[str, Binding]


class Violation(NamedTuple):
    lineno: int
    col_offset: int
    message: str


ResolutionContext = tuple[ScopeFrame, ...]
