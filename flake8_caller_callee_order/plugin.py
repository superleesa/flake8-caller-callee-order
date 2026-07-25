from __future__ import annotations

import ast
import re
from typing import Any, Generator, Type

from .checker import OrderChecker
from .models import CallerCalleeOrder


PluginResult = tuple[
    int,
    int,
    str,
    Type["CallerCalleeOrderChecker"],
]


class CallerCalleeOrderChecker:
    name = "flake8-caller-callee-order"
    version = "0.2.0"
    order = CallerCalleeOrder.CALLEE_BEFORE_CALLER
    ignore_definition_patterns: tuple[re.Pattern[str], ...] = ()

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
        option_manager.add_option(
            "--caller-callee-order-ignore-definitions",
            default="",
            parse_from_config=True,
            comma_separated_list=True,
            help=(
                "Comma-separated regular expressions for definition names whose "
                "references should be ignored by caller/callee order checks."
            ),
        )

    @classmethod
    def parse_options(cls, options: Any) -> None:
        cls.order = CallerCalleeOrder(options.caller_callee_order)
        cls.ignore_definition_patterns = tuple(
            re.compile(pattern)
            for pattern in options.caller_callee_order_ignore_definitions
            if pattern
        )

    def __init__(self, tree: ast.AST, filename: str = "(none)") -> None:
        self.tree = tree
        self.filename = filename

    def run(self) -> Generator[PluginResult, None, None]:
        checker = OrderChecker(
            self.tree,
            self.order,
            ignore_definition_patterns=self.ignore_definition_patterns,
        )
        for violation in checker.run():
            yield (
                violation.lineno,
                violation.col_offset,
                violation.message,
                type(self),
            )
