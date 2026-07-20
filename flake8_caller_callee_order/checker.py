from __future__ import annotations

import ast
from typing import Generator

from .collectors import ShallowReferenceCollector
from .definitions import (
    definition_for_statement,
    definitions_for_body,
    module_definitions_in_body,
)
from .diagnostics import format_order_violation, is_allowed_definition_order
from .frames import ScopeFrameBuilder
from .models import (
    BodyCheckMode,
    CallerCalleeOrder,
    Definition,
    Reference,
    ResolutionContext,
    Violation,
)
from .resolver import ReferenceResolver


class OrderChecker:
    def __init__(
        self,
        tree: ast.AST,
        order: CallerCalleeOrder,
        *,
        frame_builder: ScopeFrameBuilder | None = None,
        resolver: ReferenceResolver | None = None,
    ) -> None:
        self.tree = tree
        self.order = order
        self.frame_builder = frame_builder or ScopeFrameBuilder()
        self.resolver = resolver or ReferenceResolver()

    def _shallow_references_in_node(self, node: ast.AST) -> list[Reference]:
        collector = ShallowReferenceCollector()
        collector.visit(node)
        return collector.references

    def _check_reference(
        self,
        reference: Reference,
        context: ResolutionContext,
        containing_definition: Definition,
    ) -> Generator[Violation, None, None]:
        callee_definition = self.resolver.resolve_reference(reference, context)
        if (
            callee_definition is None
            or callee_definition.node is containing_definition.node
        ):
            return

        if is_allowed_definition_order(
            self.order,
            containing_definition,
            callee_definition,
        ):
            return

        yield Violation(
            reference.lineno,
            reference.col_offset,
            format_order_violation(
                self.order,
                containing_definition,
                callee_definition,
                reference,
            ),
        )

    def _check_shallow_references(
        self,
        node: ast.AST,
        context: ResolutionContext,
        containing_definition: Definition,
    ) -> Generator[Violation, None, None]:
        for reference in sorted(self._shallow_references_in_node(node)):
            yield from self._check_reference(
                reference,
                context,
                containing_definition,
            )

    def _child_bodies_in_statement(
        self,
        statement: ast.stmt,
    ) -> Generator[list[ast.stmt], None, None]:
        if isinstance(statement, ast.If):
            yield statement.body
            yield statement.orelse
            return

        if isinstance(statement, (ast.For, ast.AsyncFor, ast.While)):
            yield statement.body
            yield statement.orelse
            return

        if isinstance(statement, (ast.With, ast.AsyncWith)):
            yield statement.body
            return

        if isinstance(statement, ast.Try):
            yield statement.body
            for handler in statement.handlers:
                yield handler.body
            yield statement.orelse
            yield statement.finalbody
            return

        if isinstance(statement, ast.Match):
            for case in statement.cases:
                yield case.body

    def _check_body(
        self,
        body: list[ast.stmt],
        *,
        mode: BodyCheckMode,
        context: ResolutionContext,
        containing_definition: Definition | None,
        method_namespace: dict[str, Definition] | None = None,
        method_parent_context: ResolutionContext | None = None,
    ) -> Generator[Violation, None, None]:
        definitions = definitions_for_body(body, mode)

        for statement in body:
            statement_definition = definition_for_statement(
                statement,
                definitions,
            )

            active_containing_definition = statement_definition or containing_definition
            if active_containing_definition is not None:
                yield from self._check_shallow_references(
                    statement,
                    context,
                    active_containing_definition,
                )

            if active_containing_definition is None:
                continue

            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                function_context = (
                    method_parent_context
                    if statement_definition is not None
                    and method_parent_context is not None
                    else context
                )
                yield from self._check_body(
                    statement.body,
                    mode=BodyCheckMode.FUNCTION_BODY,
                    context=self.frame_builder.function_body_context(
                        statement,
                        function_context,
                        method_namespace if statement_definition is not None else None,
                    ),
                    containing_definition=active_containing_definition,
                )
                continue

            if isinstance(statement, ast.ClassDef):
                class_context, class_method_namespace = (
                    self.frame_builder.class_body_context(
                        statement,
                        context,
                    )
                )
                yield from self._check_body(
                    statement.body,
                    mode=BodyCheckMode.CLASS_BODY,
                    context=class_context,
                    containing_definition=active_containing_definition,
                    method_namespace=class_method_namespace,
                    method_parent_context=context,
                )
                continue

            for child_body in self._child_bodies_in_statement(statement):
                yield from self._check_body(
                    child_body,
                    mode=mode,
                    context=context,
                    containing_definition=active_containing_definition,
                    method_namespace=method_namespace,
                    method_parent_context=method_parent_context,
                )

    def run(self) -> Generator[Violation, None, None]:
        if not isinstance(self.tree, ast.Module):
            return

        definitions = module_definitions_in_body(self.tree.body)
        module_frame = self.frame_builder.frame_for_body(
            self.tree.body,
            definitions=definitions,
            mode=BodyCheckMode.MODULE,
        )
        yield from self._check_body(
            self.tree.body,
            mode=BodyCheckMode.MODULE,
            context=(module_frame,),
            containing_definition=None,
        )
