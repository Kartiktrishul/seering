CodebaseAnalyzer Class Documentation
Overview
The CodebaseAnalyzer class unifies Python codebase analysis by integrating:

AST Parsing: Extracts detailed information (functions, classes, methods, imports, variables, control structures, function calls, comments) using ast and tokenize, replacing CodeAnalyzer and extract_ast_info.
Dependency Graph: Constructs a directed graph of module dependencies (imports, function calls) using NetworkX, replacing DependencyGraph.
Directory Structure: Generates a hierarchical directory tree, incorporating print_directory_structure.

Purpose
The class is designed to:

Process large codebases by filtering files (>5KB, non-Python).
Output to terminal (directory structure, parsing progress, graph summary).
Return structured data for:
Integration with codebase_summarizer.py (API-based summarization).
LLM training (tokenization: CodeBERT; vectorization: GraphCodeBERT).


Support threading for non-blocking execution.
Adhere to requirements: no docstrings, minimal imports (os, ast, networkx, tokenize, io, utils.load_codebase), terminal-only output.

Key Features

Unified Analysis: Combines directory traversal, AST parsing, and graph construction.
Scalability: Filters large/non-Python files for large codebases.
LLM Compatibility: Outputs text (directory, DOT graph) and structured data (AST dict) for tokenization and vectorization.
API Integration: Matches ast_results and to_dot for API prompts and output.

Global Variables
Defined outside the class, used for analysis:

RESERVED_WORDS

Type: Set
Description: Python reserved keywords (e.g., if, for, class) from keyword.kwlist.
Purpose: Prevents misidentification of keywords as variables/functions.
Usage: Filters names in analyze_code.


INBUILT_FUNCTIONS

Type: Set
Description: Built-in function names (e.g., print, len) from dir(builtins).
Purpose: Classifies function calls as built-in (inbuilt_func) or user-defined (user_func).
Usage: Populates inbuilt_func/inbuilt_method in analyze_code.


INBUILT_DATASTRUCTURES

Type: Set
Description: Built-in data structure names (e.g., list, dict, set).
Purpose: Identifies classes inheriting these types in is_probably_datastructure.
Usage: Flags classes as data structures (user_ds) in analyze_code.



Class Variables
Initialized in __init__, these store analysis state/results:

self.base_path

Type: String
Description: Root directory path (e.g., ./codebase).
Purpose: Base for file loading and directory traversal.
Usage: Used in print_directory_structure and analyze (via load_codebase).


self.graph

Type: networkx.DiGraph
Description: Directed graph with module nodes (e.g., subdir.file1) and dependency edges (e.g., module1 -> os).
Purpose: Stores dependency graph for analysis/visualization.
Usage: Built in analyze, converted to DOT in to_dot.


self.parsed

Type: Dictionary ({file_path: analysis_info})
Description: Maps file paths (e.g., ./codebase/file1.py) to AST results:
functions: List of function details (name, args, returns, decorators, lineno, return_exprs).
classes: List of class details (name, bases, lineno, is_datastructure).
methods: List of method details (like functions).
imports: List of imports (module, name, asname).
variables: Sorted set of variable names.
control_structures: List of control structures (type, lineno, condition).
function_calls: List of all function calls (name, lineno, args).
user_function_calls: List of user-defined function calls.
user_func: Set of user-defined function names.
inbuilt_func: Set of built-in function names.
user_method: Set of user-defined method names.
inbuilt_method: Set of built-in method names.
user_ds: Set of user-defined data structure classes.
inbuilt_ds: Set of built-in data structures used.
comments: List of comments (text, lineno, type: inline/multiline).
uses_self: Boolean for self usage.


Purpose: Stores AST analysis for API prompts/LLM vectorization.
Usage: Populated in analyze via analyze_code, used for graph building.


self.file_module_map

Type: Dictionary ({file_path: module_name})
Description: Maps file paths (e.g., ./codebase/subdir/file1.py) to module names (e.g., subdir.file1).
Purpose: Links files to modules for graph nodes.
Usage: Populated in analyze, used for node creation.


self.module_file_map

Type: Dictionary ({module_name: file_path})
Description: Maps module names to file paths.
Purpose: Enables file lookup for graph edges.
Usage: Populated in analyze, used for cross-referencing modules/AST data.


self.directory_structure

Type: List of strings
Description: Stores directory tree lines (e.g., [├── file1.py, │   ├── subdir]).
Purpose: Captures directory structure for output/LLM training.
Usage: Populated in print_directory_structure, joined in analyze.



Class Methods
Methods perform analysis tasks, producing terminal output and LLM-compatible results.
init(self, base_path)

