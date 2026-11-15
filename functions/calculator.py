import ast
import math
import operator

_BIN = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod, ast.Pow: operator.pow,
}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_FUNCS = {
    "sqrt": math.sqrt, "abs": abs, "round": round, "floor": math.floor, "ceil": math.ceil,
    "sin": math.sin, "cos": math.cos, "tan": math.tan, "log": math.log, "log10": math.log10,
}
_CONSTS = {"pi": math.pi, "e": math.e}


def _eval(node):
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN:
        left, right = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 1000:
            raise ValueError("Exponent is too large.")
        return _BIN[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return _UNARY[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.Name) and node.id in _CONSTS:
        return _CONSTS[node.id]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCS and not node.keywords:
        return _FUNCS[node.func.id](*[_eval(a) for a in node.args])
    raise ValueError("Unsupported expression.")


def evaluate_expression(expression):
    """Safely evaluate a math expression such as '450 * 15 / 100' or 'sqrt(144) + 2**3'."""
    expr = str(expression).strip().replace("^", "**").replace("×", "*").replace("÷", "/").replace(",", "")
    if not expr or len(expr) > 200:
        raise ValueError("Please provide a valid math expression.")
    try:
        result = _eval(ast.parse(expr, mode="eval"))
    except ZeroDivisionError:
        raise ValueError("Cannot divide by zero.")
    except (SyntaxError, TypeError, OverflowError):
        raise ValueError("I could not understand that expression.")
    if isinstance(result, float) and not math.isfinite(result):
        raise ValueError("The result is outside the supported range.")
    if isinstance(result, float):
        result = round(result, 10)
    return {"expression": expression, "result": result}


def calculate(a, b, operation):
    """Original ActionAI two-operand calculator (kept for compatibility)."""
    a, b = float(a), float(b)
    ops = {
        "add": lambda: a + b, "subtract": lambda: a - b, "multiply": lambda: a * b,
        "divide": lambda: a / b, "power": lambda: a ** b, "percentage": lambda: (a * b) / 100,
    }
    if operation not in ops:
        raise ValueError("Unsupported calculation.")
    if operation == "divide" and b == 0:
        raise ValueError("Cannot divide by zero.")
    result = ops[operation]()
    if not math.isfinite(result):
        raise ValueError("The result is outside the supported range.")
    return {"operation": operation, "a": a, "b": b, "result": result}
