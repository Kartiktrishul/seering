import os
import requests
from typing import Dict
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from src.downloader.Z_U_F import load_codebase
from src.parser.CodeBase_CodeLine import CodebaseAnalyzer
import threading
import streamlit as st

LLM_API_URL = "https://openrouter.ai/api/v1/chat/completions"
LLM_API_KEY = "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"  # Replace with your actual OpenRouter API key
LLM_API_KEY2= "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"


def generate_summary(code_files):
    if not LLM_API_KEY:
        print("Error: OPENROUTER_API_KEY is not set", flush=True)
        return "Error: OPENROUTER_API_KEY is not set", []

    print("Debug: Processing codebase...", flush=True)
    errors = []
    
    if not code_files:
        print("Error: No valid code files provided", flush=True)
        return "Error: No valid code files provided", errors

    max_file_size = 10000
    max_token_limit = 10000
    base_prompt = (
        "You are a technical code analysis assistant helping to create animated engineering explainer videos. "
        "You will be given a portion of a codebase (possibly spanning multiple files). Your task is to produce a clear, technically informative summary suitable for an audience of software engineers. "
        "Avoid line-by-line explanations; focus on structural, modular, and conceptual clarity. Prioritize components with the most dependencies or impact. Provide detailed descriptions for High-Level Overview, Class-Level Breakdown, Function-Level Breakdown, and Interdependencies and Flow, including specific examples or snippets. Keep Engineering Commentary brief (under 50 words) with one key observation or improvement.\n\n"
        "Your output should be organized into the following sections:\n\n"
        "1. *High-Level Overview*:\n"
        "   - Describe the primary goal or purpose of this codebase/module.\n"
        "   - Explain what problem it solves or functionality it provides.\n"
        "   - Include a snippet showing the main entry point or key class.\n\n"
        "2. *Class-Level Breakdown*:\n"
        "   - List and explain key classes (focus on those with significant dependencies).\n"
        "   - Detail inheritance or composition relationships.\n"
        "   - Include a snippet of a key class definition.\n\n"
        "3. *Function-Level Breakdown*:\n"
        "   - Summarize important functions or methods (prioritize those with critical logic).\n"
        "   - Describe their input/output, key logic, and notable patterns.\n"
        "   - Include a snippet of a key function.\n\n"
        "4. *Interdependencies and Flow*:\n"
        "   - Describe how components (functions, classes, files) interact.\n"
        "   - Highlight critical data or control flow.\n"
        "   - Include a snippet showing a key interaction.\n\n"
        "5. *Engineering Commentary*:\n"
        "   - Provide one brief technical observation or improvement (under 50 words).\n"
        "   - Include a snippet to illustrate the observation if relevant.\n\n"
        "Here is the codebase you should analyze:\n\n"
    )

    file_contents = []
    for path, content in code_files.items():
        if len(content) > max_file_size:
            print(f"Skipping large file: {path} ({len(content)} bytes)", flush=True)
            continue
        ext = os.path.splitext(path)[1][1:].lower()
        file_content = f"\nFile: {path}\n```{ext}\n{content}\n```\n"
        file_contents.append(file_content)

    if not file_contents:
        print("Error: No valid files after filtering", flush=True)
        return "Error: No valid files after filtering", errors

    prompt = base_prompt + "".join(file_contents)
    prompt_length_chars = len(prompt)
    estimated_tokens = prompt_length_chars // 4
    print(f"Debug: Prompt size: {prompt_length_chars} chars (~{estimated_tokens} tokens)", flush=True)

    if estimated_tokens > max_token_limit:
        print(f"Error: Prompt exceeds token limit ({estimated_tokens} > {max_token_limit} tokens)", flush=True)
        return f"Error: Prompt exceeds token limit ({estimated_tokens} > {max_token_limit} tokens)", errors

    print("Debug: Sending summary API request...", flush=True)
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost",
        "X-Title": "Codebase Summarizer"
    }
    payload = {
        "model": "deepseek/deepseek-r1:free",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 7000,
        "temperature": 0.7
    }

    try:
        response = requests.post(LLM_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        summary = response.json().get('choices', [{}])[0].get('message', {}).get('content', 'Error: No summary returned')
        required_sections = ["High-Level Overview", "Class-Level Breakdown", "Function-Level Breakdown", "Interdependencies and Flow", "Engineering Commentary"]
        missing_sections = [s for s in required_sections if s not in summary]
        if missing_sections:
            print(f"Warning: Missing summary sections: {', '.join(missing_sections)}", flush=True)
            errors.append(f"Missing summary sections: {', '.join(missing_sections)}")
        return summary, errors
    except requests.RequestException as e:
        print(f"API Error Details for summary: {response.text if 'response' in locals() else 'No response'}", flush=True)
        errors.append(f"Error calling OpenRouter API for summary: {e}")
        return f"Error calling OpenRouter API for summary: {e}", errors

def generate_video_script(summary, errors):
    if not summary or summary.startswith("Error:"):
        print("Error: No valid summary to generate video script", flush=True)
        return "Error: No valid summary to generate video script", errors

    print("Debug: Generating video script...", flush=True)
    script_prompt = (
        "You are a scriptwriter for animated engineering explainer videos. Given a technical codebase summary, create a video script for software engineers. The script should:\n"
        "- Be engaging, clear, and concise, using analogies to simplify complex concepts (e.g., compare graphs to road networks).\n"
        "- Highlight the codebase's purpose, 2–3 key components, and one improvement suggestion.\n"
        "- Use a conversational, enthusiastic tone for narration.\n"
        "- Include 4–6 specific visual cues (e.g., '[Visualize DiGraph.add_edge]', '[Show data flow for add_node]') tied to the codebase for Manim or animation tools.\n"
        "- Structure: Opening (15s), Core Explanation (60–90s), Closing (15s).\n"
        "- Produce a detailed script without a strict word limit, but aim for clarity and animation feasibility.\n\n"
        "Here is the summary to convert:\n"
        f"{summary}\n\n"
        "Output the script in plain text."
    )

    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost",
        "X-Title": "Codebase Video Script"
    }
    payload = {
        "model": "deepseek/deepseek-r1:free",
        "messages": [{"role": "user", "content": script_prompt}],
        "max_tokens": 7000,
        "temperature": 0.8
    }

    try:
        response = requests.post(LLM_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        script = response.json().get('choices', [{}])[0].get('message', {}).get('content', 'Error: No script returned')
        word_count = len(script.split())
        print(f"Debug: Video script word count: {word_count}", flush=True)
        visual_cue_count = script.count('[')
        if visual_cue_count < 4:
            print(f"Warning: Video script has only {visual_cue_count} visual cues (minimum 4 recommended)", flush=True)
            errors.append(f"Video script has only {visual_cue_count} visual cues")
        return script, errors
    except requests.RequestException as e:
        print(f"API Error Details for video script: {response.text if 'response' in locals() else 'No response'}", flush=True)
        errors.append(f"Error calling OpenRouter API for video script: {e}")
        return f"Error calling OpenRouter API for video script: {e}", errors

def main():
    codebase_path = input("Enter the path to the codebase: ").strip()
    errors = []
    
    if not os.path.isdir(codebase_path):
        print(f"Error: Invalid directory path: {codebase_path}", flush=True)
        return

    print("Loading codebase...", flush=True)
    code_files = load_codebase(codebase_path)
    if not code_files:
        print("No valid code files found", flush=True)
        return

    print("Generating summary...", flush=True)
    summary, summary_errors = generate_summary(code_files)
    errors.extend(summary_errors)
    
    print("\n=== Codebase Summary ===\n", flush=True)
    print(summary, flush=True)

    print("\nGenerating video script...", flush=True)
    script, script_errors = generate_video_script(summary, errors)
    errors.extend(script_errors)
    
    print("\n=== Video Script ===\n", flush=True)
    print(script, flush=True)
    print("\n=======================\n", flush=True)

    if errors:
        print("Debug: Errors encountered:", flush=True)
        for err in errors:
            print(err, flush=True)

if __name__ == "__main__":
    main()