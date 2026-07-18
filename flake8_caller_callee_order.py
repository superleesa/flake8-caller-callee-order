from __future__ import annotations

import ast
from enum import Enum
from typing import Any, Generator, NamedTuple, Type


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


ResolutionContext = tuple[ScopeFrame, ...]


class ShallowReferenceCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.references: list[Reference] = []

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
        if isinstance(node.ctx, ast.Load):
            self.references.append(
                Reference(
                    name=node.id,
                    lineno=node.lineno,
                    col_offset=node.col_offset,
                )
            )

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.ctx, ast.Load) and isinstance(node.value, ast.Name):
            self.references.append(
                Reference(
                    name=node.attr,
                    lineno=node.lineno,
                    col_offset=node.col_offset,
                    base_name=node.value.id,
                )
            )

        self.visit(node.value)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return

    def visit_ListComp(self, node: ast.ListComp) -> None:
        return

    def visit_SetComp(self, node: ast.SetComp) -> None:
        return

    def visit_DictComp(self, node: ast.DictComp) -> None:
        return

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        return

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

    def visit_If(self, node: ast.If) -> None:
        self.visit(node.test)

    def visit_For(self, node: ast.For) -> None:
        self.visit(node.iter)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self.visit(node.iter)

    def visit_While(self, node: ast.While) -> None:
        self.visit(node.test)

    def visit_With(self, node: ast.With) -> None:
        for item in node.items:
            self.visit(item.context_expr)

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        for item in node.items:
            self.visit(item.context_expr)

    def visit_Try(self, node: ast.Try) -> None:
        for handler in node.handlers:
            if handler.type is not None:
                self.visit(handler.type)

    def visit_Match(self, node: ast.Match) -> None:
        self.visit(node.subject)


class ScopeBindingCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.names: set[str] = set()

    def _add_target_names(self, target: ast.expr) -> None:
        if isinstance(target, ast.Name):
            self.names.add(target.id)
            return

        if isinstance(target, (ast.Tuple, ast.List)):
            for item in target.elts:
                self._add_target_names(item)
            return

        if isinstance(target, ast.Starred):
            self._add_target_names(target.value)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.names.add(node.name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.names.add(node.name)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.names.add(node.name)

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            self._add_target_names(target)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self._add_target_names(node.target)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self._add_target_names(node.target)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        self._add_target_names(node.target)

    def visit_For(self, node: ast.For) -> None:
        self._add_target_names(node.target)
        for statement in node.body:
            self.visit(statement)
        for statement in node.orelse:
            self.visit(statement)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self._add_target_names(node.target)
        for statement in node.body:
            self.visit(statement)
        for statement in node.orelse:
            self.visit(statement)

    def visit_With(self, node: ast.With) -> None:
        for item in node.items:
            if item.optional_vars is not None:
                self._add_target_names(item.optional_vars)
        for statement in node.body:
            self.visit(statement)

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        for item in node.items:
            if item.optional_vars is not None:
                self._add_target_names(item.optional_vars)
        for statement in node.body:
            self.visit(statement)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name is not None:
            self.names.add(node.name)
        for statement in node.body:
            self.visit(statement)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.names.add(alias.asname or alias.name.split(".", maxsplit=1)[0])

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            if alias.name == "*":
                continue
            self.names.add(alias.asname or alias.name)


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

    def _argument_names(self, arguments: ast.arguments) -> set[str]:
        names = {arg.arg for arg in arguments.posonlyargs}
        names.update(arg.arg for arg in arguments.args)
        names.update(arg.arg for arg in arguments.kwonlyargs)

        if arguments.vararg is not None:
            names.add(arguments.vararg.arg)
        if arguments.kwarg is not None:
            names.add(arguments.kwarg.arg)

        return names

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

    def _module_definitions_in_body(
        self,
        body: list[ast.stmt],
    ) -> dict[str, Definition]:
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

    def _nested_definitions_in_body(
        self,
        body: list[ast.stmt],
    ) -> dict[str, Definition]:
        definitions: dict[str, Definition] = {}
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                definitions[node.name] = Definition(
                    name=node.name,
                    node=node,
                    lineno=node.lineno,
                    col_offset=node.col_offset,
                )

        return definitions

    def _definitions_for_body(
        self,
        body: list[ast.stmt],
        mode: BodyCheckMode,
    ) -> dict[str, Definition]:
        if mode == BodyCheckMode.MODULE:
            return self._module_definitions_in_body(body)

        if mode == BodyCheckMode.CLASS_BODY:
            return self._method_definitions_in_body(body)

        if mode == BodyCheckMode.FUNCTION_BODY:
            return self._nested_definitions_in_body(body)

        return {}

    def _definition_for_statement(
        self,
        statement: ast.stmt,
        definitions: dict[str, Definition],
    ) -> Definition | None:
        for definition in definitions.values():
            if definition.node is statement:
                return definition

        return None

    def _binding_names_in_body(self, body: list[ast.stmt]) -> set[str]:
        collector = ScopeBindingCollector()
        for statement in body:
            collector.visit(statement)
        return collector.names

    def _is_staticmethod(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name) and decorator.id == "staticmethod":
                return True
            if (
                isinstance(decorator, ast.Attribute)
                and decorator.attr == "staticmethod"
            ):
                return True

        return False

    def _first_positional_argument(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> ast.arg | None:
        if node.args.posonlyargs:
            return node.args.posonlyargs[0]
        if node.args.args:
            return node.args.args[0]
        return None

    def _receiver_binding(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        method_namespace: dict[str, Definition] | None,
    ) -> tuple[str, Binding] | None:
        receiver_argument = self._first_positional_argument(node)
        if method_namespace is None or self._is_staticmethod(node):
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

    def _frame_for_body(
        self,
        body: list[ast.stmt],
        definitions: dict[str, Definition],
        mode: BodyCheckMode,
        extra_bindings: dict[str, Binding] | None = None,
    ) -> ScopeFrame:
        bindings: dict[str, Binding] = {}

        if mode != BodyCheckMode.CLASS_BODY:
            for name in self._binding_names_in_body(body):
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

    def _resolve_name(
        self,
        name: str,
        context: ResolutionContext,
    ) -> Binding | None:
        for frame in context:
            binding = frame.bindings.get(name)
            if binding is not None:
                return binding

        return None

    def _resolve_reference(
        self,
        reference: Reference,
        context: ResolutionContext,
    ) -> Definition | None:
        if reference.base_name is None:
            binding = self._resolve_name(reference.name, context)
            if binding is not None and binding.kind == BindingKind.ORDERED:
                return binding.definition
            return None

        base_binding = self._resolve_name(reference.base_name, context)
        if (
            base_binding is not None
            and base_binding.kind == BindingKind.RECEIVER
            and base_binding.receiver_namespace is not None
        ):
            return base_binding.receiver_namespace.get(reference.name)

        return None

    def _shallow_references_in_node(self, node: ast.AST) -> list[Reference]:
        collector = ShallowReferenceCollector()
        collector.visit(node)
        return collector.references

    def _check_reference(
        self,
        reference: Reference,
        context: ResolutionContext,
        containing_definition: Definition,
    ) -> Generator[PluginResult, None, None]:
        callee_definition = self._resolve_reference(reference, context)
        if (
            callee_definition is None
            or callee_definition.node is containing_definition.node
        ):
            return

        if self._is_allowed_definition_order(
            containing_definition,
            callee_definition,
        ):
            return

        relative_position = (
            "later"
            if self.order == CallerCalleeOrder.CALLEE_BEFORE_CALLER
            else "earlier"
        )
        message = (
            f"CCO001 `{containing_definition.name}` references "
            f"`{reference.name}`, but `{reference.name}` is defined "
            f"{relative_position} at line {callee_definition.lineno}"
        )
        yield reference.lineno, reference.col_offset, message, type(self)

    def _check_shallow_references(
        self,
        node: ast.AST,
        context: ResolutionContext,
        containing_definition: Definition,
    ) -> Generator[PluginResult, None, None]:
        for reference in sorted(self._shallow_references_in_node(node)):
            yield from self._check_reference(
                reference,
                context,
                containing_definition,
            )

    def _function_body_context(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        context: ResolutionContext,
        method_namespace: dict[str, Definition] | None = None,
    ) -> ResolutionContext:
        extra_bindings = {
            name: Binding(kind=BindingKind.SHADOW)
            for name in self._argument_names(node.args)
        }
        receiver_binding = self._receiver_binding(node, method_namespace)
        if receiver_binding is not None:
            name, binding = receiver_binding
            extra_bindings[name] = binding

        frame = self._frame_for_body(
            node.body,
            definitions=self._definitions_for_body(
                node.body,
                BodyCheckMode.FUNCTION_BODY,
            ),
            mode=BodyCheckMode.FUNCTION_BODY,
            extra_bindings=extra_bindings,
        )
        return (frame, *context)

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

    def _class_body_context(
        self,
        node: ast.ClassDef,
        context: ResolutionContext,
    ) -> tuple[ResolutionContext, dict[str, Definition]]:
        method_definitions = self._method_definitions_in_body(node.body)
        frame = self._frame_for_body(
            node.body,
            definitions=method_definitions,
            mode=BodyCheckMode.CLASS_BODY,
        )
        return (frame, *context), method_definitions

    def _check_body(
        self,
        body: list[ast.stmt],
        *,
        mode: BodyCheckMode,
        context: ResolutionContext,
        containing_definition: Definition | None,
        method_namespace: dict[str, Definition] | None = None,
        method_parent_context: ResolutionContext | None = None,
    ) -> Generator[PluginResult, None, None]:
        definitions = self._definitions_for_body(body, mode)

        for statement in body:
            statement_definition = self._definition_for_statement(
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
                    context=self._function_body_context(
                        statement,
                        function_context,
                        method_namespace if statement_definition is not None else None,
                    ),
                    containing_definition=active_containing_definition,
                )
                continue

            if isinstance(statement, ast.ClassDef):
                class_context, class_method_namespace = self._class_body_context(
                    statement,
                    context,
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

    def run(self) -> Generator[PluginResult, None, None]:
        if not isinstance(self.tree, ast.Module):
            return

        definitions = self._module_definitions_in_body(self.tree.body)
        module_frame = self._frame_for_body(
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
