import os
import ast
import networkx as nx
import tokenize
import io
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from src.downloader.Z_U_F import load_codebase
import builtins
import keyword  


RESERVED_WORDS  = set(keyword.kwlist)
INBUILT_FUNCTIONS = set(dir(builtins))
INBUILT_DATASTRUCTURES = {
    "list", "dict", "tuple", "set", "frozenset", "deque", "Counter",
    "DefaultDict", "OrderedDict", "array", "queue", "bytes", "bytearray", "memoryview"
}

class CodebaseAnalyzer:
    def __init__(self, base_path):
        self.base_path = base_path
        self.graph = nx.DiGraph()
        self.parsed = {}
        self.file_module_map = {}
        self.module_file_map = {}
        self.directory_structure = []

    def is_probably_datastructure(self, class_node):
        special_methods = {"__getitem__", "__setitem__", "__delitem__", "__iter__", "__next__", "__len__", "__contains__"}
        method_names = {n.name for n in class_node.body if isinstance(n, ast.FunctionDef)}
        if special_methods & method_names:
            return True
        for base in class_node.bases:
            base_name = ast.unparse(base)
            if base_name in INBUILT_DATASTRUCTURES:
                return True
        return False

    def print_directory_structure(self, root_path=None, indent=""):
        if root_path is None:
            root_path = self.base_path
        print(f"Debug: Attempting to access directory: {root_path}", flush=True)
        if not os.path.exists(root_path):
            error_msg = f"[Error: Path does not exist: {root_path}]"
            self.directory_structure.append(indent + error_msg)
            print(error_msg, flush=True)
            return
        if not os.path.isdir(root_path):
            error_msg = f"[Error: Not a directory: {root_path}]"
            self.directory_structure.append(indent + error_msg)
            print(error_msg, flush=True)
            return
        try:
            entries = sorted(os.listdir(root_path))
            if not entries:
                self.directory_structure.append(indent + "[Empty Directory]")
                print(indent + "[Empty Directory]", flush=True)
                return
        except PermissionError:
            error_msg = f"[Permission Denied: {root_path}]"
            self.directory_structure.append(indent + error_msg)
            print(error_msg, flush=True)
            return
        except OSError as e:
            error_msg = f"[OS Error: {str(e)} for {root_path}]"
            self.directory_structure.append(indent + error_msg)
            print(error_msg, flush=True)
            return
        for index, entry in enumerate(entries):
            try:
                # Handle non-ASCII characters safely
                entry = entry.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
            except Exception as e:
                print(f"Debug: Encoding error for entry '{entry}': {str(e)}", flush=True)
                entry = "[Invalid Filename]"
            full_path = os.path.join(root_path, entry)
            is_last = index == len(entries) - 1
            branch = "└── " if is_last else "├── "
            line = indent + branch + entry
            self.directory_structure.append(line)
            print(line, flush=True)
            if os.path.isdir(full_path):
                new_indent = indent + ("    " if is_last else "│   ")
                self.print_directory_structure(full_path, new_indent)

    def analyze_code(self, code_string, file_path):
        tree = None
        error = None
        try:
            tree = ast.parse(code_string)
        except SyntaxError as e:
            error = f"SyntaxError: {e}"
        info = {
            "functions": [],
            "classes": [],
            "methods": [],
            "imports": [],
            "variables": set(),
            "control_structures": [],
            "function_calls": [],
            "user_function_calls": [],
            "user_func": set(),
            "inbuilt_func": set(),
            "user_method": set(),
            "inbuilt_method": set(),
            "user_ds": set(),
            "inbuilt_ds": set(),
            "comments": [],
            "uses_self": False
        }
        user_defined_funcs = set()
        user_defined_methods = set()
        if not error:
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    parent = getattr(node, "parent", None)
                    if isinstance(parent, ast.ClassDef):
                        user_defined_methods.add(node.name)
                    else:
                        user_defined_funcs.add(node.name)
            for node in ast.walk(tree):
                for child in ast.iter_child_nodes(node):
                    child.parent = node
                if isinstance(node, ast.Name) and node.id == "self":
                    info["uses_self"] = True
                if isinstance(node, ast.FunctionDef):
                    parent = getattr(node, "parent", None)
                    func_info = {
                        "name": node.name,
                        "args": [arg.arg for arg in node.args.args],
                        "returns": ast.unparse(node.returns) if node.returns else None,
                        "decorators": [ast.unparse(dec) for dec in node.decorator_list],
                        "lineno": node.lineno,
                        "return_exprs": []
                    }
                    for n in ast.walk(node):
                        if isinstance(n, ast.Return) and n.value:
                            func_info["return_exprs"].append(ast.unparse(n.value))
                    if isinstance(parent, ast.ClassDef):
                        info["methods"].append(func_info)
                        info["user_method"].add(node.name)
                    else:
                        info["functions"].append(func_info)
                        info["user_func"].add(node.name)
                    if "self" in func_info["args"]:
                        info["uses_self"] = True
                elif isinstance(node, ast.ClassDef):
                    is_ds = self.is_probably_datastructure(node)
                    info["classes"].append({
                        "name": node.name,
                        "bases": [ast.unparse(base) for base in node.bases],
                        "lineno": node.lineno,
                        "is_datastructure": is_ds
                    })
                    if is_ds:
                        info["user_ds"].add(node.name)
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    for alias in node.names:
                        info["imports"].append({
                            "module": getattr(node, 'module', None),
                            "name": alias.name,
                            "asname": alias.asname
                        })
                elif isinstance(node, (ast.Assign, ast.AugAssign)):
                    targets = [node.target] if hasattr(node, 'target') else node.targets
                    for target in targets:
                        if isinstance(target, ast.Name):
                            info["variables"].add(target.id)
                        elif isinstance(target, ast.Tuple):
                            for elt in target.elts:
                                if isinstance(elt, ast.Name):
                                    info["variables"].add(elt.id)
                elif isinstance(node, (ast.If, ast.For, ast.While)):
                    info["control_structures"].append({
                        "type": type(node).__name__,
                        "lineno": node.lineno,
                        "condition": ast.unparse(node.test) if hasattr(node, "test") else None
                    })
                elif isinstance(node, ast.Call):
                    try:
                        func_name = ast.unparse(node.func)
                        call_info = {
                            "name": func_name,
                            "lineno": node.lineno,
                            "args": []
                        }
                        for arg in node.args:
                            if isinstance(arg, (ast.Constant, ast.List, ast.Tuple, ast.Dict, ast.Set)):
                                call_info["args"].append(ast.unparse(arg))
                            else:
                                call_info["args"].append("<dynamic>")
                        info["function_calls"].append(call_info)
                        if isinstance(node.func, ast.Name):
                            fname = node.func.id
                            if fname in user_defined_funcs:
                                info["user_function_calls"].append(call_info)
                                info["user_func"].add(fname)
                            elif fname in INBUILT_FUNCTIONS:
                                info["inbuilt_func"].add(fname)
                        elif isinstance(node.func, ast.Attribute):
                            attr_name = node.func.attr
                            if attr_name in user_defined_methods:
                                info["user_method"].add(attr_name)
                            elif attr_name in INBUILT_FUNCTIONS:
                                info["inbuilt_method"].add(attr_name)
                    except Exception:
                        pass
                elif isinstance(node, ast.List):
                    info["inbuilt_ds"].add("list")
                elif isinstance(node, ast.Dict):
                    info["inbuilt_ds"].add("dict")
                elif isinstance(node, ast.Tuple):
                    info["inbuilt_ds"].add("tuple")
                elif isinstance(node, ast.Set):
                    info["inbuilt_ds"].add("set")
            try:
                tokens = tokenize.generate_tokens(io.StringIO(code_string).readline)
                for tok in tokens:
                    if tok.type == tokenize.COMMENT:
                        info["comments"].append({
                            "text": tok.string.strip(),
                            "lineno": tok.start[0],
                            "type": "inline"
                        })
            except tokenize.TokenError:
                pass
            for node in ast.walk(tree):
                if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                    if isinstance(node.value.value, str):
                        parent = getattr(node, 'parent', None)
                        if not isinstance(parent, (ast.FunctionDef, ast.ClassDef, ast.Module)):
                            info["comments"].append({
                                "text": node.value.value.strip(),
                                "lineno": node.lineno,
                                "type": "multiline"
                            })
            info["variables"] = sorted(info["variables"])
        return {"error": error} if error else info

    def select_files(self, mode, num_files, criteria):
        if not self.parsed:
            print("Warning: No files parsed. Run analyze() first.", flush=True)
            return []
        if mode not in [0, 1]:
            print(f"Error: Invalid mode {mode}. Use 0 or 1.", flush=True)
            return []
        if mode == 1:
            return sorted(self.parsed.keys())
        files = list(self.parsed.keys())
        if criteria == "function_calls":
            files = sorted(
                files,
                key=lambda f: len(self.parsed[f].get("function_calls", [])),
                reverse=True
            )
        elif criteria == "size":
            code_dict = load_codebase(self.base_path)
            files = sorted(
                files,
                key=lambda f: len(code_dict.get(f, "")),
                reverse=True
            )
        elif criteria == "name":
            files = sorted(files)
        else:
            print(f"Error: Invalid criteria {criteria}. Use 'function_calls', 'size', or 'name'.", flush=True)
            return []
        return files[:min(num_files, len(files))]

    def get_ast_info(self, mode=0, num_files=5, criteria="function_calls"):
        if not self.parsed:
            print("Warning: No files parsed. Run analyze() first.", flush=True)
            return {}
        code_dict = load_codebase(self.base_path)
        selected_files = self.select_files(mode, num_files, criteria)
        result = {}
        print("\n=== AST Information ===", flush=True)
        for file_path in selected_files:
            ast_info = self.parsed.get(file_path, {"error": "No AST data available"})
            code = code_dict.get(file_path, "")
            truncated_code = (code[:100] + "...") if len(code) > 100 else code
            print(f"\nFile: {file_path}", flush=True)
            print(f"Code (truncated): {truncated_code}", flush=True)
            print(f"AST: {ast_info}", flush=True)
            result[file_path] = {
                "actual_code": code,
                "ast_info": ast_info
            }
        return result

    def analyze(self, sort_by="function_calls"):
        self.directory_structure = []
        print("\n=== Directory Structure ===\n", flush=True)
        self.print_directory_structure()
        print("\n", flush=True)
        code_dict = load_codebase(self.base_path)
        for file_path, code in code_dict.items():
            if len(code) > 5000:
                print(f"Skipping large file: {file_path} ({len(code)} bytes)", flush=True)
                continue
            if not file_path.endswith('.py'):
                continue
            rel_path = os.path.relpath(file_path, self.base_path)
            module_name = rel_path.replace(os.sep, ".").replace(".py", "")
            self.file_module_map[file_path] = module_name
            self.module_file_map[module_name] = file_path
            self.parsed[file_path] = self.analyze_code(code, file_path)
            print(f"Parsed: {module_name}", flush=True)
        module_order = list(self.module_file_map.keys())
        if sort_by == "function_calls":
            module_order = sorted(
                [(m, self.parsed[self.module_file_map[m]]) for m in module_order],
                key=lambda x: len(x[1].get("function_calls", [])),
                reverse=True
            )
            module_order = [m[0] for m in module_order]
        elif sort_by == "file":
            module_order = sorted(module_order)
        for module in module_order:
            file_path = self.module_file_map[module]
            data = self.parsed[file_path]
            self.graph.add_node(module)
            print(f"\nBuilding edges for {module}", flush=True)
            print(f"  - Imports: {len(data.get('imports', []))}", flush=True)
            print(f"  - Function Calls: {len(data.get('function_calls', []))}", flush=True)
            imports = sorted(data.get("imports", []), key=lambda x: x.get("module") or "")
            for imp in imports:
                imported = imp.get("module")
                if imported:
                    self.graph.add_edge(imported, module)
            call_edges = []
            for call in data.get("user_function_calls", []):
                callee = call["name"].split(".")[0]
                for mod, mod_file in self.module_file_map.items():
                    mod_data = self.parsed.get(mod_file, {})
                    user_funcs = {f["name"] for f in mod_data.get("functions", [])}
                    if callee in user_funcs and mod != module:
                        call_edges.append((mod, module, callee))
            for src, dst, callee in sorted(call_edges, key=lambda x: x[2]):
                self.graph.add_edge(src, dst)
        print(f"\nGraph built with {self.graph.number_of_nodes()} nodes and {self.graph.number_of_edges()} edges.", flush=True)
        print("Modules:", flush=True)
        for node in sorted(self.graph.nodes):
            print(f" - {node}", flush=True)
        print("Dependencies:", flush=True)
        for u, v in sorted(self.graph.edges):
            print(f" - {u} -> {v}", flush=True)
        return {
            "directory": "\n".join(self.directory_structure),
            "ast": self.parsed,
            "graph": self.to_dot()
        }

    def to_dot(self):
        dot = ['digraph G {']
        for node in sorted(self.graph.nodes):
            dot.append(f'"{node}"')
        for u, v in sorted(self.graph.edges):
            dot.append(f'"{u}" -> "{v}";')
        dot.append('}')
        return '\n'.join(dot)    


#analyzer=CodebaseAnalyzer(r"C:\Users\Yatharth_Shivam\OneDrive\Documents\repos\seering\src")
#analyzer.analyze(sort_by="file")
#analyzer.get_ast_info(mode=0, num_files=5, criteria="name")

