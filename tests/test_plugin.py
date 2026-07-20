from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

from flake8_caller_callee_order import CallerCalleeOrder, CallerCalleeOrderChecker


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


def run_flake8(
    tmp_path: Path,
    *filenames: str,
    config: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    if config is None:
        config = tmp_path / ".flake8"
        config.write_text(
            """
[flake8]
select = CCO
""",
            encoding="utf-8",
        )

    paths = [str(FIXTURES / name) for name in filenames]
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "flake8",
            "--config",
            str(config),
            *paths,
        ],
        cwd=tmp_path,
        check=False,
        text=True,
        capture_output=True,
    )


def run_checker(
    source: str,
    *,
    order: CallerCalleeOrder = CallerCalleeOrder.CALLEE_BEFORE_CALLER,
) -> list[tuple[int, int, str, type[CallerCalleeOrderChecker]]]:
    tree = ast.parse(source)
    checker = CallerCalleeOrderChecker(tree)
    checker.order = order
    return list(checker.run())


def test_checker_allows_calls_to_earlier_definitions() -> None:
    results = run_checker(
        """
def helper():
    print("helper")


def main():
    helper()
"""
    )

    assert results == []


def test_checker_reports_later_defined_callee() -> None:
    results = run_checker(
        """
def main():
    helper()


def helper():
    print("helper")
"""
    )

    assert results == [
        (
            3,
            4,
            (
                "CCO001 `main` references `helper`, but `helper` is "
                "defined later at line 6"
            ),
            CallerCalleeOrderChecker,
        )
    ]


def test_checker_reports_earlier_defined_callee_in_bottom_up_order() -> None:
    results = run_checker(
        """
def helper():
    print("helper")


def main():
    helper()
""",
        order=CallerCalleeOrder.CALLER_BEFORE_CALLEE,
    )

    assert results == [
        (
            7,
            4,
            (
                "CCO001 `main` references `helper`, but `helper` is "
                "defined earlier at line 2"
            ),
            CallerCalleeOrderChecker,
        )
    ]


def test_mixed_fixture_reports_each_later_defined_callee(tmp_path: Path) -> None:
    result = run_flake8(tmp_path, "mixed.py")

    assert result.returncode == 1
    assert f"{FIXTURES / 'mixed.py'}:2:5: CCO001" in result.stdout
    assert f"{FIXTURES / 'mixed.py'}:3:5: CCO001" in result.stdout
    assert "`a` references `b`" in result.stdout
    assert "`a` references `c`" in result.stdout
    assert result.stderr == ""


def test_bottom_up_order_can_be_configured(tmp_path: Path) -> None:
    config = tmp_path / ".flake8"
    config.write_text(
        """
[flake8]
select = CCO
caller-callee-order = caller-before-callee
""",
        encoding="utf-8",
    )

    result = run_flake8(tmp_path, "mixed.py", config=config)

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_checker_reports_later_defined_class_reference() -> None:
    results = run_checker(
        """
def main():
    return User()


class User:
    pass
"""
    )

    assert results == [
        (
            3,
            11,
            "CCO001 `main` references `User`, but `User` is defined later at line 6",
            CallerCalleeOrderChecker,
        )
    ]


def test_checker_reports_later_defined_assignment_reference() -> None:
    results = run_checker(
        """
VALUE = OTHER
OTHER = 1
"""
    )

    assert results == [
        (
            2,
            8,
            "CCO001 `VALUE` references `OTHER`, but `OTHER` is defined later at line 3",
            CallerCalleeOrderChecker,
        )
    ]


def test_checker_reports_later_defined_annotated_assignment_reference() -> None:
    results = run_checker(
        """
VALUE: int = OTHER
OTHER = 1
"""
    )

    assert results == [
        (
            2,
            13,
            "CCO001 `VALUE` references `OTHER`, but `OTHER` is defined later at line 3",
            CallerCalleeOrderChecker,
        )
    ]


def test_checker_reports_later_defined_import_reference() -> None:
    results = run_checker(
        """
def main():
    return Path("file.txt")


from pathlib import Path
"""
    )

    assert results == [
        (
            3,
            11,
            "CCO001 `main` references `Path`, but `Path` is defined later at line 6",
            CallerCalleeOrderChecker,
        )
    ]


def test_checker_allows_class_body_references_to_later_class_members() -> None:
    results = run_checker(
        """
class Config:
    value = default
    default = 1
"""
    )

    assert results == []


def test_checker_reports_later_defined_class_method_reference() -> None:
    results = run_checker(
        """
class Service:
    def run(self):
        self.helper()

    def helper(self):
        pass
"""
    )

    assert results == [
        (
            4,
            8,
            (
                "CCO001 `run` references `helper`, but `helper` is "
                "defined later at line 6"
            ),
            CallerCalleeOrderChecker,
        )
    ]


def test_checker_reports_later_defined_class_method_reference_from_cls() -> None:
    results = run_checker(
        """
class Service:
    @classmethod
    def run(cls):
        cls.helper()

    @classmethod
    def helper(cls):
        pass
"""
    )

    assert results == [
        (
            5,
            8,
            (
                "CCO001 `run` references `helper`, but `helper` is "
                "defined later at line 8"
            ),
            CallerCalleeOrderChecker,
        )
    ]


def test_checker_reports_class_method_reference_inside_nested_function() -> None:
    results = run_checker(
        """
class Service:
    def run(self):
        def inner():
            self.helper()

    def helper(self):
        pass
"""
    )

    assert results == [
        (
            5,
            12,
            (
                "CCO001 `inner` references `helper`, but `helper` is "
                "defined later at line 7"
            ),
            CallerCalleeOrderChecker,
        )
    ]


