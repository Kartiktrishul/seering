LLM_API_KEY = "AIzaSyD_z23EGoNu3tjGYjhj9r_TQkUveVcqw1o" 
import os
import requests
import json
import time
from github import Github, GithubException


# The model identifier for Google's API
LLM_MODEL = "gemini-1.5-pro-latest" # Or "gemini-1.5-flash-latest" for faster, cheaper calls

# Files and directories to ignore during codebase processing.
IGNORE_LIST = {
    "dirs": [".git", ".vscode", "node_modules", "__pycache__", "dist", "build", "venv"],
    "files": [".gitignore", "package-lock.json", "yarn.lock", ".DS_Store"],
    "extensions": [".log", ".tmp", ".bak", ".swo", ".swp", ".env", ".lock"]
}

# --- Helper Functions ---

def is_relevant_file(file_path):
    """Checks if a file should be included based on the IGNORE_LIST."""
    path_parts = file_path.split(os.sep)
    
    # Check if any directory in the path is in the ignore list
    if any(part in IGNORE_LIST["dirs"] for part in path_parts):
        return False
        
    # Check if the file itself is in the ignore list
    if os.path.basename(file_path) in IGNORE_LIST["files"]:
        return False
        
    # Check if the file extension is in the ignore list
    if os.path.splitext(file_path)[1] in IGNORE_LIST["extensions"]:
        return False
        
    return True

# --- Codebase Loading ---

def load_codebase(input_path, github_token=None):
    """Loads codebase from local path or GitHub URL."""
    print(f"Loading codebase from: {input_path}")
    if input_path.startswith("https://github.com"):
        return load_codebase_from_github(input_path, github_token)
    elif os.path.isdir(input_path):
        return load_codebase_from_local(input_path)
    else:
        print("Error: Invalid input. Please provide a valid GitHub URL or a local directory path.")
        return None

def load_codebase_from_github(repo_url, github_token=None):
    """Loads relevant code files from a GitHub repository."""
    code_files = {}
    try:
        repo_name = repo_url.split('github.com/')[1].rstrip('/')
        g = Github(github_token)
        repo = g.get_repo(repo_name)
        
        print(f"Cloning repository '{repo_name}'...")
        contents = repo.get_contents("")
        
        queue = list(contents)
        while queue:
            file_content = queue.pop(0)
            path = file_content.path
            
            if not is_relevant_file(path):
                continue

            if file_content.type == "dir":
                try:
                    queue.extend(repo.get_contents(path))
                except GithubException as e:
                    print(f"Could not access directory {path}: {e}")
            else:
                try:
                    # Only decode text files
                    decoded_content = file_content.decoded_content.decode('utf-8')
                    code_files[path] = decoded_content
                except (UnicodeDecodeError, AttributeError):
                    print(f"Skipping non-text or binary file: {path}")

    except GithubException as e:
        print(f"Error loading from GitHub: {e}. Check URL and token permissions.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while loading from GitHub: {e}")
        return None
        
    return code_files

def load_codebase_from_local(local_path):
    """Loads relevant code files from a local directory."""
    code_files = {}
    print(f"Scanning local directory: {local_path}")
    for root, _, files in os.walk(local_path):
        # Create a relative path from the initial local_path to keep the structure clean
        relative_root = os.path.relpath(root, local_path)
        
        # Skip ignored directories
        if any(part in IGNORE_LIST["dirs"] for part in relative_root.split(os.sep)):
            continue

        for file in files:
            # Use relative path for keys
            relative_file_path = os.path.join(relative_root, file)
            if relative_file_path.startswith('.' + os.sep):
                relative_file_path = relative_file_path[2:]

            if not is_relevant_file(relative_file_path):
                continue
            
            full_file_path = os.path.join(root, file)
            try:
                with open(full_file_path, "r", encoding="utf-8", errors="ignore") as f:
                    code_files[relative_file_path] = f.read()
            except Exception as e:
                print(f"Error reading {full_file_path}: {e}")
                
    return code_files

# --- LLM Interaction (Updated for Google AI Studio with Retry Logic) ---

def call_llm(prompt):
    """Generic function to call the Google Gemini API with retry logic for rate limiting."""
    if not LLM_API_KEY or LLM_API_KEY == "YOUR_GOOGLE_AI_API_KEY":
        print("Error: LLM_API_KEY is not set. Please add your Google AI Studio key to the script.")
        return None

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{LLM_MODEL}:generateContent?key={LLM_API_KEY}"
    headers = {"Content-Type": "application/json"}
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    
    max_retries = 5
    base_delay = 10  # seconds

    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, data=json.dumps(data), timeout=300)
            response.raise_for_status()
            result = response.json()
            return result['candidates'][0]['content']['parts'][0]['text']

        except requests.exceptions.RequestException as e:
            # Handle 429 Rate Limit Error specifically
            if e.response is not None and e.response.status_code == 429:
                delay = base_delay * (2 ** attempt) # Exponential backoff
                print(f"Rate limit exceeded. Retrying in {delay} seconds... (Attempt {attempt + 1}/{max_retries})")
                time.sleep(delay)
                continue
            else:
                print(f"Error calling LLM API: {e}")
                if e.response is not None:
                    print(f"Response Body: {e.response.text}")
                return None # Exit on other errors

        except (KeyError, IndexError) as e:
            print(f"Error parsing LLM response: {e}")
            if 'response' in locals():
                 print("Full response:", response.text)
            return None
    
    print("Failed to call LLM API after multiple retries due to rate limiting.")
    return None

