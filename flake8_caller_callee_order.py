from __future__ import annotations

import ast
from enum import Enum
from typing import Any, Generator, NamedTuple, Type


class CallerCalleeOrder(str, Enum):
    CALLEE_BEFORE_CALLER = "callee-before-caller"
    CALLER_BEFORE_CALLEE = "caller-before-callee"


PluginResult = tuple[
    int,
    int,
    str,
    Type["CallerCalleeOrderChecker"],
]


class Definition(NamedTuple):
    name: str
    node: ast.stmt
    lineno: int
    col_offset: int


class NameReference(NamedTuple):
    name: str
    lineno: int
    col_offset: int


class NameReferenceCollector(ast.NodeVisitor):
    def __init__(
        self,
        local_names: set[str],
        *,
        attribute_base_names: set[str] | None = None,
    ) -> None:
        self.local_names = local_names
        self.attribute_base_names = attribute_base_names or set()
        self.references: set[NameReference] = set()

    def _visit_function_signature(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> None:
        for decorator in node.decorator_list:
            self.visit(decorator)
        self.visit(node.args)
        if node.returns is not None:
            self.visit(node.returns)

    def visit_Name(self, node: ast.Name) -> None:
        # Handles simple local references such as foo or foo(...). Attribute
        # references like self.foo or module.foo are intentionally ignored.
        if isinstance(node.ctx, ast.Load) and node.id in self.local_names:
            self.references.add(
                NameReference(
                    name=node.id,
                    lineno=node.lineno,
                    col_offset=node.col_offset,
                )
            )

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if (
            isinstance(node.ctx, ast.Load)
            and isinstance(node.value, ast.Name)
            and node.value.id in self.attribute_base_names
            and node.attr in self.local_names
        ):
            self.references.add(
                NameReference(
                    name=node.attr,
                    lineno=node.lineno,
                    col_offset=node.col_offset,
                )
            )

        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function_signature(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function_signature(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        for decorator in node.decorator_list:
            self.visit(decorator)
        for base in node.bases:
            self.visit(base)
        for keyword in node.keywords:
            self.visit(keyword)


class CallerCalleeOrderChecker:
    name = "flake8-caller-callee-order"
    version = "0.1.1"
    order = CallerCalleeOrder.CALLEE_BEFORE_CALLER

    @classmethod
    def add_options(cls, option_manager: Any) -> None:
        option_manager.add_option(
            "--caller-callee-order",
            choices=[order.value for order in CallerCalleeOrder],
            default=cls.order.value,
            parse_from_config=True,
            help=(
                "Expected local definition/reference order: "
                "%(choices)s. (Default: %(default)s)"
            ),
        )

    @classmethod
    def parse_options(cls, options: Any) -> None:
        cls.order = CallerCalleeOrder(options.caller_callee_order)

    def __init__(self, tree: ast.AST, filename: str = "(none)") -> None:
        self.tree = tree
        self.filename = filename

    def _is_allowed_definition_order(
        self,
        containing_definition: Definition,
        callee_definition: Definition,
    ) -> bool:
        if self.order == CallerCalleeOrder.CALLEE_BEFORE_CALLER:
            return callee_definition.lineno <= containing_definition.lineno

        return callee_definition.lineno >= containing_definition.lineno

    def _target_names(
        self,
        target: ast.expr,
    ) -> Generator[tuple[str, int, int], None, None]:
        if isinstance(target, ast.Name):
            yield target.id, target.lineno, target.col_offset
            return

        if isinstance(target, (ast.Tuple, ast.List)):
            for item in target.elts:
                yield from self._target_names(item)
            return

        if isinstance(target, ast.Starred):
            yield from self._target_names(target.value)

    def _definition_names(
        self,
        node: ast.stmt,
    ) -> Generator[tuple[str, int, int], None, None]:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            yield node.name, node.lineno, node.col_offset
            return

        if isinstance(node, ast.Assign):
            for target in node.targets:
                yield from self._target_names(target)
            return

        if isinstance(node, ast.AnnAssign):
            yield from self._target_names(node.target)
            return

        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname or alias.name.split(".", maxsplit=1)[0]
                yield name, node.lineno, node.col_offset
            return

        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "*":
                    continue
                name = alias.asname or alias.name
                yield name, node.lineno, node.col_offset

    def _definitions_in_body(self, body: list[ast.stmt]) -> dict[str, Definition]:
        definitions: dict[str, Definition] = {}
        for node in body:
            for name, lineno, col_offset in self._definition_names(node):
                definitions[name] = Definition(
                    name=name,
                    node=node,
                    lineno=lineno,
                    col_offset=col_offset,
                )

        return definitions

    def _method_receiver_names(self, node: ast.stmt) -> set[str]:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return set()

        names = {"self", "cls"}
        if node.args.args:
            names.add(node.args.args[0].arg)

        return names

    def _method_definitions_in_body(
        self,
        body: list[ast.stmt],
    ) -> dict[str, Definition]:
        definitions: dict[str, Definition] = {}
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                definitions[node.name] = Definition(
                    name=node.name,
                    node=node,
                    lineno=node.lineno,
                    col_offset=node.col_offset,
                )

        return definitions

    def _visit_definition_references(
        self,
        node: ast.stmt,
        collector: NameReferenceCollector,
    ) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator in node.decorator_list:
                collector.visit(decorator)
            collector.visit(node.args)
            if node.returns is not None:
                collector.visit(node.returns)
            for statement in node.body:
                collector.visit(statement)
            return

        if isinstance(node, ast.ClassDef):
            for decorator in node.decorator_list:
                collector.visit(decorator)
            for base in node.bases:
                collector.visit(base)
            for keyword in node.keywords:
                collector.visit(keyword)
            for statement in node.body:
                collector.visit(statement)
            return

        if isinstance(node, ast.Assign):
            collector.visit(node.value)
            return

        if isinstance(node, ast.AnnAssign):
            if node.value is not None:
                collector.visit(node.value)

            return

    def _check_class_methods(
        self,
        body: list[ast.stmt],
    ) -> Generator[PluginResult, None, None]:
        definitions = self._method_definitions_in_body(body)
        local_names = set(definitions)

        for containing_definition in definitions.values():
            collector = NameReferenceCollector(
                local_names,
                attribute_base_names=self._method_receiver_names(
                    containing_definition.node
                ),
            )
            self._visit_definition_references(containing_definition.node, collector)

            for caller in sorted(collector.references):
                if caller.name == containing_definition.name:
                    continue

                callee_definition = definitions[caller.name]
                if self._is_allowed_definition_order(
                    containing_definition,
                    callee_definition,
                ):
                    continue

                relative_position = (
                    "later"
                    if self.order == CallerCalleeOrder.CALLEE_BEFORE_CALLER
                    else "earlier"
                )
                message = (
                    f"CCO001 `{containing_definition.name}` references "
                    f"`{caller.name}`, but `{caller.name}` is defined "
                    f"{relative_position} at line {callee_definition.lineno}"
                )
                yield caller.lineno, caller.col_offset, message, type(self)

    def _check_body(
        self,
        body: list[ast.stmt],
    ) -> Generator[PluginResult, None, None]:
        definitions = self._definitions_in_body(body)
        local_names = set(definitions)

        for containing_definition in definitions.values():
            collector = NameReferenceCollector(local_names)
            self._visit_definition_references(containing_definition.node, collector)

            for caller in sorted(collector.references):
                if caller.name == containing_definition.name:
                    continue

                callee_definition = definitions[caller.name]
                if self._is_allowed_definition_order(
                    containing_definition,
                    callee_definition,
                ):
                    continue

                relative_position = (
                    "later"
                    if self.order == CallerCalleeOrder.CALLEE_BEFORE_CALLER
                    else "earlier"
                )
                message = (
                    f"CCO001 `{containing_definition.name}` references "
                    f"`{caller.name}`, but `{caller.name}` is defined "
                    f"{relative_position} at line {callee_definition.lineno}"
                )
                yield caller.lineno, caller.col_offset, message, type(self)

            if isinstance(containing_definition.node, ast.ClassDef):
                yield from self._check_class_methods(containing_definition.node.body)

    def run(self) -> Generator[PluginResult, None, None]:
        if not isinstance(self.tree, ast.Module):
            return

        yield from self._check_body(self.tree.body)
