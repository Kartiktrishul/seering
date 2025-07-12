import os

def load_codebase(path):
    allowed_exts = [
        ".py", ".js", ".ts", ".java", ".cpp", ".c", ".r",
        ".json", ".yaml", ".yml", ".toml", ".xml",
        ".html", ".css", ".scss",
        ".md", ".rst", ".txt",
        ".ipynb", ".sh", ".bat", ".ini", ".cfg"
    ]

    def read_file_safely(full_path):
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

    code_files = {}
    total_attempted = 0
    total_loaded = 0

    print(f"\nScanning codebase at: {path}")
    for root, _, files in os.walk(path):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in allowed_exts:
                full_path = os.path.join(root, file)
                total_attempted += 1
                code = read_file_safely(full_path)
                if code is not None:
                    if code.strip():  # Skip purely empty files
                        code_files[full_path] = code
                        total_loaded += 1
                        print(f"Loaded file: {full_path}")
                    else:
                        print(f"Skipped empty file: {full_path}")
                else:
                    print(f"Failed to load file: {full_path}")

    print(f"\nTotal files attempted: {total_attempted}")
    print(f"Total files successfully loaded: {total_loaded}")
    return code_files