Purpose: Initializes the class with the codebase path.
Functionality:
Sets self.base_path.
Initializes self.graph as networkx.DiGraph.
Initializes self.parsed, self.file_module_map, self.module_file_map as empty dictionaries.
Initializes self.directory_structure as an empty list.


Output: None (sets instance variables).
Usage: Called at instantiation (e.g., analyzer = CodebaseAnalyzer("./codebase")).

is_probably_datastructure(self, class_node)

Purpose: Identifies if a class behaves like a data structure.
Functionality:
Checks for special methods (e.g., __getitem__, __len__).
Checks inheritance from INBUILT_DATASTRUCTURES (e.g., list).
Returns True if either condition is met, else False.


Output: Boolean.
Usage: Called in analyze_code for ast.ClassDef nodes.

print_directory_structure(self, root_path=None, indent="")

Purpose: Generates/prints directory tree, stores lines.
Functionality:
Uses self.base_path if root_path is None.
Lists entries with os.listdir, sorted.
Handles PermissionError with [Permission Denied].
Appends formatted lines (e.g., ├── file1.py) to self.directory_structure, prints to terminal.
Recursively processes subdirectories with indentation (e.g., │   ).


Output: None (prints, appends to self.directory_structure).
Usage: Called in analyze to display/store directory structure.

analyze_code(self, code_string, file_path)

Purpose: Parses a Python file for AST information.
Functionality:
Parses code_string with ast.parse, catching SyntaxError.
Initializes info dictionary with analysis keys.
Two AST walks:
First: Collects user-defined functions/methods.
Second: Extracts functions, classes, methods, imports, variables, control structures, function calls, data structures, self usage.


Extracts comments via tokenize (inline) and AST (multiline).
Sorts variables alphabetically.
Returns {"error": str} or info.


Output: Dictionary (info or {"error": str}).
Usage: Called in analyze to populate self.parsed.

analyze(self, sort_by="function_calls")

Purpose: Orchestrates directory, AST, and graph analysis.
Functionality:
Clears self.directory_structure, calls print_directory_structure.
Loads files via load_codebase, skips >5KB/non-Python files.
Maps files to modules in self.file_module_map/self.module_file_map.
Analyzes files with analyze_code, stores in self.parsed.
Sorts modules by sort_by (function_calls: most calls first; file: alphabetical).
Builds self.graph:
Adds module nodes.
Adds edges for imports/function calls.


Prints progress (e.g., Parsed: module1, Building edges for module1).
Prints graph summary (e.g., Graph built with 3 nodes).
Returns:
directory: Joined self.directory_structure.
ast: self.parsed.
graph: DOT string from to_dot.




Output: Dictionary ({directory: str, ast: dict, graph: str}).
Usage: Main analysis method, run in a thread (e.g., analyzer.analyze()).

to_dot(self)

Purpose: Converts dependency graph to DOT string.
Functionality:
Generates DOT string (e.g., digraph G { "module1"; "module1" -> "os"; }).
Includes sorted nodes/edges from self.graph.


Output: String (DOT format).
Usage: Called in analyze for results["graph"].

API Pipeline Integration

Usage:
Instantiate: analyzer = CodebaseAnalyzer(codebase_path).
Run: threading.Thread(target=lambda: analyzer.analyze()).
Use analyzer.parsed for API prompts, print results["directory"], results["ast"], results["graph"].


Compatibility:
results["ast"] matches ast_results for API prompts.
results["graph"] matches DependencyGraph.to_dot.
File filtering aligns with 5K-character batching.



LLM Training Compatibility

Tokenization:
directory: Text tree for raw tokenizers.
ast: JSON-serializable dict for CodeBERT.
graph: DOT string for GraphCodeBERT.


Vectorization:
directory: Hierarchical path embeddings.
ast: Embeddings for functions/imports (CodeBERT).
graph: Adjacency lists/features (GraphCodeBERT).



Usage Instructions

Save: Save as codebase_analyzer.py in my_project/.
Dependencies: Install networkx (pip install networkx), ensure utils.py.
Test:from codebase_analyzer import CodebaseAnalyzer
analyzer = CodebaseAnalyzer("./codebase")
results = analyzer.analyze()
print("\n=== Directory Structure ===\n", results["directory"])
print("\n=== AST Information ===\n")
for path, info in results["ast"].items():
    print(f"{path}: {info}")
print("\n=== Dependency Graph (DOT) ===\n", results["graph"])


Run: python test_analyzer.py in VSCode.
Output: Terminal shows directory, parsing progress, graph summary, and results dict.

Notes

Scalability: Filters >5KB/non-Python files.
Threading: Supports non-blocking execution.
PDF Conversion:
Use Pandoc: pandoc CodebaseAnalyzer_Documentation.md -o CodebaseAnalyzer_Documentation.pdf --pdf-engine=pdflatex.
Or VSCode Markdown PDF extension.


