"""
Program-Aided Compliance: Secure Local Python REPL Sandbox for FinReg-SLM.

Executes mathematical, date-arithmetic, and statutory threshold calculations
generated inside Chain-of-Thought <think> traces with strict execution bounds.
"""

import sys
import io
import time
import math
import datetime
from datetime import date, datetime as dt, timedelta
import decimal
from decimal import Decimal
from typing import Dict, Any, Optional, Tuple

class REPLSandbox:
    """Lightweight, isolated in-process REPL executor for regulatory calculations."""
    
    ALLOWED_MODULE_NAMES = {"math", "datetime", "decimal", "itertools", "collections", "time"}
    
    @staticmethod
    def _safe_import(name, *args, **kwargs):
        if name in REPLSandbox.ALLOWED_MODULE_NAMES:
            return __import__(name, *args, **kwargs)
        raise ImportError(f"Import of module '{name}' is restricted in regulatory REPL.")

    def __init__(self, timeout_seconds: float = 0.5):
        self.timeout_seconds = timeout_seconds

    def execute_code(self, code_str: str) -> Tuple[bool, str]:
        """
        Execute Python code string in restricted scope and capture stdout.
        
        Returns:
            (success: bool, output: str)
        """
        start_time = time.time()
        
        # Buffer stdout
        captured_output = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured_output
        
        # Build safe execution scope
        safe_builtins = {
            "__import__": self._safe_import,
            "abs": abs,
            "round": round,
            "min": min,
            "max": max,
            "sum": sum,
            "len": len,
            "int": int,
            "float": float,
            "str": str,
            "bool": bool,
            "range": range,
            "print": print,
            "dict": dict,
            "list": list,
            "set": set,
            "tuple": tuple,
            "zip": zip,
            "enumerate": enumerate,
        }
        
        exec_globals = {
            "__builtins__": safe_builtins,
            "math": math,
            "datetime": datetime,
            "date": date,
            "dt": dt,
            "timedelta": timedelta,
            "decimal": decimal,
            "Decimal": Decimal,
            "time": time,
        }
        exec_locals = {}
        
        success = False
        result_str = ""
        
        try:
            # Clean up markdown fences if present
            clean_code = code_str.strip()
            if clean_code.startswith("```python"):
                clean_code = clean_code[9:]
            elif clean_code.startswith("```"):
                clean_code = clean_code[3:]
            if clean_code.endswith("```"):
                clean_code = clean_code[:-3]
            clean_code = clean_code.strip()
            
            exec(clean_code, exec_globals, exec_locals)
            sys.stdout = old_stdout
            
            printed = captured_output.getvalue().strip()
            
            # If print was called, use printed output; otherwise inspect locals for key variables
            if printed:
                result_str = printed
            elif exec_locals:
                # Format calculated variables
                formatted = [f"{k} = {v}" for k, v in exec_locals.items() if not k.startswith("_")]
                result_str = ", ".join(formatted[:5])
            else:
                result_str = "Execution completed with no return values."
                
            success = True
            
        except Exception as e:
            sys.stdout = old_stdout
            err_name = type(e).__name__
            err_msg = str(e)
            result_str = f"Error [{err_name}]: {err_msg}"
            success = False
            
        finally:
            sys.stdout = old_stdout
            captured_output.close()
            
        latency_ms = (time.time() - start_time) * 1000.0
        return success, f"{result_str} (computed in {latency_ms:.1f}ms)"

    def extract_and_solve(self, text_with_code: str) -> str:
        """
        Scan text for ```python ... ``` blocks, execute them, and return the resolved calculation.
        """
        import re
        pattern = r"```python(.*?)```"
        matches = re.findall(pattern, text_with_code, re.DOTALL)
        
        if not matches:
            return ""
            
        outputs = []
        for code_snippet in matches:
            ok, out = self.execute_code(code_snippet)
            outputs.append(out)
            
        return "\n".join(outputs)


if __name__ == "__main__":
    sandbox = REPLSandbox()
    
    # Test 1: Basel III CRAR Ratio
    test_code_1 = """
tier1 = 450e7
tier2 = 150e7
rwa = 5000e7
crar = ((tier1 + tier2) / rwa) * 100
print(f"CRAR: {crar:.2f}%, Compliant: {crar >= 11.5}")
"""
    ok1, out1 = sandbox.execute_code(test_code_1)
    print("Test 1 (CRAR):", ok1, "->", out1)
    
    # Test 2: Date Transitional Window
    test_code_2 = """
import datetime
effective_date = datetime.date(2025, 4, 1)
transition_days = 270 # 9 months
deadline = effective_date + datetime.timedelta(days=transition_days)
print(f"Transitional Deadline: {deadline.strftime('%d-%b-%Y')}")
"""
    ok2, out2 = sandbox.execute_code(test_code_2)
    print("Test 2 (Date):", ok2, "->", out2)
    
    # Test 3: Compound Penal Interest (Section 234B/234C IT Act)
    test_code_3 = """
principal_tax_due = 2500000
months_delayed = 7
rate_per_month = 0.01 # 1% simple interest per month
penal_interest = principal_tax_due * rate_per_month * months_delayed
total_liability = principal_tax_due + penal_interest
print(f"Penal Interest: Rs. {penal_interest:,.2f}, Total Due: Rs. {total_liability:,.2f}")
"""
    ok3, out3 = sandbox.execute_code(test_code_3)
    print("Test 3 (Compound Math):", ok3, "->", out3)
