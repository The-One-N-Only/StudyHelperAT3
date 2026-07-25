"""Mathematics computation and visualization tools."""

import logging
import urllib.parse

logger = logging.getLogger(__name__)

try:
    import sympy
    SYMPY_AVAILABLE = True
except ImportError:
    SYMPY_AVAILABLE = False


def solve_equation(equation_str: str, variable: str = "x") -> dict:
    """Solve an equation symbolically using SymPy."""
    if not SYMPY_AVAILABLE:
        return {"error": "SymPy not installed. Install with: pip install sympy"}

    try:
        x = sympy.symbols(variable)
        expr = sympy.sympify(equation_str.replace("=", "-(") + ")")
        solution = sympy.solve(expr, x)
        return {
            "equation": equation_str,
            "variable": variable,
            "solutions": [str(s) for s in solution],
            "steps": [
                f"Original: {equation_str}",
                f"Rearrange: {expr} = 0",
                f"Solve for {variable}: {', '.join(str(s) for s in solution) if solution else 'No solutions found'}",
            ],
        }
    except Exception as e:
        return {"error": str(e)}

def differentiate(expr_str: str, variable: str = "x") -> dict:
    """Differentiate an expression."""
    if not SYMPY_AVAILABLE:
        return {"error": "SymPy not installed"}

    try:
        x = sympy.symbols(variable)
        expr = sympy.sympify(expr_str)
        derivative = sympy.diff(expr, x)
        return {
            "expression": expr_str,
            "derivative": str(derivative),
            "steps": [f"f({variable}) = {expr_str}", f"f'({variable}) = {derivative}"],
        }
    except Exception as e:
        return {"error": str(e)}

def integrate(expr_str: str, variable: str = "x") -> dict:
    """Integrate an expression."""
    if not SYMPY_AVAILABLE:
        return {"error": "SymPy not installed"}

    try:
        x = sympy.symbols(variable)
        expr = sympy.sympify(expr_str)
        integral = sympy.integrate(expr, x)
        return {
            "expression": expr_str,
            "integral": f"{integral} + C",
            "steps": [f"∫ {expr_str} d{variable}", f"= {integral} + C"],
        }
    except Exception as e:
        return {"error": str(e)}

def get_desmos_embed_url(expr: str, graph_type: str = "function") -> str:
    """Generate a Desmos embed URL for graphing."""
    params = urllib.parse.urlencode({
        expr if graph_type == "function" else graph_type: expr,
    })
    return f"https://www.desmos.com/calculator?{params}"
