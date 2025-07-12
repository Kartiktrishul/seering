import os
import requests
from typing import Dict
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from src.downloader.Z_U_F import load_codebase
from src.parser.CodeBase_CodeLine import CodebaseAnalyzer
import threading


LLM_API_URL = "https://openrouter.ai/api/v1/chat/completions"
LLM_API_KEY = "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"  # Replace with your actual OpenRouter API key


def generate_summary(code_files, codebase_path):
    if not LLM_API_KEY:
        print("Error: OPENROUTER_API_KEY is not set", flush=True)
        return "Error: OPENROUTER_API_KEY is not set"

    print(f"Debug: Initializing CodebaseAnalyzer with path: {codebase_path}", flush=True)
    
    if not os.path.exists(codebase_path):
        print(f"Error: Codebase path does not exist: {codebase_path}", flush=True)
        print("Suggestion: Use a local path (e.g., C:/repos/seering/src/codebase) to avoid OneDrive issues", flush=True)
        return f"Error: Codebase path does not exist: {codebase_path}"
    if not os.path.isdir(codebase_path):
        print(f"Error: Codebase path is not a directory: {codebase_path}", flush=True)
        return f"Error: Codebase path is not a directory: {codebase_path}"

    analyzer = CodebaseAnalyzer(codebase_path)
    
    results = {}
    thread_output = []
    def run_analyzer():
        nonlocal results, thread_output
        import sys
        original_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')
        try:
            results = analyzer.analyze()
            thread_output.extend(analyzer.directory_structure)
            thread_output.append(f"Debug: Analysis completed for {len(analyzer.parsed)} files")
        except Exception as e:
            thread_output.append(f"Error in analysis thread: {str(e)}")
        finally:
            sys.stdout = original_stdout

    print("Debug: Starting analysis thread...", flush=True)
    analysis_thread = threading.Thread(target=run_analyzer)
    analysis_thread.start()
    analysis_thread.join()
    
    print("\n=== Directory Structure ===", flush=True)
    if not thread_output:
        print("No directory structure output captured. Check path or permissions.", flush=True)
    for line in thread_output:
        print(line, flush=True)
    print("Debug: Directory structure printed.", flush=True)

    if not results:
        print("Error: Analysis failed to produce results.", flush=True)
        return "Error: Analysis failed to produce results."

    ast_info = analyzer.get_ast_info(mode=0, num_files=5, criteria="function_calls")
    print(f"Debug: Retrieved AST info for {len(ast_info)} files", flush=True)
    
    max_batch_size = 10000
    max_file_size = 10000
    batch_prompts = []
    current_batch = []
    current_length = 0
    file_count = 0
    base_prompt = (
        "You are a code analysis assistant. Below is a portion of a codebase with raw code and AST information. "
        "Provide a concise summary in markdown format, including:\n"
        "- Overview: Purpose and main functionality.\n"
        "- Structure: File organization and components.\n"
        "- Key Features: Main functionalities, including insights from AST (e.g., functions, classes, imports).\n"
        "- Technologies: Languages, frameworks, libraries.\n"
        "- Potential Improvements: Optimization suggestions.\n\n"
        "Codebase files and AST information:\n"
    )

    for path, content in code_files.items():
        if len(content) > max_file_size:
            print(f"Skipping large file: {path} ({len(content)} bytes)", flush=True)
            continue
        ext = os.path.splitext(path)[1][1:].lower()
        file_content = f"\n### {path}\n```{ext}\n{content}\n```\n"
        if path in ast_info:
            ast_data = ast_info[path]["ast_info"]
            ast_summary = (
                f"#### AST Information for {path}\n"
                f"- Functions: {', '.join(f['name'] for f in ast_data.get('functions', [])) or 'None'}\n"
                f"- Classes: {', '.join(c['name'] for c in ast_data.get('classes', [])) or 'None'}\n"
                f"- Imports: {', '.join(i['name'] for i in ast_data.get('imports', [])) or 'None'}\n"
                f"- Function Calls: {len(ast_data.get('function_calls', []))} calls\n"
            )
            file_content += ast_summary
        file_length = len(file_content)
        if current_length + file_length > max_batch_size and current_batch:
            prompt = base_prompt + "".join(current_batch)
            batch_prompts.append((prompt, file_count))
            current_batch = []
            current_length = 0
            file_count = 0
        current_batch.append(file_content)
        current_length += file_length
        file_count += 1

    if current_batch:
        prompt = base_prompt + "".join(current_batch)
        batch_prompts.append((prompt, file_count))

    summaries = []
    for i, (prompt, count) in enumerate(batch_prompts):
        print(f"Processing batch {i+1}/{len(batch_prompts)} ({count} files, {len(prompt)} chars)...", flush=True)
        headers = {
            "Authorization": f"Bearer {LLM_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost",
            "X-Title": "Codebase Summarizer"
        }
        payload = {
            "model": "deepseek/deepseek-chat:free",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 250,
            "temperature": 0.7
        }

        try:
            response = requests.post(LLM_API_URL, headers=headers, json=payload)
            response.raise_for_status()
            summary = response.json().get('choices', [{}])[0].get('message', {}).get('content', 'Error: No summary returned')
            summaries.append(summary)
        except requests.RequestException as e:
            print(f"API Error Details for batch {i+1}: {response.text if 'response' in locals() else 'No response'}", flush=True)
            return f"Error calling OpenRouter API in batch {i+1}: {e}"

    combine_prompt = (
        "Combine the following batch summaries into a single cohesive summary in markdown format, "
        "covering the entire codebase:\n"
        + "\n\n".join(f"Batch {i+1}:\n{summary}" for i, summary in enumerate(summaries))
    )
    print(f"Combining {len(summaries)} batch summaries...", flush=True)
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost",
        "X-Title": "Codebase Summarizer"
    }
    payload = {
        "model": "deepseek/deepseek-chat:free",
        "messages": [{"role": "user", "content": combine_prompt}],
        "max_tokens": 500,
        "temperature": 0.7
    }

    try:
        response = requests.post(LLM_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        final_summary = response.json().get('choices', [{}])[0].get('message', {}).get('content', 'Error: No final summary returned')
        return final_summary
    except requests.RequestException as e:
        print(f"API Error Details for final summary: {response.text if 'response' in locals() else 'No response'}", flush=True)
        return f"Error combining summaries: {e}\n\nPartial Summaries:\n" + "\n\n".join(summaries)

def main():
    codebase_path = input("Enter the path to the codebase: ").strip()
    if not os.path.isdir(codebase_path):
        print("Error: Invalid directory path", flush=True)
        return

    print("Loading codebase...", flush=True)
    code_files = load_codebase(codebase_path)
    if not code_files:
        print("No valid code files found", flush=True)
        return

    print("Generating summary...", flush=True)
    summary = generate_summary(code_files, codebase_path)
    
    print("\n=== Codebase Summary ===\n", flush=True)
    print(summary, flush=True)
    print("\n=======================\n", flush=True)

if __name__ == "__main__":
    main()