def test_checker_reports_class_method_reference_inside_nested_class() -> None:
    results = run_checker(
        """
class Service:
    def run(self):
        class Inner:
            value = self.helper()

    def helper(self):
        pass
"""
    )

    assert results == [
        (
            5,
            20,
            (
                "CCO001 `Inner` references `helper`, but `helper` is "
                "defined later at line 7"
            ),
            CallerCalleeOrderChecker,
        )
    ]


def test_checker_allows_inner_namespace_name_matching_later_definition() -> None:
    results = run_checker(
        """
def main():
    def inner():
        helper = lambda: None
        helper()


def helper():
    pass
"""
    )

    assert results == []


def test_checker_allows_inner_namespace_name_matching_later_method() -> None:
    results = run_checker(
        """
class Service:
    def run(self):
        def inner():
            helper = lambda: None
            helper()

    def helper(self):
        pass
"""
    )

    assert results == []


def test_checker_allows_inner_namespace_method_receiver() -> None:
    results = run_checker(
        """
class Service:
    def run(self):
        def inner(self):
            self.helper()

    def helper(self):
        pass
"""
    )

    assert results == []


def test_checker_reports_later_defined_attribute_base_reference() -> None:
    results = run_checker(
        """
def main():
    return Service.make()


class Service:
    pass
"""
    )

    assert results == [
        (
            3,
            11,
            "CCO001 `main` references `Service`, but `Service` is defined later at line 6",
            CallerCalleeOrderChecker,
        )
    ]


def test_checker_reports_nested_function_reference_under_if() -> None:
    results = run_checker(
        """
def main():
    if enabled:
        def inner():
            helper()


def helper():
    pass
"""
    )

    assert results == [
        (
            5,
            12,
            "CCO001 `inner` references `helper`, but `helper` is defined later at line 8",
            CallerCalleeOrderChecker,
        )
    ]


def test_checker_reports_nested_class_reference_inside_function() -> None:
    results = run_checker(
        """
def main():
    def inner():
        return Local()

    class Local:
        pass
"""
    )

    assert results == [
        (
            4,
            15,
            (
                "CCO001 `inner` references `Local`, but `Local` is "
                "defined later at line 6"
            ),
            CallerCalleeOrderChecker,
        )
    ]


def test_checker_allows_loop_target_matching_later_definition() -> None:
    results = run_checker(
        """
def main():
    for helper in helpers:
        helper()


def helper():
    pass
"""
    )

    assert results == []


def test_checker_allows_with_target_matching_later_definition() -> None:
    results = run_checker(
        """
def main():
    with manager() as helper:
        helper()


def helper():
    pass
"""
    )

    assert results == []


def test_checker_allows_except_target_matching_later_definition() -> None:
    results = run_checker(
        """
def main():
    try:
        risky()
    except Exception as helper:
        helper()


def helper():
    pass
"""
    )

    assert results == []


def test_checker_allows_named_expr_matching_later_definition() -> None:
    results = run_checker(
        """
def main():
    if helper := get_helper():
        helper()


def helper():
    pass
"""
    )

    assert results == []


def test_checker_allows_augassign_target_matching_later_definition() -> None:
    results = run_checker(
        """
def main():
    helper += 1
    return helper


def helper():
    pass
"""
    )

    assert results == []


def test_checker_allows_lambda_argument_matching_later_definition() -> None:
    results = run_checker(
        """
def main():
    return lambda helper: helper()


def helper():
    pass
"""
    )

    assert results == []


def test_checker_allows_comprehension_target_matching_later_definition() -> None:
    results = run_checker(
        """
def main():
    return [helper() for helper in helpers]


def helper():
    pass
"""
    )

    assert results == []


def test_checker_reports_same_named_method_reference_to_module_definition() -> None:
    results = run_checker(
        """
class Service:
    def helper(self):
        helper()


def helper():
    pass
"""
    )

    assert results == [
        (
            4,
            8,
            "CCO001 `helper` references `helper`, but `helper` is defined later at line 7",
            CallerCalleeOrderChecker,
        )
    ]


def test_checker_reports_later_defined_class_method_reference_from_custom_receiver() -> (
    None
):
    results = run_checker(
        """
class Service:
    def run(instance):
        instance.helper()

    def helper(self):
        pass
"""
    )

    assert results == [
        (
            4,
            8,
            (
                "CCO001 `run` references `helper`, but `helper` is "
                "defined later at line 6"
            ),
            CallerCalleeOrderChecker,
        )
    ]


def test_checker_reports_later_defined_class_method_reference_from_posonly_receiver() -> (
    None
):
    results = run_checker(
        """
class Service:
    def run(instance, /):
        instance.helper()

    def helper(self):
        pass
"""
    )

    assert results == [
        (
            4,
            8,
            (
                "CCO001 `run` references `helper`, but `helper` is "
                "defined later at line 6"
            ),
            CallerCalleeOrderChecker,
        )
    ]


def test_checker_allows_staticmethod_reference_to_later_method() -> None:
    results = run_checker(
        """
class Service:
    @staticmethod
    def run(instance):
        instance.helper()

    def helper(self):
        pass
"""
    )

    assert results == []


def test_checker_reports_class_body_reference_to_later_global() -> None:
    results = run_checker(
        """
class Config:
    value = DEFAULT
    DEFAULT = 1


DEFAULT = 2
"""
    )

    assert results == [
        (
            3,
            12,
            (
                "CCO001 `Config` references `DEFAULT`, but `DEFAULT` is "
                "defined later at line 7"
            ),
            CallerCalleeOrderChecker,
        )
    ]
