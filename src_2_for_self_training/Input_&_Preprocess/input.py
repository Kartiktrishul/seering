
import os
import json
from tree_sitter_language_pack import get_language, get_parser
from github import Github
import networkx as nx
from tokenize import tokenize, COMMENT
import io
import keyword
import builtins 
import nbformat


class CodebaseAnalyzer:
    def __init__(self, input_path, github_token=None):
        self.input_path = input_path
        self.github_token = github_token
        self.graph = nx.DiGraph()
        self.parsed = {}
        self.file_module_map = {}
        self.module_file_map = {}
        self.directory_structure = []
        self.__language_map = {
            'py': 'python',
            'java': 'java',
            'js': 'javascript',
            'cpp': 'cpp',
            'c': 'c',
            'ts': 'typescript',
            'tsx': 'typescript',
            'go': 'go',
            'partial_movie_file_list': 'text'
        }
        self.__allowed_exts = [
            ".py", ".js", ".ts", ".java", ".cpp", ".c", ".r",
            ".json", ".yaml", ".yml", ".toml", ".xml",
            ".html", ".css", ".scss",
            ".md", ".rst", ".txt",
            ".ipynb", ".sh", ".bat", ".ini", ".cfg",
            ".partial_movie_file_list"
        ]
        self.__reserved_words = set(keyword.kwlist)
        self.__inbuilt_functions = set(dir(builtins))
        self.__inbuilt_datastructures = {
            "list", "dict", "tuple", "set", "frozenset", "deque", "Counter",
            "DefaultDict", "OrderedDict", "array", "queue", "bytes", "bytearray", "memoryview"
        }
        self.__inbuilt_methods = {'append', 'extend', 'pop', 'remove', 'sort', 'clear'}

    def __load_codebase(self):
        """Fetch code files from local path or GitHub URL."""
        code_files = {}
        total_attempted = 0
        total_loaded = 0

        def read_file_safely(full_path, is_github=False, content=None):
            if is_github:
                try:
                    return content.decode('utf-8') if isinstance(content, bytes) else content
                except UnicodeDecodeError:
                    try:
                        return content.decode('utf-8-sig')
                    except Exception as e:
                        print(f"Skipped (utf-8-sig failed): {full_path} — {e}")
                        return None
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    return f.read()
            except UnicodeDecodeError:
                try:
                    with open(full_path, "r", encoding="utf-8-sig") as f:
                        return f.read()
                except Exception as e:
                    print(f"Skipped (utf-8-sig failed): {full_path} — {e}")
            except Exception as e:
                print(f"Skipped (utf-8 failed): {full_path} — {e}")
            return None

        print(f"\nScanning codebase at: {self.input_path}")
        if self.input_path.startswith("https://github.com"):
            repo_name = self.input_path.split('github.com/')[1].rstrip('/')
            g = Github(self.github_token)
            repo = g.get_repo(repo_name)
            contents = repo.get_contents("")
            while contents:
                file_content = contents.pop(0)
                if file_content.type == "dir":
                    contents.extend(repo.get_contents(file_content.path))
                elif os.path.splitext(file_content.name)[1].lower() in self.__allowed_exts:
                    total_attempted += 1
                    code = read_file_safely(file_content.path, is_github=True, content=file_content.decoded_content)
                    if code is not None and code.strip():
                        code_files[file_content.path] = code
                        total_loaded += 1
                        print(f"Loaded file: {file_content.path}")
                    else:
                        print(f"Skipped empty or unreadable file: {file_content.path}")
        else:
            for root, dirs, files in os.walk(self.input_path):
                # Store directory structure
                self.directory_structure.append(f"Directory: {root}")
                for dir_name in sorted(dirs):
                    self.directory_structure.append(f"  Subdirectory: {os.path.join(root, dir_name)}")
                for file in files:
                    ext = os.path.splitext(file)[1].lower()
                    if ext in self.__allowed_exts:
                        full_path = os.path.join(root, file)
                        total_attempted += 1
                        code = read_file_safely(full_path)
                        if code is not None and code.strip():
                            code_files[full_path] = code
                            total_loaded += 1
                            print(f"Loaded file: {full_path}")
                            self.directory_structure.append(f"  File: {full_path}")
                        else:
                            print(f"Skipped empty or unreadable file: {full_path}")
                            self.directory_structure.append(f"  Skipped File: {full_path}")
        print(f"\nTotal files attempted: {total_attempted}")
        print(f"Total files successfully loaded: {total_loaded}")
        return code_files

    def __is_probably_datastructure(self, node, language, results):
        """Check if a class resembles a data structure."""
        special_methods = {"__getitem__", "__setitem__", "__delitem__", "__iter__", "__next__", "__len__", "__contains__"}
        name_node = node.child_by_field_name('name')
        class_name = name_node.text.decode('utf-8') if name_node else None
        method_names = {m['name'] for m in results['methods'] if m.get('class') == class_name}
        if special_methods & method_names:
            return True
        for child in node.children:
            if language == 'python' and child.type == 'argument_list':
                for arg in child.children:
                    if arg.type == 'identifier' and arg.text.decode('utf-8') in self.__inbuilt_datastructures:
                        return True
            elif language in ('java', 'javascript', 'typescript') and child.type == 'superclass':
                base_name = child.children[1].text.decode('utf-8') if len(child.children) > 1 else ''
                if base_name in self.__inbuilt_datastructures:
                    return True
        return False

    def __parse_file(self, file_path, content, language):
        """Parse a file using Tree-sitter or as text for non-code files or .ipynb."""
        print(f"Attempting to parse: {file_path} (language: {language})")
        if language == 'text' or os.path.splitext(file_path)[1].lower() == '.ipynb':
            if os.path.splitext(file_path)[1].lower() == '.ipynb':
                try:
                    nb = nbformat.from_string(content)
                    content = "\n".join(cell["source"] for cell in nb["cells"] if cell["cell_type"] == "code")
                    language = 'python'  # Parse .ipynb code cells as Python
                except Exception as e:
                    print(f"Failed to parse .ipynb {file_path}: {e}")
                    return {
                        'functions': [], 'classes': [], 'methods': [], 'imports': [],
                        'variables': set(), 'function_calls': [], 'user_function_calls': [],
                        'user_func': set(), 'inbuilt_func': set(), 'user_method': set(),
                        'inbuilt_method': set(), 'user_ds': set(), 'inbuilt_ds': set(),
                        'comments': [], 'uses_self': False, 'content': content,
                        'error': f"IPYNBError: {str(e)}"
                    }
            else:
                print(f"Non-code file detected, storing content only: {file_path}")
                return {
                    'functions': [], 'classes': [], 'methods': [], 'imports': [],
                    'variables': set(), 'function_calls': [], 'user_function_calls': [],
                    'user_func': set(), 'inbuilt_func': set(), 'user_method': set(),
                    'inbuilt_method': set(), 'user_ds': set(), 'inbuilt_ds': set(),
                    'comments': [], 'uses_self': False, 'content': content, 'error': None
                }
        try:
            LANG = get_language(language)
            parser = get_parser(language)
            tree = parser.parse(content.encode('utf-8'))
            results = {
                'functions': [], 'classes': [], 'methods': [], 'imports': [],
                'variables': set(), 'function_calls': [], 'user_function_calls': [],
                'user_func': set(), 'inbuilt_func': set(), 'user_method': set(),
                'inbuilt_method': set(), 'user_ds': set(), 'inbuilt_ds': set(),
                'comments': [], 'uses_self': False, 'content': content, 'error': None
            }
            user_defined_funcs = set()
            user_defined_methods = set()
            class_context = None

            def traverse(node):
                nonlocal class_context
                if language == 'python':
                    if node.type == 'function_definition':
                        name_node = node.child_by_field_name('name')
                        name = name_node.text.decode('utf-8') if name_node else 'anonymous'
                        if name in self.__reserved_words or name in self.__inbuilt_functions:
                            return
                        params = []
                        for param in node.child_by_field_name('parameters').children:
                            if param.type == 'identifier':
                                params.append(param.text.decode('utf-8'))
                        returns = None
                        return_exprs = []
                        for child in node.children:
                            if child.type == 'type' and child.text:
                                returns = child.text.decode('utf-8')
                            if child.type == 'block':
                                for stmt in child.children:
                                    if stmt.type == 'return_statement' and len(stmt.children) > 1:
                                        return_exprs.append(stmt.children[1].text.decode('utf-8'))
                        func_info = {
                            'name': name, 'args': params, 'returns': returns, 'decorators': [],
                            'lineno': node.start_point[0] + 1, 'return_exprs': return_exprs,
                            'class': class_context.text.decode('utf-8') if class_context and class_context.child_by_field_name('name') else None
                        }
                        if 'self' in params:
                            results['uses_self'] = True
                        if class_context:
                            results['methods'].append(func_info)
                            user_defined_methods.add(name)
                            results['user_method'].add(name)
                        else:
                            results['functions'].append(func_info)
                            user_defined_funcs.add(name)
                            results['user_func'].add(name)
                    elif node.type == 'class_definition':
                        class_context = node
                        name_node = node.child_by_field_name('name')
                        class_name = name_node.text.decode('utf-8') if name_node else 'anonymous'
                        bases = []
                        for child in node.children:
                            if child.type == 'argument_list':
                                for arg in child.children:
                                    if arg.type == 'identifier':
                                        bases.append(arg.text.decode('utf-8'))
                        is_ds = self.__is_probably_datastructure(node, language, results)
                        results['classes'].append({
                            'name': class_name, 'bases': bases, 'lineno': node.start_point[0] + 1,
                            'is_datastructure': is_ds
                        })
                        if is_ds:
                            results['user_ds'].add(class_name)
                        class_context = None
                    elif node.type in ('import_statement', 'import_from_statement'):
                        for child in node.children:
                            if child.type == 'import_list':
                                for import_node in child.children:
                                    module = None
                                    alias = None
                                    if import_node.type in ('identifier', 'dotted_name'):
                                        module = import_node.text.decode('utf-8')
                                    elif import_node.type == 'aliased_import':
                                        for subchild in import_node.children:
                                            if subchild.type in ('identifier', 'dotted_name'):
                                                module = subchild.text.decode('utf-8')
                                            elif subchild.type == 'alias':
                                                alias = subchild.children[-1].text.decode('utf-8') if subchild.children else None
                                    if module:
                                        results['imports'].append({
                                            'module': module,
                                            'name': module,
                                            'asname': alias,
                                            'lineno': node.start_point[0] + 1
                                        })
                    elif node.type == 'assignment':
                        name_node = node.child_by_field_name('left')
                        if name_node and name_node.type == 'identifier':
                            name = name_node.text.decode('utf-8')
                            if name not in self.__reserved_words:
                                results['variables'].add(name)
                        elif name_node and name_node.type == 'tuple':
                            for elt in name_node.children:
                                if elt.type == 'identifier':
                                    name = elt.text.decode('utf-8')
                                    if name not in self.__reserved_words:
                                        results['variables'].add(name)
                    elif node.type == 'call':
                        callee = node.child_by_field_name('function')
                        if callee:
                            fname = callee.text.decode('utf-8')
                            args = []
                            for arg in node.child_by_field_name('arguments').children:
                                if arg.type in ('string', 'integer', 'float', 'list', 'dictionary', 'set', 'tuple'):
                                    args.append(arg.text.decode('utf-8'))
                                else:
                                    args.append('<dynamic>')
                            call_info = {
                                'name': fname, 'lineno': node.start_point[0] + 1, 'args': args
                            }
                            results['function_calls'].append(call_info)
                            fname_base = fname.split('.')[0]
                            if fname_base in user_defined_funcs:
                                results['user_function_calls'].append(call_info)
                                results['user_func'].add(fname_base)
                            elif fname_base in self.__inbuilt_functions:
                                results['inbuilt_func'].add(fname_base)
                            elif '.' in fname and fname.split('.')[-1] in user_defined_methods:
                                results['user_method'].add(fname.split('.')[-1])
                            elif '.' in fname and fname.split('.')[-1] in self.__inbuilt_methods:
                                results['inbuilt_method'].add(fname.split('.')[-1])
                    elif node.type in ('list', 'dictionary', 'tuple', 'set'):
                        results['inbuilt_ds'].add(node.type)
                    elif node.type == 'identifier' and node.text.decode('utf-8') == 'self':
                        results['uses_self'] = True
                    elif node.type == 'comment':
                        results['comments'].append({
                            'text': node.text.decode('utf-8').strip(),
                            'lineno': node.start_point[0] + 1,
                            'type': 'inline'
                        })
                elif language in ('java', 'javascript', 'typescript'):
                    if node.type in ('method_declaration', 'function_declaration'):
                        name_node = node.child_by_field_name('name')
                        name = name_node.text.decode('utf-8') if name_node else 'anonymous'
                        params = []
                        for param in node.child_by_field_name('parameters').children:
                            if param.type == 'formal_parameter':
                                params.append(param.children[1].text.decode('utf-8') if len(param.children) > 1 else '')
                        returns = None
                        for child in node.children:
                            if child.type == 'type_identifier':
                                returns = child.text.decode('utf-8')
                        func_info = {
                            'name': name, 'args': params, 'returns': returns, 'decorators': [],
                            'lineno': node.start_point[0] + 1, 'return_exprs': [], 'class': None
                        }
                        if class_context:
                            results['methods'].append(func_info)
                            user_defined_methods.add(name)
                            results['user_method'].add(name)
                        else:
                            results['functions'].append(func_info)
                            user_defined_funcs.add(name)
                            results['user_func'].add(name)
                    elif node.type == 'class_declaration':
                        class_context = node
                        name_node = node.child_by_field_name('name')
                        class_name = name_node.text.decode('utf-8') if name_node else 'anonymous'
                        bases = []
                        for child in node.children:
                            if child.type == 'superclass':
                                bases.append(child.children[1].text.decode('utf-8') if len(child.children) > 1 else '')
                        is_ds = self.__is_probably_datastructure(node, language, results)
                        results['classes'].append({
                            'name': class_name, 'bases': bases, 'lineno': node.start_point[0] + 1,
                            'is_datastructure': is_ds
                        })
                        if is_ds:
                            results['user_ds'].add(class_name)
                        class_context = None
                    elif node.type == 'import_declaration':
                        module = node.children[1].text.decode('utf-8').split('.')[-1]
                        results['imports'].append({
                            'module': module, 'name': module, 'asname': None,
                            'lineno': node.start_point[0] + 1
                        })
                    elif node.type == 'variable_declarator':
                        name_node = node.child_by_field_name('name')
                        if name_node:
                            name = name_node.text.decode('utf-8')
                            results['variables'].add(name)
                    elif node.type == 'call_expression':
                        callee = node.child_by_field_name('function')
                        if callee:
                            fname = callee.text.decode('utf-8')
                            args = []
                            for arg in node.child_by_field_name('arguments').children:
                                if arg.type in ('string', 'number', 'array', 'object'):
                                    args.append(arg.text.decode('utf-8'))
                                else:
                                    args.append('<dynamic>')
                            call_info = {
                                'name': fname, 'lineno': node.start_point[0] + 1, 'args': args
                            }
                            results['function_calls'].append(call_info)
                            fname_base = fname.split('.')[0]
                            if fname_base in user_defined_funcs:
                                results['user_function_calls'].append(call_info)
                                results['user_func'].add(fname_base)
                            elif '.' in fname and fname.split('.')[-1] in user_defined_methods:
                                results['user_method'].add(fname.split('.')[-1])
                    elif node.type == 'comment':
                        results['comments'].append({
                            'text': node.text.decode('utf-8').strip(),
                            'lineno': node.start_point[0] + 1,
                            'type': 'inline'
                        })
                elif language in ('cpp', 'c'):
                    if node.type == 'function_definition':
                        name_node = node.child_by_field_name('declarator')
                        name = name_node.text.decode('utf-8')[:name_node.text.decode('utf-8').index('(')] if name_node and '(' in name_node.text.decode('utf-8') else 'anonymous'
                        params = []
                        for param in node.child_by_field_name('parameters').children:
                            if param.type == 'parameter_declaration':
                                params.append(param.children[-1].text.decode('utf-8') if param.children else '')
                        returns = None
                        for child in node.children:
                            if child.type == 'type_identifier':
                                returns = child.text.decode('utf-8')
                        func_info = {
                            'name': name, 'args': params, 'returns': returns, 'decorators': [],
                            'lineno': node.start_point[0] + 1, 'return_exprs': [], 'class': None
                        }
                        results['functions'].append(func_info)
                        user_defined_funcs.add(name)
                        results['user_func'].add(name)
                    elif node.type == 'class_specifier':
                        class_context = node
                        name_node = node.child_by_field_name('name')
                        class_name = name_node.text.decode('utf-8') if name_node else 'anonymous'
                        bases = []
                        for child in node.children:
                            if child.type == 'base_class_clause':
                                bases.append(child.children[1].text.decode('utf-8') if len(child.children) > 1 else '')
                        results['classes'].append({
                            'name': class_name, 'bases': bases, 'lineno': node.start_point[0] + 1,
                            'is_datastructure': False
                        })
                        class_context = None
                    elif node.type == 'declaration':
                        name_node = node.child_by_field_name('declarator')
                        if name_node:
                            name = name_node.text.decode('utf-8')
                            results['variables'].add(name)
                    elif node.type == 'call_expression':
                        callee = node.child_by_field_name('function')
                        if callee:
                            fname = callee.text.decode('utf-8')
                            args = []
                            for arg in node.child_by_field_name('arguments').children:
                                if arg.type in ('number', 'string'):
                                    args.append(arg.text.decode('utf-8'))
                                else:
                                    args.append('<dynamic>')
                            call_info = {
                                'name': fname, 'lineno': node.start_point[0] + 1, 'args': args
                            }
                            results['function_calls'].append(call_info)
                            if fname in user_defined_funcs:
                                results['user_function_calls'].append(call_info)
                                results['user_func'].add(fname)
                    elif node.type == 'comment':
                        results['comments'].append({
                            'text': node.text.decode('utf-8').strip(),
                            'lineno': node.start_point[0] + 1,
                            'type': 'inline'
                        })
                for child in node.children:
                    traverse(child)

            traverse(tree.root_node)
            if language == 'python':
                try:
                    tokens = tokenize(io.StringIO(content).readline)
                    for tok in tokens:
                        if tok.type == COMMENT:
                            results['comments'].append({
                                'text': tok.string.strip(),
                                'lineno': tok.start[0],
                                'type': 'inline'
                            })
                except Exception as e:
                    print(f"Comment parsing failed for {file_path}: {e}")
            print(f"Successfully parsed: {file_path} (functions: {len(results['functions'])}, classes: {len(results['classes'])}, methods: {len(results['methods'])})")
            return results
        except Exception as e:
            print(f"Parsing failed for {file_path}: {e}")
            return {
                'functions': [], 'classes': [], 'methods': [], 'imports': [],
                'variables': set(), 'function_calls': [], 'user_function_calls': [],
                'user_func': set(), 'inbuilt_func': set(), 'user_method': set(),
                'inbuilt_method': set(), 'user_ds': set(), 'inbuilt_ds': set(),
                'comments': [], 'uses_self': False, 'content': content,
                'error': f"ParseError: {str(e)}"
            }

    def __select_files(self, mode, num_files, criteria):
        """Select files based on mode and criteria."""
        if not self.parsed:
            print("Warning: No files parsed.")
            return []
        if mode not in [0, 1]:
            print(f"Error: Invalid mode {mode}. Use 0 (top N) or 1 (all).")
            return []
        files = list(self.parsed.keys())
        if mode == 1 or not files:
            return sorted(files)
        if criteria == "function_calls":
            files = sorted(files, key=lambda f: len(self.parsed[f].get("function_calls", [])), reverse=True)
        elif criteria == "size":
            files = sorted(files, key=lambda f: len(self.parsed[f].get('content', '')), reverse=True)
        elif criteria == "name":
            files = sorted(files)
        else:
            print(f"Error: Invalid criteria {criteria}. Use 'function_calls', 'size', or 'name'.")
            return []
        return files[:min(num_files, len(files))]

    def __get_ast_info(self, mode=1, num_files=None, criteria="name"):
        """Generate AST information for selected files."""
        if not self.parsed:
            print("Warning: No files parsed.")
            return {}
        num_files = len(self.parsed) if num_files is None else num_files
        selected_files = self.__select_files(mode, num_files, criteria)
        if not selected_files:
            print("Warning: No files selected for AST printing.")
            return {}
        result = {}
        for file_path in selected_files:
            ast_info = self.parsed.get(file_path, {"error": "No AST data available"})
            code = ast_info.get('content', '')
            result[file_path] = {'actual_code': code, 'ast_info': {k: v for k, v in ast_info.items() if k != 'content'}}
        return result

    def __build_dependency_graph(self):
        """Build dependency graph for cross-file analysis."""
        for file_path in self.parsed:
            if self.input_path.startswith("https://github.com"):
                module_name = file_path.replace("/", ".").rsplit(".", 1)[0]
            else:
                module_name = os.path.relpath(file_path, self.input_path).replace(os.sep, ".").rsplit(".", 1)[0]
            self.file_module_map[file_path] = module_name
            self.module_file_map[module_name] = file_path
            self.graph.add_node(module_name)
            data = self.parsed[file_path]
            print(f"\nBuilding edges for {module_name}")
            print(f"  - Imports: {len(data.get('imports', []))}")
            print(f"  - Function Calls: {len(data.get('function_calls', []))}")
            imports = sorted(data.get("imports", []), key=lambda x: x.get("module") or "")
            for imp in imports:
                imported = imp.get("module")
                if imported and imported in self.module_file_map:
                    self.graph.add_edge(imported, module_name)
            call_edges = []
            for call in data.get("function_calls", []):
                fname = call["name"]
                fname_base = fname.split('.')[0]
                for mod, mod_file in self.module_file_map.items():
                    if mod_file == file_path:
                        continue
                    mod_data = self.parsed.get(mod_file, {})
                    user_funcs = {f["name"] for f in mod_data.get("functions", [])}
                    user_methods = {m["name"] for m in mod_data.get("methods", [])}
                    if fname_base in user_funcs or fname_base in user_methods:
                        call_edges.append((mod, module_name, fname))
            for src, dst, fname in sorted(call_edges, key=lambda x: x[2]):
                self.graph.add_edge(src, dst)

    def __to_dot(self):
        """Generate DOT representation of the dependency graph."""
        dot = ['digraph G {']
        for node in sorted(self.graph.nodes):
            dot.append(f'"{node}"')
        for u, v in sorted(self.graph.edges):
            dot.append(f'"{u}" -> "{v}";')
        dot.append('}')
        return '\n'.join(dot)

    def analyze(self, sort_by="name"):
        """Public method to analyze the codebase."""
        code_dict = self.__load_codebase()
        for file_path, code in code_dict.items():
            extension = os.path.splitext(file_path)[1].lower()
            language = self.__language_map.get(extension[1:] if extension else 'text', 'text')
            try:
                parsed_data = self.__parse_file(file_path, code, language)
                self.parsed[file_path] = parsed_data
            except MemoryError:
                print(f"Skipped due to memory constraints: {file_path}")
                self.parsed[file_path] = {
                    'functions': [], 'classes': [], 'methods': [], 'imports': [],
                    'variables': set(), 'function_calls': [], 'user_function_calls': [],
                    'user_func': set(), 'inbuilt_func': set(), 'user_method': set(),
                    'inbuilt_method': set(), 'user_ds': set(), 'inbuilt_ds': set(),
                    'comments': [], 'uses_self': False, 'content': code,
                    'error': "MemoryError: File too large to parse"
                }
        self.__build_dependency_graph()
        ast_result = self.__get_ast_info(mode=1, num_files=len(self.parsed), criteria=sort_by)
        return {
            "directory": "\n".join(self.directory_structure),
            "ast": self.parsed,
            "graph": self.__to_dot(),
            "ast_info": ast_result
        }

# Initialize and run CodebaseAnalyzer
analyzer = CodebaseAnalyzer(
    input_path=r"C:\Users\Yatharth_Shivam\OneDrive\Documents\repos\seering\src"
)
result = analyzer.analyze(sort_by="name")

# Print results to terminal
print("\n=== Codebase Analysis Results ===")
print("\nDirectory Structure:")
print(result["directory"])

print("\nParsed Files:")
for file_path, info in result["ast"].items():
    print(f"\nFile: {file_path}")
    print("Metadata:")
    for key, value in info.items():
        if key != "content":
            print(f"  {key}: {value}")
    print("Content (truncated):")
    content = info["content"]
    print(f"    {content[:100] + '...' if len(content) > 100 else content}")

print("\nDependency Graph (DOT format):")
print(result["graph"])

print("\nHierarchy Dependencies:")
for file_path, info in result["ast_info"].items():
    print(f"  File: {file_path}")
    print(f"    Actual Code (truncated): {info['actual_code'][:100] + '...' if len(info['actual_code']) > 100 else info['actual_code']}")
    print("    AST Info:")
    for key, value in info["ast_info"].items():
        print(f"      {key}: {value}")

