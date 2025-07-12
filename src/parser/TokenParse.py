import networkx as nx
import sys, os
import tokenize
import ast
import io
import keyword
import matplotlib
from collections import defaultdict
matplotlib.use('TkAgg')  
from typing import Dict, List
import matplotlib.pyplot as plt
import builtins
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from src.downloader.Z_U_F import load_codebase


#code_files = load_codebase(r"C:\Users\Yatharth_Shivam\OneDrive\Documents\repos\seering\src")

#file_path = r"C:\Users\Yatharth_Shivam\OneDrive\Documents\repos\seering\src\downloader\Z_U_F.py"  # use the exact key as printed
#code_content = code_files.get(file_path)

#if code_content:
 #   code_lines = code_content.splitlines()
  #  for i, line in enumerate(code_lines, start=1):
  #      print(f"{i:03}: {line}")
#else:
 #   print("File not found in codebase.")


RESERVED_WORDS = set(keyword.kwlist)
INBUILT_FUNCTIONS = set(dir(builtins))
INBUILT_DATASTRUCTURES = {
    "list", "dict", "tuple", "set", "frozenset", "deque", "Counter",
    "DefaultDict", "OrderedDict", "array", "queue", "bytes", "bytearray", "memoryview"
}


def is_probably_datastructure(class_node: ast.ClassDef) -> bool:
    """
    Heuristically determine if a class behaves like a data structure.
    """
    special_methods = {"__getitem__", "__setitem__", "__delitem__", "__iter__", "__next__", "__len__", "__contains__"}
    method_names = {n.name for n in class_node.body if isinstance(n, ast.FunctionDef)}
    if special_methods & method_names:
        return True
    for base in class_node.bases:
        base_name = ast.unparse(base)
        if base_name in INBUILT_DATASTRUCTURES:
            return True
    return False


