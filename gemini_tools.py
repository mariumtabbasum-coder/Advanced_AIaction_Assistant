"""Tool declarations and execution for ActionAI (Gemini function calling)."""
from google.genai import types

from functions.age_calculator import calculate_age
from functions.calculator import evaluate_expression
from functions.currency import convert_currency
from functions.weather import get_weather

_S = types.Schema
_T = types.Type

DECLARATIONS = [
    types.FunctionDeclaration(
        name="calculator",
        description=("Evaluate a math expression exactly. Use for arithmetic, percentages, powers and roots. "
                     "Example: '15% of 450' -> expression '450 * 15 / 100'."),
        parameters=_S(type=_T.OBJECT, properties={
            "expression": _S(type=_T.STRING, description="Math expression using + - * / ** % ( ) sqrt() etc.")},
            required=["expression"]),
    ),
    types.FunctionDeclaration(
        name="get_weather",
        description="Get the CURRENT live weather for a city. Only use when the user wants the weather of a specific place now.",
        parameters=_S(type=_T.OBJECT, properties={"city": _S(type=_T.STRING, description="City name, e.g. Karachi")},
                      required=["city"]),
    ),
    types.FunctionDeclaration(
        name="convert_currency",
        description="Convert an amount between currencies using live exchange rates. Not for explaining how currencies work.",
        parameters=_S(type=_T.OBJECT, properties={
            "amount": _S(type=_T.NUMBER, description="Amount to convert"),
            "from_currency": _S(type=_T.STRING, description="3-letter source code, e.g. USD"),
            "to_currency": _S(type=_T.STRING, description="3-letter target code, e.g. PKR")},
            required=["amount", "from_currency", "to_currency"]),
    ),
    types.FunctionDeclaration(
        name="calculate_age",
        description="Calculate exact age (years, months, days) from a date of birth.",
        parameters=_S(type=_T.OBJECT, properties={
            "birth_date": _S(type=_T.STRING, description="Date of birth, YYYY-MM-DD")},
            required=["birth_date"]),
    ),
]
TOOLS = [types.Tool(function_declarations=DECLARATIONS)]

FUNCTIONS = {
    "calculator": evaluate_expression,
    "get_weather": get_weather,
    "convert_currency": convert_currency,
    "calculate_age": calculate_age,
}
LABELS = {
    "calculator": "Calculator",
    "get_weather": "Live Weather",
    "convert_currency": "Currency Conversion",
    "calculate_age": "Age Calculator",
}


def execute(name, args):
    """Run a tool and always return a dict. Errors are returned, never raised."""
    fn = FUNCTIONS.get(name)
    if fn is None:
        return {"error": "Unknown tool requested."}
    try:
        return fn(**args)
    except ValueError as exc:
        return {"error": str(exc)}
    except Exception:  # noqa: BLE001  network / provider failures
        return {"error": "The live service is not reachable right now. Please try again shortly."}
