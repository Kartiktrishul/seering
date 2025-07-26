import streamlit as st
import requests
import os
import zipfile
import tempfile
import re
from dotenv import load_dotenv
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from src.downloader.Z_U_F import load_codebase


# Load environment variables
load_dotenv()
LLM_API_URL = "https://openrouter.ai/api/v1/chat/completions"
LLM_API_KEY = "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" 

def generate_summary(code_files):
    if not LLM_API_KEY:
        return "Error: OPENROUTER_API_KEY is not set", ["Error: OPENROUTER_API_KEY is not set"]

    st.write("Debug: Processing codebase...")
    errors = []
    
    if not code_files:
        return "Error: No valid code files provided", ["Error: No valid code files provided"]

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
            st.write(f"Skipping large file: {path} ({len(content)} bytes)")
            continue
        ext = os.path.splitext(path)[1][1:].lower()
        file_content = f"\nFile: {path}\n```{ext}\n{content}\n```\n"
        file_contents.append(file_content)

    if not file_contents:
        return "Error: No valid files after filtering", ["Error: No valid files after filtering"]

    prompt = base_prompt + "".join(file_contents)
    prompt_length_chars = len(prompt)
    estimated_tokens = prompt_length_chars // 4
    st.write(f"Debug: Prompt size: {prompt_length_chars} chars (~{estimated_tokens} tokens)")

    if estimated_tokens > max_token_limit:
        return f"Error: Prompt exceeds token limit ({estimated_tokens} > {max_token_limit} tokens)", [f"Error: Prompt exceeds token limit ({estimated_tokens} > {max_token_limit} tokens)"]

    st.write("Debug: Sending summary API request...")
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost",
        "X-Title": "Codebase Summarizer"
    }
    payload = {
        "model": "deepseek/deepseek-r1:free",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1500,
        "temperature": 0.6
    }

    try:
        response = requests.post(LLM_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        summary = response.json().get('choices', [{}])[0].get('message', {}).get('content', 'Error: No summary returned')
        required_sections = ["High-Level Overview", "Class-Level Breakdown", "Function-Level Breakdown", "Interdependencies and Flow"]
        missing_sections = [s for s in required_sections if s not in summary]
        if missing_sections:
            st.warning(f"Missing summary sections: {', '.join(missing_sections)}")
            errors.append(f"Missing summary sections: {', '.join(missing_sections)}")
        return summary, errors
    except requests.RequestException as e:
        st.write(f"API Error Details for summary: {response.text if 'response' in locals() else 'No response'}")
        errors.append(f"Error calling OpenRouter API for summary: {e}")
        return f"Error calling OpenRouter API for summary: {e}", errors

def generate_video_script(summary, errors):
    if not summary or summary.startswith("Error:"):
        return "Error: No valid summary to generate video script", ["Error: No valid summary to generate video script"]

    st.write("Debug: Generating video script...")
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
        "max_tokens": 1500,
        "temperature": 0.8
    }

    try:
        response = requests.post(LLM_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        script = response.json().get('choices', [{}])[0].get('message', {}).get('content', 'Error: No script returned')
        word_count = len(script.split())
        st.write(f"Debug: Video script word count: {word_count}")
        visual_cue_count = script.count('[')
        if visual_cue_count < 4:
            st.warning(f"Video script has only {visual_cue_count} visual cues (minimum 4 recommended)")
            errors.append(f"Video script has only {visual_cue_count} visual cues")
        return script, errors
    except requests.RequestException as e:
        st.write(f"API Error Details for video script: {response.text if 'response' in locals() else 'No response'}")
        errors.append(f"Error calling OpenRouter API for video script: {e}")
        return f"Error calling OpenRouter API for video script: {e}", errors

def extract_visual_cues(script):
    cues = re.findall(r'\[(.*?)\]', script)
    cue_descriptions = []
    for cue in cues:
        if "DiGraph" in cue or "add_edge" in cue:
            description = "Graph with nodes and directed arrows (Manim: Graph, Arrow)"
        elif "data flow" in cue or "add_node" in cue:
            description = "Animated data flow between nodes (Manim: Graph, AnimationGroup)"
        elif "class hierarchy" in cue:
            description = "Class inheritance diagram (Manim: Text, Line)"
        else:
            description = "General animation (e.g., flowchart or code snippet highlight)"
        cue_descriptions.append({"Visual Cue": cue, "Animation Description": description})
    return cue_descriptions

# Streamlit website configuration
st.set_page_config(page_title="Codebase Analyzer", page_icon="📊", layout="wide")
st.title("Codebase Analyzer")
st.markdown("Upload a zip file containing Python (.py) files to generate a technical summary and video script for software engineers.")

# File uploader for zip file
uploaded_file = st.file_uploader("Upload a zip file containing .py files", type="zip")

if uploaded_file:
    with st.spinner("Processing uploaded codebase..."):
        # Create temporary directory to extract zip
        with tempfile.TemporaryDirectory() as tmp_dir:
            zip_path = os.path.join(tmp_dir, "codebase.zip")
            with open(zip_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            # Extract zip file
            try:
                with zipfile.ZipFile(zip_path, "r") as zip_ref:
                    zip_ref.extractall(tmp_dir)
            except zipfile.BadZipFile:
                st.error("Error: Invalid zip file")
                st.stop()

            # Load codebase from extracted files
            code_files = load_codebase(tmp_dir)
            if not code_files:
                st.error("No valid .py files found in the zip")
                st.stop()

            # Generate summary
            summary, summary_errors = generate_summary(code_files)
            if summary.startswith("Error:"):
                st.error(summary)
                if summary_errors:
                    st.subheader("Errors")
                    for err in summary_errors:
                        st.error(err)
                st.stop()

            # Generate video script
            script, script_errors = generate_video_script(summary, summary_errors)
            errors = summary_errors + script_errors

            # Display results in tabs
            tab1, tab2 = st.tabs(["Codebase Summary", "Video Script"])
            with tab1:
                st.subheader("Codebase Summary")
                st.text_area("Summary", summary, height=400)
            with tab2:
                st.subheader("Video Script")
                st.text_area("Script", script, height=400)
                st.subheader("Manim Visual Cues")
                st.markdown("The following visual cues from the script can be animated using Manim (offline rendering required).")
                cue_df = extract_visual_cues(script)
                if cue_df:
                    st.table(cue_df)
                else:
                    st.write("No visual cues found in the script.")

            # Display errors
            if errors:
                st.subheader("Errors")
                for err in errors:
                    st.error(err)

else:
    st.info("Please upload a zip file to begin analysis.")