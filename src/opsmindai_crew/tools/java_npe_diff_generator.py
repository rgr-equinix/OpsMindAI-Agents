from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Dict, Any, List, Optional
import re
import difflib

class JavaNpeDiffGeneratorInput(BaseModel):
    """Input schema for Java NPE Code Diff Generator Tool."""
    original_code: str = Field(..., description="The original Java code containing the NPE issue")
    class_name: str = Field(..., description="The class name where the NPE occurred (e.g., 'DemoController')")
    method_name: str = Field(..., description="The method name where the NPE occurred (e.g., 'login')")
    error_line: int = Field(..., description="The line number where the NPE occurred")
    error_message: str = Field(..., description="The NPE error message details")
    variable_name: Optional[str] = Field(None, description="The specific variable name that was null (if known)")

class JavaNpeDiffGeneratorTool(BaseTool):
    """Tool for analyzing Java NullPointerException issues and generating code fixes with unified diff format."""

    name: str = "java_npe_diff_generator"
    description: str = (
        "Analyzes Java NullPointerException issues and generates smart fixes with proper unified diff format. "
        "Handles method calls on null, array access, and other NPE scenarios with defensive programming patterns. "
        "Supports Java-specific patterns including Spring Boot controllers and REST API structures."
    )
    args_schema: Type[BaseModel] = JavaNpeDiffGeneratorInput

    def _run(self, original_code: str, class_name: str, method_name: str, error_line: int, 
             error_message: str, variable_name: Optional[str] = None) -> str:
        try:
            # Parse the original code into lines
            original_lines = original_code.split('\n')
            
            # Analyze the NPE issue
            npe_analysis = self._analyze_npe_issue(original_lines, error_line, error_message, variable_name)
            
            # Generate the fixed code
            fixed_lines = self._generate_fixed_code(original_lines, npe_analysis, class_name, method_name)
            
            # Create unified diff
            diff_result = self._create_unified_diff(original_lines, fixed_lines, class_name, method_name)
            
            # Create comprehensive result
            result = f"""# Java NPE Fix Analysis for {class_name}.{method_name}()

## Issue Analysis:
- **Error Line**: {error_line}
- **NPE Type**: {npe_analysis['npe_type']}
- **Variable**: {npe_analysis['variable']}
- **Issue**: {npe_analysis['description']}

## Applied Fix:
{npe_analysis['fix_description']}

## Code Changes (Unified Diff):
```diff
{diff_result}

## Fixed Code:
```java
{''.join(fixed_lines)}

## Summary:
The fix adds proper null checking and defensive programming patterns to prevent the NullPointerException while maintaining the original code logic flow.
"""
            
            return result
            
        except Exception as e:
            return f"Error generating Java NPE diff: {str(e)}"

    def _analyze_npe_issue(self, lines: List[str], error_line: int, error_message: str, variable_name: Optional[str]) -> Dict[str, Any]:
        """Analyze the NPE issue to understand the problem and determine the fix strategy."""
        
        # Adjust for 0-based indexing
        line_index = max(0, error_line - 1)
        
        if line_index >= len(lines):
            line_index = len(lines) - 1
        
        problematic_line = lines[line_index].strip()
        
        analysis = {
            'line_index': line_index,
            'problematic_line': problematic_line,
            'variable': variable_name,
            'npe_type': 'unknown',
            'description': '',
            'fix_description': ''
        }
        
        # Detect NPE patterns
        if '.(' in problematic_line and variable_name:
            analysis['npe_type'] = 'method_call'
            analysis['description'] = f"Method call on null variable '{variable_name}'"
            analysis['fix_description'] = f"Added null check before calling method on '{variable_name}'"
        elif '[' in problematic_line and ']' in problematic_line:
            analysis['npe_type'] = 'array_access'
            analysis['description'] = "Array access on null reference"
            analysis['fix_description'] = "Added null check before array access"
        elif '.' in problematic_line:
            # Try to extract variable from the line
            if not variable_name:
                # Extract potential variable name before dot
                match = re.search(r'(\w+)\.', problematic_line)
                if match:
                    analysis['variable'] = match.group(1)
                    variable_name = match.group(1)
            
            analysis['npe_type'] = 'field_access'
            analysis['description'] = f"Field access on null variable '{variable_name or 'unknown'}'"
            analysis['fix_description'] = f"Added null check before accessing field on '{variable_name or 'variable'}'"
        else:
            analysis['npe_type'] = 'general'
            analysis['description'] = "General null pointer exception"
            analysis['fix_description'] = "Added defensive null checking"
        
        return analysis

    def _generate_fixed_code(self, original_lines: List[str], analysis: Dict[str, Any], 
                           class_name: str, method_name: str) -> List[str]:
        """Generate the fixed code with appropriate null checks."""
        
        fixed_lines = original_lines.copy()
        line_index = analysis['line_index']
        problematic_line = analysis['problematic_line']
        variable_name = analysis['variable']
        npe_type = analysis['npe_type']
        
        # Get the indentation of the problematic line
        original_line_full = original_lines[line_index]
        indentation = len(original_line_full) - len(original_line_full.lstrip())
        indent_str = ' ' * indentation
        
        # Generate appropriate fix based on NPE type
        if npe_type == 'method_call' and variable_name:
            # Add null check before method call
            null_check = f"{indent_str}if ({variable_name} != null) {{"
            fixed_line = f"{indent_str}    {problematic_line}"
            close_brace = f"{indent_str}}}"
            
            # Handle return statements or add appropriate else
            if 'return' in problematic_line:
                else_clause = f"{indent_str}else {{"
                default_return = f"{indent_str}    return null; // Handle null case appropriately"
                else_close = f"{indent_str}}}"
                
                fixed_lines[line_index:line_index+1] = [
                    null_check,
                    fixed_line,
                    close_brace,
                    else_clause,
                    default_return,
                    else_close
                ]
            else:
                fixed_lines[line_index:line_index+1] = [
                    null_check,
                    fixed_line,
                    close_brace
                ]
        
        elif npe_type == 'field_access' and variable_name:
            # Add null check before field access
            null_check = f"{indent_str}if ({variable_name} != null) {{"
            fixed_line = f"{indent_str}    {problematic_line}"
            close_brace = f"{indent_str}}}"
            
            if 'return' in problematic_line:
                else_clause = f"{indent_str}else {{"
                default_return = f"{indent_str}    return null; // Handle null case"
                else_close = f"{indent_str}}}"
                
                fixed_lines[line_index:line_index+1] = [
                    null_check,
                    fixed_line,
                    close_brace,
                    else_clause,
                    default_return,
                    else_close
                ]
            else:
                fixed_lines[line_index:line_index+1] = [
                    null_check,
                    fixed_line,
                    close_brace
                ]
        
        elif npe_type == 'array_access':
            # Add null and length check for array access
            # Try to extract array variable name
            array_match = re.search(r'(\w+)\[', problematic_line)
            array_var = array_match.group(1) if array_match else 'array'
            
            null_check = f"{indent_str}if ({array_var} != null && {array_var}.length > 0) {{"
            fixed_line = f"{indent_str}    {problematic_line}"
            close_brace = f"{indent_str}}}"
            
            fixed_lines[line_index:line_index+1] = [
                null_check,
                fixed_line,
                close_brace
            ]
        
        else:
            # General null check
            if variable_name:
                null_check = f"{indent_str}if ({variable_name} != null) {{"
                fixed_line = f"{indent_str}    {problematic_line}"
                close_brace = f"{indent_str}}}"
                
                fixed_lines[line_index:line_index+1] = [
                    null_check,
                    fixed_line,
                    close_brace
                ]
            else:
                # Add a comment indicating manual review needed
                comment = f"{indent_str}// TODO: Add appropriate null check"
                fixed_lines.insert(line_index, comment)
        
        return fixed_lines

    def _create_unified_diff(self, original_lines: List[str], fixed_lines: List[str], 
                           class_name: str, method_name: str) -> str:
        """Create a unified diff showing the changes."""
        
        original_text = '\n'.join(original_lines)
        fixed_text = '\n'.join(fixed_lines)
        
        diff = difflib.unified_diff(
            original_text.splitlines(keepends=True),
            fixed_text.splitlines(keepends=True),
            fromfile=f"a/{class_name}.java",
            tofile=f"b/{class_name}.java",
            lineterm='',
            n=3  # Show 3 lines of context
        )
        
        return ''.join(diff)