# --- New "Map-Reduce" Functions ---

def summarize_individual_file(file_path, file_content):
    """ "Map" step: Summarizes a single file. """
    print(f"Summarizing file: {file_path}...")
    prompt = f"""
    You are a code analysis assistant. Your task is to summarize a single code file.
    Focus on the file's primary purpose, key functions or classes, and its main inputs and outputs.
    Keep the summary concise and high-level.

    File Path: {file_path}
    File Content:
    ---
    {file_content}
    ---

    Provide a brief summary of this file:
    """
    return call_llm(prompt)

def generate_final_summary(directory_tree, file_summaries):
    """ "Reduce" step: Creates a holistic summary from individual file summaries. """
    print("Generating final holistic summary from individual file analyses...")
    
    summaries_text = "\n".join(f"--- Summary for file: {path} ---\n{summary}" for path, summary in file_summaries)

    prompt = f"""
    You are a technical code analysis assistant helping to create animated engineering explainer videos.
    You have been provided with a directory tree and a set of summaries for each individual file in a codebase.
    Your task is to synthesize this information into a single, cohesive, and technically informative summary suitable for an audience of software engineers.
    Focus on the overall architecture, how the different files interact, and the main data/control flow.

    Your output should be organized into the following sections:

    1. *High-Level Overview*:
       - Describe the primary goal or purpose of this entire codebase.
       - Explain what problem it solves or functionality it provides, based on how the files work together.

    2. *Class-Level Breakdown*:
       - Based on the file summaries, identify and explain the key classes across the project.
       - Detail how classes from different files might inherit from or compose each other.

    3. *Function-Level Breakdown*:
       - Summarize the most important functions or methods that drive the core logic of the application.

    4. *Interdependencies and Flow*:
       - This is the most important section. Describe how the different files (and the components within them) interact.
       - Trace a typical data or control flow through the system (e.g., "A request comes into `api.py`, which calls a function in `database.py`...").

    5. *Engineering Commentary*:
       - Provide one brief technical observation or improvement about the overall architecture (under 50 words).

    Here is the information to analyze:

    **[1. Directory Structure]**
    {directory_tree}

    **[2. Individual File Summaries]**
    {summaries_text}
    """
    return call_llm(prompt)

def generate_video_script(summary):
    """Generates a video script from the final codebase summary using an LLM."""
    print("Generating video script...")
    prompt = f"""
    You are a scriptwriter for animated engineering explainer videos. Given a technical codebase summary, create a video script for software engineers. The script should:
    - Be engaging, clear, and concise, using analogies to simplify complex concepts (e.g., compare graphs to road networks).
    - Highlight the codebase's purpose, 2–3 key components, and one improvement suggestion.
    - Use a conversational, enthusiastic tone for narration.
    - Include 4–6 specific visual cues (e.g., '[Visualize DiGraph.add_edge]', '[Show data flow for add_node]') tied to the codebase for Manim or animation tools.
    - Structure: Opening (15s), Core Explanation (60–90s), Closing (15s).
    - Produce a detailed script without a strict word limit, but aim for clarity and animation feasibility.

    Here is the summary to convert:
    {summary}

    Output the script in plain text.
    """
    return call_llm(prompt)

# --- Main Execution (Updated with Map-Reduce Logic) ---

def main():
    """Main function to run the script."""
    print("--- Codebase to Video Script Generator (Chunking Mode) ---")
    
    input_path = input("Enter the path to the codebase (GitHub URL or local path): ").strip()
    github_token = None
    if input_path.startswith("https://github.com"):
        github_token = input("Enter your GitHub token (optional, for private repos): ").strip()

    code_files = load_codebase(input_path, github_token)

    if not code_files:
        print("Could not load codebase. Exiting.")
        return

    print(f"Successfully loaded {len(code_files)} relevant files.")
    
    # --- "Map" Step ---
    file_summaries = []
    total_files = len(code_files)
    for i, (path, content) in enumerate(code_files.items()):
        print(f"\n--- Processing file {i+1}/{total_files} ---")
        file_summary = summarize_individual_file(path, content)
        if file_summary:
            file_summaries.append((path, file_summary))
        else:
            print(f"Skipping file {path} due to summarization error.")
        
        # Add a delay to respect rate limits between each file summary call
        if i < total_files - 1:
            time.sleep(2) # A short delay between individual file calls

    if not file_summaries:
        print("No file summaries could be generated. Exiting.")
        return

    # --- "Reduce" Step ---
    print("\n--- All files summarized. Creating final analysis. ---")
    directory_tree = "\n".join(f"- {path}" for path in sorted(code_files.keys()))
    final_summary = generate_final_summary(directory_tree, file_summaries)

    if not final_summary:
        print("Failed to generate final summary. Exiting.")
        return
        
    print("\n--- Final Codebase Summary ---")
    print(final_summary)

    script = generate_video_script(final_summary)
    if not script:
        print("Failed to generate video script. Exiting.")
        return

    print("\n--- Generated Video Script ---")
    print(script)
    
    # Save outputs to files
    with open("codebase_summary.md", "w", encoding="utf-8") as f:
        f.write(final_summary)
    with open("video_script.txt", "w", encoding="utf-8") as f:
        f.write(script)
        
    print("\nSummary saved to 'codebase_summary.md'")
    print("Video script saved to 'video_script.txt'")
    print("\nVideo creation step is next. You can now use this script with a model like Veo.")

if __name__ == "__main__":
    main()
