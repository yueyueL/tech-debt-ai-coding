"""
AST-based Semantic Survival Analysis

Tracks code survival at the SEMANTIC level rather than syntactic (line-by-line).
This is more robust to:
- Formatting changes (whitespace, line breaks)
- Comment additions/removals
- Variable renaming (partial detection)
- Minor refactoring that preserves logic

Approach:
1. Parse code into AST
2. Extract semantic units (functions, classes, methods)
3. Create structural signatures for each unit
4. Compare signatures between original and current versions
5. Calculate semantic survival rate

Supported languages:
- Python (via ast module)
- JavaScript/TypeScript (via tree-sitter or regex fallback)
"""

import ast
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
import logging

logger = logging.getLogger(__name__)

# Try to import tree-sitter for JS/TS analysis (optional dependency)
_TREE_SITTER_AVAILABLE = False
try:
    import tree_sitter_javascript as _ts_js
    import tree_sitter_typescript as _ts_ts
    from tree_sitter import Language as _Language, Parser as _Parser
    _TREE_SITTER_AVAILABLE = True
except ImportError:
    pass


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class SemanticUnit:
    """A semantic unit of code (function, class, method)."""
    kind: str  # "function", "class", "method", "async_function"
    name: str
    signature: str  # Parameters/arguments signature
    body_hash: str  # Hash of normalized body structure
    line_start: int
    line_end: int
    complexity: int = 0  # Rough complexity estimate
    children: List["SemanticUnit"] = field(default_factory=list)
    
    @property
    def full_signature(self) -> str:
        """Full signature for matching."""
        return f"{self.kind}:{self.name}:{self.signature}"
    
    @property
    def structural_id(self) -> str:
        """Structural ID including body hash for exact matching."""
        return f"{self.full_signature}:{self.body_hash}"


@dataclass
class SemanticSurvivalResult:
    """Result of semantic survival analysis."""
    # Unit counts
    original_units: int = 0
    surviving_units: int = 0
    modified_units: int = 0  # Same signature, different body
    deleted_units: int = 0
    new_units: int = 0  # Units in current that weren't in original
    
    # Rates
    semantic_survival_rate: float = 0.0  # Units that exist with same/similar logic
    exact_survival_rate: float = 0.0  # Units with identical structure
    modification_rate: float = 0.0
    deletion_rate: float = 0.0
    
    # Details
    survived_names: List[str] = field(default_factory=list)
    modified_names: List[str] = field(default_factory=list)
    deleted_names: List[str] = field(default_factory=list)
    
    # Comparison with syntactic survival
    syntactic_survival_rate: float = 0.0  # For comparison
    semantic_vs_syntactic_delta: float = 0.0  # How much better semantic is


# ============================================================================
# Python AST Analysis
# ============================================================================

