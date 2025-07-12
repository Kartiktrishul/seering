import os

def load_codebase(path):
    allowed_exts = [
        ".py", ".js", ".ts", ".java", ".cpp", ".c", ".r",
        ".json", ".yaml", ".yml", ".toml", ".xml",
        ".html", ".css", ".scss",
        ".md", ".rst", ".txt",
        ".ipynb", ".sh", ".bat", ".ini", ".cfg"
    ]

    code_files = {}
    print(f"\nScanning codebase at: {path}")
    for root, _, files in os.walk(path):
        for file in files:
            ext = os.path.splitext(file)[1].lower() 
            if ext in allowed_exts:
                full_path = os.path.join(root, file)
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        code = f.read()
                        code_files[full_path] = code
                        print(f"Loaded file: {full_path}")
                except Exception as e:
                    print(f"Skipped file due to error: {full_path} — {e}")
    print(f"\n Total files loaded: {len(code_files)}")
    return code_files


