from __future__ import annotations

import ast

from .collectors import binding_names_in_body
from .definitions import argument_names, definitions_for_body, method_definitions_in_body
from .models import (
    Binding,
    BindingKind,
    BodyCheckMode,
    Definition,
    ResolutionContext,
    ScopeFrame,
)


class ScopeFrameBuilder:
    def is_staticmethod(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name) and decorator.id == "staticmethod":
                return True
            if (
                isinstance(decorator, ast.Attribute)
                and decorator.attr == "staticmethod"
            ):
                return True

        return False

    def first_positional_argument(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> ast.arg | None:
        if node.args.posonlyargs:
            return node.args.posonlyargs[0]
        if node.args.args:
            return node.args.args[0]
        return None

    def receiver_binding(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        method_namespace: dict[str, Definition] | None,
    ) -> tuple[str, Binding] | None:
        receiver_argument = self.first_positional_argument(node)
        if method_namespace is None or self.is_staticmethod(node):
            return None
        if receiver_argument is None:
            return None

        return (
            receiver_argument.arg,
            Binding(
                kind=BindingKind.RECEIVER,
                receiver_namespace=method_namespace,
            ),
        )

    def frame_for_body(
        self,
        body: list[ast.stmt],
        definitions: dict[str, Definition],
        mode: BodyCheckMode,
        extra_bindings: dict[str, Binding] | None = None,
    ) -> ScopeFrame:
        bindings: dict[str, Binding] = {}

        if mode != BodyCheckMode.CLASS_BODY:
            for name in binding_names_in_body(body):
                bindings[name] = Binding(kind=BindingKind.SHADOW)

        if mode in (BodyCheckMode.MODULE, BodyCheckMode.FUNCTION_BODY):
            for name, definition in definitions.items():
                bindings[name] = Binding(
                    kind=BindingKind.ORDERED,
                    definition=definition,
                )

        if extra_bindings is not None:
            bindings.update(extra_bindings)

        return ScopeFrame(bindings=bindings)

    def function_body_context(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        context: ResolutionContext,
        method_namespace: dict[str, Definition] | None = None,
    ) -> ResolutionContext:
        extra_bindings = {
            name: Binding(kind=BindingKind.SHADOW)
            for name in argument_names(node.args)
        }
        receiver_binding = self.receiver_binding(node, method_namespace)
        if receiver_binding is not None:
            name, binding = receiver_binding
            extra_bindings[name] = binding

        frame = self.frame_for_body(
            node.body,
            definitions=definitions_for_body(
                node.body,
                BodyCheckMode.FUNCTION_BODY,
            ),
            mode=BodyCheckMode.FUNCTION_BODY,
            extra_bindings=extra_bindings,
        )
        return (frame, *context)

    def class_body_context(
        self,
        node: ast.ClassDef,
        context: ResolutionContext,
    ) -> tuple[ResolutionContext, dict[str, Definition]]:
        method_definitions = method_definitions_in_body(node.body)
        frame = self.frame_for_body(
            node.body,
            definitions=method_definitions,
            mode=BodyCheckMode.CLASS_BODY,
        )
        return (frame, *context), method_definitions
