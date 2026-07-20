from __future__ import annotations

from .models import CallerCalleeOrder, Definition, Reference


def is_allowed_definition_order(
    order: CallerCalleeOrder,
    containing_definition: Definition,
    callee_definition: Definition,
) -> bool:
    if order == CallerCalleeOrder.CALLEE_BEFORE_CALLER:
        return callee_definition.lineno <= containing_definition.lineno

    return callee_definition.lineno >= containing_definition.lineno


def format_order_violation(
    order: CallerCalleeOrder,
    containing_definition: Definition,
    callee_definition: Definition,
    reference: Reference,
) -> str:
    relative_position = (
        "later" if order == CallerCalleeOrder.CALLEE_BEFORE_CALLER else "earlier"
    )
    return (
        f"CCO001 `{containing_definition.name}` references "
        f"`{reference.name}`, but `{reference.name}` is defined "
        f"{relative_position} at line {callee_definition.lineno}"
    )