class PythonASTAnalyzer:
    """Extract semantic units from Python code."""
    
    def extract_units(self, code: str) -> List[SemanticUnit]:
        """Parse Python code and extract semantic units."""
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            logger.debug("Python parse error: %s", e)
            return []
        
        units = []
        self._extract_from_node(tree, units, code.splitlines())
        return units
    
    def _extract_from_node(
        self, 
        node: ast.AST, 
        units: List[SemanticUnit],
        lines: List[str],
        parent_class: str = ""
    ) -> None:
        """Recursively extract semantic units from AST."""
        
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef):
                unit = self._create_function_unit(child, lines, parent_class, is_async=False)
                units.append(unit)
                # Extract nested functions/classes
                self._extract_from_node(child, unit.children, lines)
                
            elif isinstance(child, ast.AsyncFunctionDef):
                unit = self._create_function_unit(child, lines, parent_class, is_async=True)
                units.append(unit)
                self._extract_from_node(child, unit.children, lines)
                
            elif isinstance(child, ast.ClassDef):
                unit = self._create_class_unit(child, lines)
                units.append(unit)
                # Extract methods within class
                self._extract_from_node(child, unit.children, lines, parent_class=child.name)
            else:
                # Continue searching in other nodes
                self._extract_from_node(child, units, lines, parent_class)
    
    def _create_function_unit(
        self, 
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        lines: List[str],
        parent_class: str,
        is_async: bool
    ) -> SemanticUnit:
        """Create a SemanticUnit from a function definition."""
        # Determine kind
        if parent_class:
            kind = "method"
        elif is_async:
            kind = "async_function"
        else:
            kind = "function"
        
        # Build parameter signature
        args = node.args
        params = []
        
        # Positional args
        for arg in args.args:
            param = arg.arg
            if arg.annotation:
                param += f":{self._annotation_str(arg.annotation)}"
            params.append(param)
        
        # *args
        if args.vararg:
            params.append(f"*{args.vararg.arg}")
        
        # **kwargs
        if args.kwarg:
            params.append(f"**{args.kwarg.arg}")
        
        signature = ",".join(params)
        
        # Calculate body hash (normalized structure)
        body_hash = self._hash_function_body(node)
        
        # Estimate complexity
        complexity = self._estimate_complexity(node)
        
        name = f"{parent_class}.{node.name}" if parent_class else node.name
        
        return SemanticUnit(
            kind=kind,
            name=name,
            signature=signature,
            body_hash=body_hash,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            complexity=complexity,
        )
    
    def _create_class_unit(self, node: ast.ClassDef, lines: List[str]) -> SemanticUnit:
        """Create a SemanticUnit from a class definition."""
        # Get base classes
        bases = [self._annotation_str(b) for b in node.bases]
        signature = ",".join(bases) if bases else ""
        
        # Hash class structure (method names and their signatures)
        body_hash = self._hash_class_body(node)
        
        return SemanticUnit(
            kind="class",
            name=node.name,
            signature=signature,
            body_hash=body_hash,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            complexity=0,
        )
    
    def _annotation_str(self, node: ast.AST) -> str:
        """Convert annotation AST to string."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Constant):
            return str(node.value)
        elif isinstance(node, ast.Subscript):
            return f"{self._annotation_str(node.value)}[...]"
        elif isinstance(node, ast.Attribute):
            return f"{self._annotation_str(node.value)}.{node.attr}"
        return "Any"
    
    def _hash_function_body(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        """Create a semantic hash of function body that preserves real edits."""
        normalized_body = [
            ast.dump(stmt, annotate_fields=True, include_attributes=False)
            for stmt in node.body
        ]
        structure_str = "|".join(normalized_body)
        return hashlib.md5(structure_str.encode()).hexdigest()[:8]
    
    def _hash_class_body(self, node: ast.ClassDef) -> str:
        """Create a structural hash of class body (method signatures)."""
        methods = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(item.name)
        
        methods_str = "|".join(sorted(methods))
        return hashlib.md5(methods_str.encode()).hexdigest()[:8]
    
    def _estimate_complexity(self, node: ast.AST) -> int:
        """Estimate cyclomatic complexity."""
        complexity = 1  # Base complexity
        
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
            elif isinstance(child, ast.comprehension):
                complexity += 1
        
        return complexity


# ============================================================================
# JavaScript/TypeScript Analysis (Regex-based fallback)
# ============================================================================

class RegexJavaScriptAnalyzer:
    """Extract semantic units from JavaScript/TypeScript code using regex (fallback)."""
    
    # Patterns for extracting functions and classes
    FUNCTION_PATTERN = re.compile(
        r'^[ \t]*(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)',
        re.MULTILINE
    )
    
    ARROW_FUNCTION_PATTERN = re.compile(
        r'^[ \t]*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>',
        re.MULTILINE
    )
    
    METHOD_PATTERN = re.compile(
        r'^[ \t]*(?:async\s+)?(\w+)\s*\(([^)]*)\)\s*\{',
        re.MULTILINE
    )
    
    CLASS_PATTERN = re.compile(
        r'^[ \t]*(?:export\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?',
        re.MULTILINE
    )
    
    def extract_units(self, code: str) -> List[SemanticUnit]:
        """Extract semantic units from JavaScript/TypeScript code."""
        units = []
        lines = code.splitlines()
        
        # Extract functions
        for match in self.FUNCTION_PATTERN.finditer(code):
            name = match.group(1)
            params = match.group(2).strip()
            line_num = code[:match.start()].count('\n') + 1
            
            # Find function end (approximate by brace matching)
            end_line = self._find_block_end(lines, line_num - 1)
            
            body_hash = self._hash_body(lines[line_num-1:end_line])
            
            units.append(SemanticUnit(
                kind="function",
                name=name,
                signature=self._normalize_params(params),
                body_hash=body_hash,
                line_start=line_num,
                line_end=end_line,
            ))
        
        # Extract arrow functions
        for match in self.ARROW_FUNCTION_PATTERN.finditer(code):
            name = match.group(1)
            line_num = code[:match.start()].count('\n') + 1
            end_line = self._find_block_end(lines, line_num - 1)
            
            body_hash = self._hash_body(lines[line_num-1:end_line])
            
            units.append(SemanticUnit(
                kind="arrow_function",
                name=name,
                signature="",
                body_hash=body_hash,
                line_start=line_num,
                line_end=end_line,
            ))
        
        # Extract classes
        for match in self.CLASS_PATTERN.finditer(code):
            name = match.group(1)
            extends = match.group(2) or ""
            line_num = code[:match.start()].count('\n') + 1
            end_line = self._find_block_end(lines, line_num - 1)
            
            # Extract methods within class
            class_body = "\n".join(lines[line_num:end_line-1])
            body_hash = self._hash_class_methods(class_body)
            
            units.append(SemanticUnit(
                kind="class",
                name=name,
                signature=extends,
                body_hash=body_hash,
                line_start=line_num,
                line_end=end_line,
            ))
        
        return units
    
    def _normalize_params(self, params: str) -> str:
        """Normalize parameter string (remove types, defaults)."""
        if not params:
            return ""
        
        # Split by comma, extract just param names
        param_names = []
        for param in params.split(','):
            param = param.strip()
            # Remove type annotation (: Type)
            if ':' in param:
                param = param.split(':')[0].strip()
            # Remove default value (= value)
            if '=' in param:
                param = param.split('=')[0].strip()
            # Remove rest/spread
            param = param.lstrip('.')
            if param:
                param_names.append(param)
        
        return ",".join(param_names)
    
    def _find_block_end(self, lines: List[str], start_idx: int) -> int:
        """Find the end of a code block by brace matching."""
        brace_count = 0
        started = False
        
        for i in range(start_idx, min(start_idx + 500, len(lines))):
            line = lines[i]
            for char in line:
                if char == '{':
                    brace_count += 1
                    started = True
                elif char == '}':
                    brace_count -= 1
                    if started and brace_count == 0:
                        return i + 1
        
        return min(start_idx + 50, len(lines))
    
    def _hash_body(self, lines: List[str]) -> str:
        """Create a normalized body hash for regex-extracted JS/TS units."""
        normalized_lines = []
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("//"):
                continue
            normalized_lines.append(" ".join(stripped.split()))
        structure_str = "\n".join(normalized_lines)
        return hashlib.md5(structure_str.encode()).hexdigest()[:8]
    
    def _hash_class_methods(self, class_body: str) -> str:
        """Extract and hash method names from class body."""
        methods = []
        for match in self.METHOD_PATTERN.finditer(class_body):
            methods.append(match.group(1))
        
        methods_str = "|".join(sorted(methods))
        return hashlib.md5(methods_str.encode()).hexdigest()[:8]


# ============================================================================
# JavaScript/TypeScript Analysis (tree-sitter, preferred)
# ============================================================================

class TreeSitterJavaScriptAnalyzer:
    """Extract semantic units from JavaScript/TypeScript using tree-sitter AST."""

    def __init__(self, language: str = "javascript"):
        self._parser = _Parser()
        if language == "typescript":
            lang = _Language(_ts_ts.language_typescript())
        elif language == "tsx":
            lang = _Language(_ts_ts.language_tsx())
        else:
            lang = _Language(_ts_js.language())
        self._parser.language = lang

    def extract_units(self, code: str) -> List[SemanticUnit]:
        tree = self._parser.parse(code.encode("utf-8"))
        units: List[SemanticUnit] = []
        self._extract_from_node(tree.root_node, units, code.encode("utf-8"))
        return units

    def _extract_from_node(
        self, node, units: List[SemanticUnit], source: bytes,
        parent_class: str = ""
    ) -> None:
        for child in node.children:
            if child.type == "function_declaration":
                unit = self._create_function_unit(child, source, parent_class)
                if unit:
                    units.append(unit)
                    self._extract_from_node(child, unit.children, source)

            elif child.type in ("lexical_declaration", "variable_declaration"):
                for declarator in child.children:
                    if declarator.type == "variable_declarator":
                        name_node = declarator.child_by_field_name("name")
                        value_node = declarator.child_by_field_name("value")
                        if value_node and value_node.type == "arrow_function" and name_node:
                            unit = self._create_arrow_unit(name_node, value_node, source, parent_class)
                            if unit:
                                units.append(unit)

            elif child.type == "class_declaration":
                unit = self._create_class_unit(child, source)
                if unit:
                    units.append(unit)
                    body = child.child_by_field_name("body")
                    if body:
                        self._extract_from_node(body, unit.children, source, parent_class=unit.name)

            elif child.type == "method_definition" and parent_class:
                unit = self._create_method_unit(child, source, parent_class)
                if unit:
                    units.append(unit)

            elif child.type in ("export_statement", "export_default_declaration"):
                self._extract_from_node(child, units, source, parent_class)

            elif child.type in ("program", "statement_block"):
                self._extract_from_node(child, units, source, parent_class)

    def _get_text(self, node, source: bytes) -> str:
        return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")

    def _create_function_unit(self, node, source: bytes, parent_class: str) -> Optional[SemanticUnit]:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None
        name = self._get_text(name_node, source)
        is_async = any(c.type == "async" for c in node.children)

        params_node = node.child_by_field_name("parameters")
        signature = self._extract_params(params_node, source) if params_node else ""

        body_node = node.child_by_field_name("body")
        body_hash = self._hash_body_ast(body_node, source) if body_node else ""

        kind = "method" if parent_class else ("async_function" if is_async else "function")
        full_name = f"{parent_class}.{name}" if parent_class else name

        return SemanticUnit(
            kind=kind, name=full_name, signature=signature, body_hash=body_hash,
            line_start=node.start_point[0] + 1, line_end=node.end_point[0] + 1,
            complexity=self._estimate_complexity(body_node) if body_node else 0,
        )

    def _create_arrow_unit(self, name_node, value_node, source: bytes, parent_class: str) -> Optional[SemanticUnit]:
        name = self._get_text(name_node, source)
        params_node = value_node.child_by_field_name("parameters")
        if not params_node:
            params_node = value_node.child_by_field_name("parameter")
        signature = self._extract_params(params_node, source) if params_node else ""

        body_node = value_node.child_by_field_name("body")
        body_hash = self._hash_body_ast(body_node, source) if body_node else ""

        return SemanticUnit(
            kind="arrow_function", name=name, signature=signature, body_hash=body_hash,
            line_start=name_node.start_point[0] + 1, line_end=value_node.end_point[0] + 1,
        )

    def _create_class_unit(self, node, source: bytes) -> Optional[SemanticUnit]:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None
        name = self._get_text(name_node, source)

        heritage = ""
        for child in node.children:
            if child.type == "class_heritage":
                heritage = self._get_text(child, source).replace("extends ", "").strip()

        body_node = node.child_by_field_name("body")
        body_hash = self._hash_class_body_ast(body_node, source) if body_node else ""

        return SemanticUnit(
            kind="class", name=name, signature=heritage, body_hash=body_hash,
            line_start=node.start_point[0] + 1, line_end=node.end_point[0] + 1,
        )

    def _create_method_unit(self, node, source: bytes, parent_class: str) -> Optional[SemanticUnit]:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None
        name = self._get_text(name_node, source)

        params_node = node.child_by_field_name("parameters")
        signature = self._extract_params(params_node, source) if params_node else ""

        body_node = node.child_by_field_name("body")
        body_hash = self._hash_body_ast(body_node, source) if body_node else ""

        return SemanticUnit(
            kind="method", name=f"{parent_class}.{name}", signature=signature,
            body_hash=body_hash,
            line_start=node.start_point[0] + 1, line_end=node.end_point[0] + 1,
            complexity=self._estimate_complexity(body_node) if body_node else 0,
        )

    def _extract_params(self, node, source: bytes) -> str:
        if not node:
            return ""
        params = []
        for child in node.children:
            if child.type in ("identifier", "shorthand_property_identifier_pattern"):
                params.append(self._get_text(child, source))
            elif child.type in ("required_parameter", "optional_parameter"):
                pattern_node = child.child_by_field_name("pattern")
                if pattern_node:
                    params.append(self._get_text(pattern_node, source))
            elif child.type == "rest_pattern":
                inner = child.children[-1] if child.children else None
                params.append("..." + self._get_text(inner, source) if inner else "...rest")
            elif child.type == "assignment_pattern":
                left = child.child_by_field_name("left")
                if left:
                    params.append(self._get_text(left, source))
        return ",".join(params)

    def _hash_body_ast(self, node, source: bytes) -> str:
        body_text = self._get_text(node, source)
        normalized = "\n".join(" ".join(line.split()) for line in body_text.splitlines() if line.strip())
        return hashlib.md5(normalized.encode()).hexdigest()[:8]

    def _walk_for_structure(self, node, structure: list) -> None:
        _TYPE_MAP = {
            "if_statement": "IF", "for_statement": "FOR", "for_in_statement": "FOR",
            "while_statement": "WHILE", "try_statement": "TRY",
            "return_statement": "RET", "throw_statement": "THROW",
            "assignment_expression": "ASSIGN", "augmented_assignment_expression": "AUGASSIGN",
            "call_expression": "CALL", "yield_expression": "YIELD",
            "await_expression": "AWAIT", "switch_statement": "SWITCH",
        }
        if node.type in _TYPE_MAP:
            structure.append(_TYPE_MAP[node.type])
        for child in node.children:
            self._walk_for_structure(child, structure)

    def _hash_class_body_ast(self, node, source: bytes) -> str:
        methods = []
        for child in node.children:
            if child.type == "method_definition":
                name_node = child.child_by_field_name("name")
                if name_node:
                    methods.append(self._get_text(name_node, source))
        methods_str = "|".join(sorted(methods))
        return hashlib.md5(methods_str.encode()).hexdigest()[:8]

    def _estimate_complexity(self, node) -> int:
        complexity = 1
        _BRANCHING = {
            "if_statement", "for_statement", "for_in_statement",
            "while_statement", "catch_clause", "ternary_expression", "switch_case",
        }
        def walk(n):
            nonlocal complexity
            if n.type in _BRANCHING:
                complexity += 1
            for child in n.children:
                walk(child)
        walk(node)
        return complexity


# ============================================================================
# Semantic Comparison
# ============================================================================

def compare_semantic_units(
    original_units: List[SemanticUnit],
    current_units: List[SemanticUnit],
) -> SemanticSurvivalResult:
    """
    Compare semantic units between original and current versions.
    
    Matching strategy:
    1. Exact match: same name + signature + body hash
    2. Modified match: same name + signature, different body
    3. Renamed match: same body hash, different name (fuzzy)
    """
    result = SemanticSurvivalResult()
    result.original_units = len(original_units)
    
    # Build lookup maps
    current_by_name: Dict[str, SemanticUnit] = {u.name: u for u in current_units}
    current_by_signature: Dict[str, SemanticUnit] = {u.full_signature: u for u in current_units}
    current_by_body: Dict[str, List[SemanticUnit]] = {}
    for u in current_units:
        if u.body_hash not in current_by_body:
            current_by_body[u.body_hash] = []
        current_by_body[u.body_hash].append(u)
    
    matched_current: Set[str] = set()
    
    for orig in original_units:
        # Try exact match by full signature
        if orig.full_signature in current_by_signature:
            current = current_by_signature[orig.full_signature]
            if orig.body_hash == current.body_hash:
                # Exact match - identical
                result.surviving_units += 1
                result.survived_names.append(orig.name)
            else:
                # Same signature, different body - modified
                result.modified_units += 1
                result.modified_names.append(orig.name)
            matched_current.add(current.name)
            continue
        
        # Try match by name only
        if orig.name in current_by_name:
            current = current_by_name[orig.name]
            # Name exists but signature changed - still counts as modified survival
            result.modified_units += 1
            result.modified_names.append(orig.name)
            matched_current.add(current.name)
            continue
        
        # Try match by body hash (renamed)
        if orig.body_hash in current_by_body:
            candidates = current_by_body[orig.body_hash]
            for candidate in candidates:
                if candidate.name not in matched_current:
                    # Same body, different name - renamed but survived
                    result.surviving_units += 1
                    result.survived_names.append(f"{orig.name}->{candidate.name}")
                    matched_current.add(candidate.name)
                    break
            else:
                # All candidates already matched
                result.deleted_units += 1
                result.deleted_names.append(orig.name)
            continue
        
        # No match found - deleted
        result.deleted_units += 1
        result.deleted_names.append(orig.name)
    
    # Count new units (in current but not matched to original)
    for current in current_units:
        if current.name not in matched_current:
            result.new_units += 1
    
    # Calculate rates
    if result.original_units > 0:
        # Semantic survival = units that exist (exact + modified)
        result.semantic_survival_rate = round(
            (result.surviving_units + result.modified_units) / result.original_units, 4
        )
        result.exact_survival_rate = round(
            result.surviving_units / result.original_units, 4
        )
        result.modification_rate = round(
            result.modified_units / result.original_units, 4
        )
        result.deletion_rate = round(
            result.deleted_units / result.original_units, 4
        )
    
    return result


def _flatten_units(units: List[SemanticUnit]) -> List[SemanticUnit]:
    flattened: List[SemanticUnit] = []
    for unit in units:
        flattened.append(unit)
        if unit.children:
            flattened.extend(_flatten_units(unit.children))
    return flattened


def _unit_overlaps_ranges(unit: SemanticUnit, tracked_line_ranges: Sequence[Tuple[int, int]]) -> bool:
    for start, end in tracked_line_ranges:
        if unit.line_start <= end and unit.line_end >= start:
            return True
    return False


def _remove_enclosing_units(units: List[SemanticUnit]) -> List[SemanticUnit]:
    """
    Prefer the most specific overlapping units.

    If a class and one of its methods both overlap the tracked lines, keep the
    method and drop the enclosing class for the survival calculation.
    """
    filtered: List[SemanticUnit] = []
    for unit in units:
        enclosed = False
        for other in units:
            if unit is other:
                continue
            if (
                unit.line_start <= other.line_start
                and unit.line_end >= other.line_end
                and (unit.line_start != other.line_start or unit.line_end != other.line_end)
            ):
                enclosed = True
                break
        if not enclosed:
            filtered.append(unit)
    return filtered


# ============================================================================
# Main Analysis Function
# ============================================================================

def analyze_semantic_survival(
    original_code: str,
    current_code: str,
    language: str,
    syntactic_survival_rate: float = 0.0,
    tracked_line_ranges: Optional[List[Tuple[int, int]]] = None,
) -> SemanticSurvivalResult:
    """
    Analyze semantic survival of code.
    
    Args:
        original_code: Original AI-written code
        current_code: Current code at HEAD
        language: Programming language (python, javascript, typescript)
        syntactic_survival_rate: Line-based survival rate for comparison
        
    Returns:
        SemanticSurvivalResult with detailed survival metrics
    """
    # Select analyzer based on language
    if language == "python":
        analyzer = PythonASTAnalyzer()
    elif language in ("javascript", "typescript"):
        if _TREE_SITTER_AVAILABLE:
            try:
                analyzer = TreeSitterJavaScriptAnalyzer(language=language)
            except Exception:
                logger.debug("tree-sitter init failed for %s, falling back to regex", language)
                analyzer = RegexJavaScriptAnalyzer()
        else:
            analyzer = RegexJavaScriptAnalyzer()
    else:
        # Unsupported language - return empty result
        return SemanticSurvivalResult()
    
    original_units = _flatten_units(analyzer.extract_units(original_code))
    current_units = _flatten_units(analyzer.extract_units(current_code))

    if tracked_line_ranges:
        original_units = [
            unit for unit in original_units
            if _unit_overlaps_ranges(unit, tracked_line_ranges)
        ]
        original_units = _remove_enclosing_units(original_units)
    
    if not original_units:
        # No semantic units found - can't analyze
        return SemanticSurvivalResult()
    
    # Compare units
    result = compare_semantic_units(original_units, current_units)
    
    # Add comparison with syntactic survival
    result.syntactic_survival_rate = syntactic_survival_rate
    result.semantic_vs_syntactic_delta = round(
        result.semantic_survival_rate - syntactic_survival_rate, 4
    )
    
    return result


def analyze_file_semantic_survival(
    original_content: str,
    current_content: str,
    file_path: str,
    syntactic_survival_rate: float = 0.0,
    tracked_line_ranges: Optional[List[Tuple[int, int]]] = None,
) -> Dict[str, Any]:
    """
    Convenience function to analyze a single file.
    
    Args:
        original_content: Original file content
        current_content: Current file content
        file_path: Path to file (for language detection)
        syntactic_survival_rate: Line-based survival for comparison
        
    Returns:
        Dictionary with survival metrics
    """
    # Detect language from extension
    ext = Path(file_path).suffix.lower()
    lang_map = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
    }
    language = lang_map.get(ext, "unknown")
    
    if language == "unknown":
        return {"supported": False, "language": "unknown"}
    
    result = analyze_semantic_survival(
        original_content,
        current_content,
        language,
        syntactic_survival_rate,
        tracked_line_ranges=tracked_line_ranges,
    )
    
    return {
        "supported": True,
        "language": language,
        "original_units": result.original_units,
        "surviving_units": result.surviving_units,
        "modified_units": result.modified_units,
        "deleted_units": result.deleted_units,
        "new_units": result.new_units,
        "semantic_survival_rate": result.semantic_survival_rate,
        "exact_survival_rate": result.exact_survival_rate,
        "modification_rate": result.modification_rate,
        "deletion_rate": result.deletion_rate,
        "syntactic_survival_rate": result.syntactic_survival_rate,
        "semantic_vs_syntactic_delta": result.semantic_vs_syntactic_delta,
        "survived_names": result.survived_names,
        "modified_names": result.modified_names,
        "deleted_names": result.deleted_names,
    }