class CodeAnalyzer:
    def __init__(self, code_string: str):
        self.code = code_string
        self.tree = None
        try:
            self.tree = ast.parse(code_string)
        except SyntaxError as e:
            self.error = f"SyntaxError: {e}"
        else:
            self.error = None

        self.info = {
            "functions": [],           # stores func outside class
            "classes": [],             # stores class info + is_datastructure
            "methods": [],             # stores methods inside classes
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
            "comments": [],            # inline + multiline merged
            "uses_self": False
        }

        self.user_defined_funcs = set()
        self.user_defined_methods = set()

    def _analyze_functions(self):
        # Walk first to register all user-defined functions and methods
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef):
                parent = getattr(node, "parent", None)
                if isinstance(parent, ast.ClassDef):
                    self.user_defined_methods.add(node.name)
                else:
                    self.user_defined_funcs.add(node.name)

    def _process_function_node(self, node, is_method=False):
        func_info = {
            "name": node.name,
            "args": [arg.arg for arg in node.args.args],
            "returns": ast.unparse(node.returns) if node.returns else None,
            "docstring": ast.get_docstring(node),
            "decorators": [ast.unparse(dec) for dec in node.decorator_list],
            "lineno": node.lineno,
            "return_exprs": [],
        }

        for n in ast.walk(node):
            if isinstance(n, ast.Return) and n.value:
                func_info["return_exprs"].append(ast.unparse(n.value))
        if not is_method:
            self.info["functions"].append(func_info)
            self.info["user_func"].add(node.name)
        else:
            self.info["methods"].append(func_info)
            self.info["user_method"].add(node.name)

        if "self" in func_info["args"]:
            self.info["uses_self"] = True

    def _walk_tree(self):
        for node in ast.walk(self.tree):
            for child in ast.iter_child_nodes(node):
                child.parent = node

            if isinstance(node, ast.Name) and node.id == "self":
                self.info["uses_self"] = True

            if isinstance(node, ast.FunctionDef):
                parent = getattr(node, "parent", None)
                if isinstance(parent, ast.ClassDef):
                    self._process_function_node(node, is_method=True)
                else:
                    self._process_function_node(node)

            elif isinstance(node, ast.ClassDef):
                is_ds = is_probably_datastructure(node)
                self.info["classes"].append({
                    "name": node.name,
                    "bases": [ast.unparse(base) for base in node.bases],
                    "docstring": ast.get_docstring(node),
                    "lineno": node.lineno,
                    "is_datastructure": is_ds
                })
                if is_ds:
                    self.info["user_ds"].add(node.name)

            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    self.info["imports"].append({
                        "module": getattr(node, 'module', None),
                        "name": alias.name,
                        "asname": alias.asname
                    })

            elif isinstance(node, (ast.Assign, ast.AugAssign)):
                targets = [node.target] if hasattr(node, 'target') else node.targets
                for target in targets:
                    if isinstance(target, ast.Name):
                        self.info["variables"].add(target.id)
                    elif isinstance(target, ast.Tuple):
                        for elt in target.elts:
                            if isinstance(elt, ast.Name):
                                self.info["variables"].add(elt.id)

            elif isinstance(node, (ast.If, ast.For, ast.While)):
                self.info["control_structures"].append({
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

                    self.info["function_calls"].append(call_info)

                    if isinstance(node.func, ast.Name):
                        fname = node.func.id
                        if fname in self.user_defined_funcs:
                            self.info["user_function_calls"].append(call_info)
                            self.info["user_func"].add(fname)
                        elif fname in INBUILT_FUNCTIONS:
                            self.info["inbuilt_func"].add(fname)

                    elif isinstance(node.func, ast.Attribute):
                        attr_name = node.func.attr
                        if attr_name in self.user_defined_methods:
                            self.info["user_method"].add(attr_name)
                        elif attr_name in INBUILT_FUNCTIONS:
                            self.info["inbuilt_method"].add(attr_name)

                except Exception:
                    pass

            # Track use of built-in DS literals
            elif isinstance(node, ast.List):
                self.info["inbuilt_ds"].add("list")
            elif isinstance(node, ast.Dict):
                self.info["inbuilt_ds"].add("dict")
            elif isinstance(node, ast.Tuple):
                self.info["inbuilt_ds"].add("tuple")
            elif isinstance(node, ast.Set):
                self.info["inbuilt_ds"].add("set")

    def _extract_comments(self):
        try:
            tokens = tokenize.generate_tokens(io.StringIO(self.code).readline)
            for tok in tokens:
                if tok.type == tokenize.COMMENT:
                    self.info["comments"].append({
                        "text": tok.string.strip(),
                        "lineno": tok.start[0],
                        "type": "inline"
                    })
        except tokenize.TokenError:
            pass

        # Multi-line comments via ast.Expr (docstring-like blocks not attached to defs)
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                if isinstance(node.value.value, str):
                    parent = getattr(node, 'parent', None)
                    if not isinstance(parent, (ast.FunctionDef, ast.ClassDef, ast.Module)):
                        self.info["comments"].append({
                            "text": node.value.value.strip(),
                            "lineno": node.lineno,
                            "type": "multiline"
                        })

    def analyze(self):
        if self.error:
            return {"error": self.error}
        self._analyze_functions()
        self._walk_tree()
        self._extract_comments()
        self.info["variables"] = sorted(self.info["variables"])
        return self.info


code="""
import math , ast , numpy , pandas
def func(a,b):
    return 0
#hello
#hoi

class hello:
    def __init__():
        print("Hello")
        #hello
    def do(self):
        self.do()

"""





class DependencyGraph:
    def __init__(self, base_path):
        self.base_path = base_path
        self.graph = nx.DiGraph()
        self.parsed = {}
        self.file_module_map = {}
        self.module_file_map = {}

    def parse_files(self):
        code_dict = load_codebase(self.base_path)
        for file_path, code in code_dict.items():
            analyzer = CodeAnalyzer(code)
            result = analyzer.analyze()

            rel_path = os.path.relpath(file_path, self.base_path)
            module_name = rel_path.replace(os.sep, ".").replace(".py", "")
            self.file_module_map[file_path] = module_name
            self.module_file_map[module_name] = file_path
            self.parsed[module_name] = result

            print(f"Parsed: {module_name}")

    def build_dependency_graph(self, sort_by="function_calls"):
        if not self.parsed:
            self.parse_files()

        module_order = list(self.parsed.keys())
        if sort_by == "function_calls":
            module_order = sorted(
                self.parsed.items(),
                key=lambda x: len(x[1].get("function_calls", [])),
                reverse=True
            )
            module_order = [m[0] for m in module_order]
        elif sort_by == "file":
            module_order = sorted(module_order)

        for module in module_order:
            data = self.parsed[module]
            self.graph.add_node(module)
            print(f"\nBuilding edges for {module}")
            print(f"  - Imports: {len(data.get('imports', []))}")
            print(f"  - Function Calls: {len(data.get('function_calls', []))}")

            # Add import edges
            imports = sorted(data.get("imports", []), key=lambda x: x.get("module") or "")
            for imp in imports:
                imported = imp.get("module")
                if imported:
                    self.graph.add_edge(imported,module)  # reversed: imported → module

            # Add function call edges
            call_edges = []
            for call in data.get("user_function_calls", []):
                callee = call["name"].split(".")[0]
                for mod, mod_data in self.parsed.items():
                    user_funcs = {f["name"] for f in mod_data.get("functions", [])}
                    if callee in user_funcs and mod != module:
                        call_edges.append((mod, module, callee))  # reversed: mod → module

            # Add sorted call edges
            for src, dst, callee in sorted(call_edges, key=lambda x: x[2]):
                self.graph.add_edge(src, dst)

    def show_summary(self):
        print(f"\nGraph built with {self.graph.number_of_nodes()} nodes and {self.graph.number_of_edges()} edges.")
        print("Modules:")
        for node in sorted(self.graph.nodes):
            print(f" - {node}")
        print("Dependencies:")
        for u, v in sorted(self.graph.edges):
            print(f" - {u} -> {v}")

    def visualize(self):
        if not self.graph.nodes:
            print("No nodes to visualize.")
            return

        pos = nx.spring_layout(self.graph, seed=42, k=1.8)

        plt.figure(figsize=(14, 10))

    # Draw edges with offset at arrowhead and tail to avoid label box overlap
        nx.draw_networkx_edges(
            self.graph,
            pos,
            arrows=True,
            arrowstyle='->',
            arrowsize=18,
            width=1.5,
            connectionstyle='arc3,rad=0.1',
            edge_color='black',
            node_size=3000,  # approximate node size for offset
            min_source_margin=15,  # buffer at source
            min_target_margin=25   # buffer at target (arrow head)
        )

    # Draw node labels with padding and visible boxes
        nx.draw_networkx_labels(
            self.graph,
            pos,
            font_size=10,
            font_color='white',
            bbox=dict(boxstyle="round,pad=0.5", edgecolor="black", facecolor="blue")
        )

        plt.title("Dependency Graph", fontsize=14)
        plt.axis("off")
        plt.tight_layout()
        plt.show()







#ca=CodeAnalyzer()
#ast_info=ca.analyze()

#print(type(ast_info))
a=DependencyGraph(r"C:\Users\Yatharth_Shivam\OneDrive\Documents\repos\python-mini-projects-master")



a.build_dependency_graph()
a.show_summary()
a.visualize()
#print_directory_structure(r"C:\Users\Yatharth_Shivam\OneDrive\Documents\repos\python-mini-projects-master")

