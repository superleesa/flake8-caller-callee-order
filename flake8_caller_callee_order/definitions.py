from __future__ import annotations

import ast
from typing import Generator

from .models import BodyCheckMode, Definition


def target_names(
    target: ast.expr,
) -> Generator[tuple[str, int, int], None, None]:
    if isinstance(target, ast.Name):
        yield target.id, target.lineno, target.col_offset
        return

    if isinstance(target, (ast.Tuple, ast.List)):
        for item in target.elts:
            yield from target_names(item)
        return

    if isinstance(target, ast.Starred):
        yield from target_names(target.value)


def argument_names(arguments: ast.arguments) -> set[str]:
    names = {arg.arg for arg in arguments.posonlyargs}
    names.update(arg.arg for arg in arguments.args)
    names.update(arg.arg for arg in arguments.kwonlyargs)

    if arguments.vararg is not None:
        names.add(arguments.vararg.arg)
    if arguments.kwarg is not None:
        names.add(arguments.kwarg.arg)

    return names


def definition_names(
    node: ast.stmt,
) -> Generator[tuple[str, int, int], None, None]:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        yield node.name, node.lineno, node.col_offset
        return

    if isinstance(node, ast.Assign):
        for target in node.targets:
            yield from target_names(target)
        return

    if isinstance(node, ast.AnnAssign):
        yield from target_names(node.target)
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


def module_definitions_in_body(
    body: list[ast.stmt],
) -> dict[str, Definition]:
    definitions: dict[str, Definition] = {}
    for node in body:
        for name, lineno, col_offset in definition_names(node):
            definitions[name] = Definition(
                name=name,
                node=node,
                lineno=lineno,
                col_offset=col_offset,
            )

    return definitions


def method_definitions_in_body(
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


def nested_definitions_in_body(
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


def definitions_for_body(
    body: list[ast.stmt],
    mode: BodyCheckMode,
) -> dict[str, Definition]:
    if mode == BodyCheckMode.MODULE:
        return module_definitions_in_body(body)

    if mode == BodyCheckMode.CLASS_BODY:
        return method_definitions_in_body(body)

    if mode == BodyCheckMode.FUNCTION_BODY:
        return nested_definitions_in_body(body)

    return {}


def definition_for_statement(
    statement: ast.stmt,
    definitions: dict[str, Definition],
) -> Definition | None:
    for definition in definitions.values():
        if definition.node is statement:
            return definition

    return None
