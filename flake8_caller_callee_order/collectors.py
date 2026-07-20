from __future__ import annotations

import ast

from .definitions import target_names
from .models import Reference


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
        for name, _, _ in target_names(target):
            self.names.add(name)

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


def binding_names_in_body(body: list[ast.stmt]) -> set[str]:
    collector = ScopeBindingCollector()
    for statement in body:
        collector.visit(statement)
    return collector.names
