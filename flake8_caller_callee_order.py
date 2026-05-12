from __future__ import annotations

import ast
from enum import Enum
from typing import Any, Dict, Generator, NamedTuple, Type, Union


class CallerCalleeOrder(str, Enum):
    CALLEE_BEFORE_CALLER = "callee-before-caller"
    CALLER_BEFORE_CALLEE = "caller-before-callee"


FunctionNode = Union[ast.FunctionDef, ast.AsyncFunctionDef]
PluginResult = tuple[
    int,
    int,
    str,
    Type["CallerCalleeOrderChecker"],
]


class FunctionCall(NamedTuple):
    name: str
    lineno: int
    col_offset: int


class FunctionCallCollector(ast.NodeVisitor):
    def __init__(self, local_function_names: set[str]) -> None:
        self.local_function_names = local_function_names
        self.calls: set[FunctionCall] = set()

    def visit_Call(self, node: ast.Call) -> None:
        # Handles simple local function calls such as foo(...). Attribute calls
        # like self.foo(...) or module.foo(...) are intentionally ignored.
        if (
            isinstance(node.func, ast.Name)
            and node.func.id in self.local_function_names
        ):
            self.calls.add(
                FunctionCall(
                    name=node.func.id,
                    lineno=node.func.lineno,
                    col_offset=node.func.col_offset,
                )
            )

        self.generic_visit(node)


class CallerCalleeOrderChecker:
    name = "flake8-caller-callee-order"
    version = "0.1.0"
    order = CallerCalleeOrder.CALLEE_BEFORE_CALLER

    @classmethod
    def add_options(cls, option_manager: Any) -> None:
        option_manager.add_option(
            "--caller-callee-order",
            choices=[order.value for order in CallerCalleeOrder],
            default=cls.order.value,
            parse_from_config=True,
            help=(
                "Expected top-level caller/callee definition order: "
                "%(choices)s. (Default: %(default)s)"
            ),
        )

    @classmethod
    def parse_options(cls, options: Any) -> None:
        cls.order = CallerCalleeOrder(options.caller_callee_order)

    def __init__(self, tree: ast.AST, filename: str = "(none)") -> None:
        self.tree = tree
        self.filename = filename

    def run(self) -> Generator[PluginResult, None, None]:
        top_level_functions = self._top_level_functions()
        function_names = set(top_level_functions)

        for caller_name, caller_node in top_level_functions.items():
            collector = FunctionCallCollector(function_names)
            collector.visit(caller_node)

            for call in sorted(collector.calls):
                # NOTE: Skip self-recursive calls, as they don't have a definition order issue.
                if call.name == caller_name:
                    continue

                callee_node = top_level_functions[call.name]
                if self._is_allowed_definition_order(caller_node, callee_node):
                    continue

                relative_position = (
                    "later"
                    if self.order == CallerCalleeOrder.CALLEE_BEFORE_CALLER
                    else "earlier"
                )
                message = (
                    f"CCO001 `{caller_name}` calls `{call.name}`, "
                    f"but `{call.name}` is defined {relative_position} at line "
                    f"{callee_node.lineno}"
                )
                yield call.lineno, call.col_offset, message, type(self)

    def _is_allowed_definition_order(
        self,
        caller_node: FunctionNode,
        callee_node: FunctionNode,
    ) -> bool:
        if self.order == CallerCalleeOrder.CALLEE_BEFORE_CALLER:
            return callee_node.lineno <= caller_node.lineno

        return callee_node.lineno >= caller_node.lineno

    def _top_level_functions(self) -> Dict[str, FunctionNode]:
        if not isinstance(self.tree, ast.Module):
            return {}

        top_level_functions: Dict[str, FunctionNode] = {}

        for node in self.tree.body:
            # TODO: support other top-level variables too
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                top_level_functions[node.name] = node

        return top_level_functions
