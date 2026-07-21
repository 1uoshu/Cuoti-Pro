from app.kernel.agent.sandbox import PythonSandbox


def _sandbox(timeout_seconds: float = 1) -> PythonSandbox:
    return PythonSandbox(
        timeout_seconds=timeout_seconds,
        memory_limit_mb=256,
        max_code_chars=4000,
        max_output_chars=4000,
    )


def test_python_sandbox_allows_restricted_math_libraries():
    execution = _sandbox().execute(
        """from fractions import Fraction
import sympy as sp
x = sp.symbols("x")
solutions = sp.solve(sp.Eq(x ** 2 - 5 * x + 6, 0), x)
result = {
    "fraction": str(Fraction(1, 3) + Fraction(1, 6)),
    "solutions": [str(item) for item in solutions],
}
"""
    )

    assert execution.ok is True
    assert execution.value == {"fraction": "1/2", "solutions": ["2", "3"]}
    assert execution.error is None


def test_python_sandbox_rejects_os_file_and_dynamic_execution_access():
    for code in (
        "import os\nresult = os.environ",
        'result = open("secret.txt").read()',
        'result = eval("1 + 1")',
        'result = (1).__class__.__mro__',
        "import sympy.utilities.runtests as rt\nresult = rt.os.getcwd()",
        "import sympy as sp\nresult = sp.utilities.runtests.subprocess.run(['whoami'])",
    ):
        execution = _sandbox().execute(code)

        assert execution.ok is False
        assert execution.error
        assert execution.value is None


def test_python_sandbox_terminates_infinite_computation():
    execution = _sandbox(timeout_seconds=0.25).execute("while True:\n    pass\nresult = 1")

    assert execution.ok is False
    assert execution.value is None
    assert execution.error == "Python sandbox timed out"
