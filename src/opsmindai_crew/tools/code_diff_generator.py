from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Dict, Any, List
import re
import json

class CodeDiffGeneratorInput(BaseModel):
    """Input schema for Code Diff Generator Tool."""
    error_analysis: str = Field(
        ...,
        description="The error analysis containing error type, class name, method name, line number, and error details"
    )
    file_path: str = Field(
        ...,
        description="The file path where the error occurred (e.g., 'src/main/java/com/example/PaymentService.java')"
    )
    programming_language: str = Field(
        default="java",
        description="The programming language of the file (java, python, javascript, etc.)"
    )

class CodeDiffGeneratorTool(BaseTool):
    """Tool for generating git diff format code suggestions to fix common programming errors."""

    name: str = "code_diff_generator"
    description: str = (
        "Generates git diff format code suggestions for fixing common programming errors "
        "like NullPointerException, FileNotFoundException, resource leaks, configuration errors, "
        "database connection issues, and API timeout issues. Takes error analysis and file path "
        "as input and returns properly formatted git diff output."
    )
    args_schema: Type[BaseModel] = CodeDiffGeneratorInput

    def _run(self, error_analysis: str, file_path: str, programming_language: str = "java") -> str:
        try:
            # Parse error analysis to extract key information
            error_info = self._parse_error_analysis(error_analysis)
            
            # Generate appropriate fix based on error type
            fix_suggestion = self._generate_fix_suggestion(error_info, programming_language)
            
            # Format as git diff
            git_diff = self._format_as_git_diff(file_path, error_info, fix_suggestion)
            
            return git_diff
            
        except Exception as e:
            return f"Error generating code diff: {str(e)}"

    def _parse_error_analysis(self, error_analysis: str) -> Dict[str, Any]:
        """Parse error analysis to extract relevant information."""
        error_info = {
            'error_type': '',
            'class_name': '',
            'method_name': '',
            'line_number': 0,
            'error_message': '',
            'context': ''
        }
        
        # Extract error type
        if 'NullPointerException' in error_analysis or 'null pointer' in error_analysis.lower():
            error_info['error_type'] = 'NullPointerException'
        elif 'FileNotFoundException' in error_analysis or 'file not found' in error_analysis.lower():
            error_info['error_type'] = 'FileNotFoundException'
        elif 'resource leak' in error_analysis.lower() or 'connection not closed' in error_analysis.lower():
            error_info['error_type'] = 'ResourceLeak'
        elif 'configuration' in error_analysis.lower() or 'config' in error_analysis.lower():
            error_info['error_type'] = 'ConfigurationError'
        elif 'database' in error_analysis.lower() or 'sql' in error_analysis.lower():
            error_info['error_type'] = 'DatabaseError'
        elif 'timeout' in error_analysis.lower() or 'connection timeout' in error_analysis.lower():
            error_info['error_type'] = 'TimeoutError'
        else:
            error_info['error_type'] = 'GeneralError'
        
        # Extract class name
        class_match = re.search(r'class\s+(\w+)', error_analysis)
        if class_match:
            error_info['class_name'] = class_match.group(1)
        
        # Extract method name
        method_match = re.search(r'method\s+(\w+)', error_analysis)
        if method_match:
            error_info['method_name'] = method_match.group(1)
        
        # Extract line number
        line_match = re.search(r'line\s+(\d+)', error_analysis)
        if line_match:
            error_info['line_number'] = int(line_match.group(1))
        
        error_info['error_message'] = error_analysis
        
        return error_info

    def _generate_fix_suggestion(self, error_info: Dict[str, Any], language: str) -> Dict[str, Any]:
        """Generate fix suggestion based on error type and programming language."""
        error_type = error_info['error_type']
        
        if error_type == 'NullPointerException':
            return self._generate_null_check_fix(error_info, language)
        elif error_type == 'ResourceLeak':
            return self._generate_resource_leak_fix(error_info, language)
        elif error_type == 'FileNotFoundException':
            return self._generate_file_not_found_fix(error_info, language)
        elif error_type == 'ConfigurationError':
            return self._generate_config_error_fix(error_info, language)
        elif error_type == 'DatabaseError':
            return self._generate_database_error_fix(error_info, language)
        elif error_type == 'TimeoutError':
            return self._generate_timeout_error_fix(error_info, language)
        else:
            return self._generate_general_error_fix(error_info, language)

    def _generate_null_check_fix(self, error_info: Dict[str, Any], language: str) -> Dict[str, Any]:
        """Generate null check fix."""
        if language.lower() == 'java':
            return {
                'old_code': '    return paymentGateway.charge(request.getAmount());',
                'new_code': '''    if (request == null || request.getAmount() == null) {
        throw new IllegalArgumentException("Payment request cannot be null");
    }
    return paymentGateway.charge(request.getAmount());''',
                'line_start': error_info.get('line_number', 45),
                'context_lines': 3
            }
        elif language.lower() == 'python':
            return {
                'old_code': '    return payment_gateway.charge(request.amount)',
                'new_code': '''    if request is None or request.amount is None:
        raise ValueError("Payment request cannot be None")
    return payment_gateway.charge(request.amount)''',
                'line_start': error_info.get('line_number', 45),
                'context_lines': 3
            }
        else:  # JavaScript
            return {
                'old_code': '    return paymentGateway.charge(request.amount);',
                'new_code': '''    if (!request || request.amount === null || request.amount === undefined) {
        throw new Error("Payment request cannot be null or undefined");
    }
    return paymentGateway.charge(request.amount);''',
                'line_start': error_info.get('line_number', 45),
                'context_lines': 3
            }

    def _generate_resource_leak_fix(self, error_info: Dict[str, Any], language: str) -> Dict[str, Any]:
        """Generate resource leak fix."""
        if language.lower() == 'java':
            return {
                'old_code': '''    Connection conn = DriverManager.getConnection(url);
    Statement stmt = conn.createStatement();
    ResultSet rs = stmt.executeQuery(query);''',
                'new_code': '''    try (Connection conn = DriverManager.getConnection(url);
         Statement stmt = conn.createStatement();
         ResultSet rs = stmt.executeQuery(query)) {''',
                'line_start': error_info.get('line_number', 30),
                'context_lines': 3
            }
        elif language.lower() == 'python':
            return {
                'old_code': '''    file = open(filename, 'r')
    content = file.read()''',
                'new_code': '''    with open(filename, 'r') as file:
        content = file.read()''',
                'line_start': error_info.get('line_number', 30),
                'context_lines': 2
            }
        else:
            return self._generate_general_error_fix(error_info, language)

    def _generate_file_not_found_fix(self, error_info: Dict[str, Any], language: str) -> Dict[str, Any]:
        """Generate file not found fix."""
        if language.lower() == 'java':
            return {
                'old_code': '    Properties props = new Properties();',
                'new_code': '''    Properties props = new Properties();
    if (!new File(configPath).exists()) {
        throw new FileNotFoundException("Config file not found: " + configPath);
    }''',
                'line_start': error_info.get('line_number', 25),
                'context_lines': 3
            }
        elif language.lower() == 'python':
            return {
                'old_code': '    with open(config_path, \'r\') as f:',
                'new_code': '''    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(config_path, 'r') as f:''',
                'line_start': error_info.get('line_number', 25),
                'context_lines': 3
            }
        else:
            return self._generate_general_error_fix(error_info, language)

    def _generate_config_error_fix(self, error_info: Dict[str, Any], language: str) -> Dict[str, Any]:
        """Generate configuration error fix."""
        return {
            'old_code': '    String dbUrl = System.getProperty("db.url");',
            'new_code': '''    String dbUrl = System.getProperty("db.url");
    if (dbUrl == null || dbUrl.isEmpty()) {
        throw new IllegalStateException("Database URL not configured. Please set 'db.url' property");
    }''',
            'line_start': error_info.get('line_number', 20),
            'context_lines': 3
        }

    def _generate_database_error_fix(self, error_info: Dict[str, Any], language: str) -> Dict[str, Any]:
        """Generate database error fix."""
        if language.lower() == 'java':
            return {
                'old_code': '    Connection conn = DriverManager.getConnection(url, user, password);',
                'new_code': '''    Connection conn = null;
    try {
        conn = DriverManager.getConnection(url, user, password);
        conn.setAutoCommit(false);
    } catch (SQLException e) {
        if (conn != null) {
            conn.rollback();
        }
        throw new RuntimeException("Database connection failed: " + e.getMessage(), e);
    }''',
                'line_start': error_info.get('line_number', 35),
                'context_lines': 5
            }
        else:
            return self._generate_general_error_fix(error_info, language)

    def _generate_timeout_error_fix(self, error_info: Dict[str, Any], language: str) -> Dict[str, Any]:
        """Generate timeout error fix."""
        if language.lower() == 'java':
            return {
                'old_code': '    HttpURLConnection connection = (HttpURLConnection) url.openConnection();',
                'new_code': '''    HttpURLConnection connection = (HttpURLConnection) url.openConnection();
    connection.setConnectTimeout(5000); // 5 seconds
    connection.setReadTimeout(10000);   // 10 seconds''',
                'line_start': error_info.get('line_number', 40),
                'context_lines': 3
            }
        elif language.lower() == 'javascript':
            return {
                'old_code': '    const response = await fetch(url);',
                'new_code': '''    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000);
    const response = await fetch(url, { 
        signal: controller.signal,
        timeout: 5000 
    });
    clearTimeout(timeoutId);''',
                'line_start': error_info.get('line_number', 40),
                'context_lines': 4
            }
        else:
            return self._generate_general_error_fix(error_info, language)

    def _generate_general_error_fix(self, error_info: Dict[str, Any], language: str) -> Dict[str, Any]:
        """Generate general error handling fix."""
        if language.lower() == 'java':
            return {
                'old_code': '    processData(data);',
                'new_code': '''    try {
        processData(data);
    } catch (Exception e) {
        logger.error("Error processing data: " + e.getMessage(), e);
        throw new RuntimeException("Processing failed", e);
    }''',
                'line_start': error_info.get('line_number', 50),
                'context_lines': 3
            }
        elif language.lower() == 'python':
            return {
                'old_code': '    process_data(data)',
                'new_code': '''    try:
        process_data(data)
    except Exception as e:
        logger.error(f"Error processing data: {e}")
        raise RuntimeError("Processing failed") from e''',
                'line_start': error_info.get('line_number', 50),
                'context_lines': 3
            }
        else:
            return {
                'old_code': '    processData(data);',
                'new_code': '''    try {
        processData(data);
    } catch (error) {
        console.error("Error processing data:", error);
        throw new Error("Processing failed: " + error.message);
    }''',
                'line_start': error_info.get('line_number', 50),
                'context_lines': 3
            }

    def _format_as_git_diff(self, file_path: str, error_info: Dict[str, Any], fix_suggestion: Dict[str, Any]) -> str:
        """Format the fix suggestion as a git diff."""
        line_start = fix_suggestion.get('line_start', 45)
        context_lines = fix_suggestion.get('context_lines', 3)
        old_code = fix_suggestion.get('old_code', '')
        new_code = fix_suggestion.get('new_code', '')
        
        # Generate context lines
        before_context = self._generate_context_lines(error_info, line_start - context_lines, context_lines)
        after_context = self._generate_context_lines(error_info, line_start + 1, context_lines)
        
        # Count lines for diff header
        old_lines = len(old_code.split('\n'))
        new_lines = len(new_code.split('\n'))
        
        diff = f"""--- a/{file_path}
+++ b/{file_path}
@@ -{line_start},{old_lines + context_lines * 2} +{line_start},{new_lines + context_lines * 2} @@
{before_context}
-{old_code.replace(chr(10), chr(10) + '-')}
+{new_code.replace(chr(10), chr(10) + '+')}
{after_context}"""
        
        return diff

    def _generate_context_lines(self, error_info: Dict[str, Any], start_line: int, num_lines: int) -> str:
        """Generate context lines for the diff."""
        context = []
        method_name = error_info.get('method_name', 'processMethod')
        class_name = error_info.get('class_name', 'ExampleClass')
        
        for i in range(num_lines):
            line_num = start_line + i
            if line_num <= 0:
                continue
                
            if i == 0:
                context.append(f"     public {method_name}Type {method_name}({class_name}Request request) {{")
            elif i == 1:
                context.append("         // Method implementation")
            else:
                context.append("         // Additional context")
        
        return '\n'.join(context)