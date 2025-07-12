from Z_U_F import load_codebase
code_files = load_codebase(r"C:\Users\Yatharth_Shivam\OneDrive\Documents\repos\seering\src")

file_path = r"C:\Users\Yatharth_Shivam\OneDrive\Documents\repos\seering\src\dowloader\Zip_Unzip_Files.py"  # use the exact key as printed
code_content = code_files.get(file_path)

if code_content:
    code_lines = code_content.splitlines()
    for i, line in enumerate(code_lines, start=1):
        print(f"{i:03}: {line}")
else:
    print("File not found in codebase.")