# ollama_model.py
import ollama
import json


def control_linux(linuxcommand):
    """Simple function to acknowledge the command before it's used."""
    print(f"🤖 AI proposed command: '{linuxcommand}'")
    return linuxcommand


# `conversation_messages` should be the LIST of {"role": ..., "content": ...} dicts
# `current_path_for_context` is the string representing the current working directory in the container
def linux_command(conversation_messages: list, current_path_for_context: str) -> str | None:
    system_prompt_content = (
        f"You are a command-line assistant. Your job is to provide exactly one simple Linux command based on the user's request.\n"
        f"IMPORTANT: Your command will be executed as if you are already in the directory: '{current_path_for_context}'.\n"
        f"Therefore, for commands like 'touch newfile.txt', 'mkdir newdir', or 'ls' targeting items within '{current_path_for_context}', "
        f"use relative paths (e.g., 'touch newfile.txt', 'ls my_subdir'). Do NOT prepend '{current_path_for_context}/' to these relative paths.\n"
        f"For 'cd' commands, you can use relative paths (e.g., 'cd ..', 'cd newfolder') or absolute paths (e.g., 'cd /etc').\n"
        "\n"
        "ALLOWED COMPLEXITY: You must provide exactly one command. However, this single command can include I/O redirection ('>', '>>') or a single simple pipe ('|') if it achieves a single conceptual goal.\n"
        "Examples of single conceptual actions:\n"
        "  - Creating/overwriting a file with content: {{ \"linuxcommand\": \"echo 'hello world' > file.txt\" }}\n"
        "  - Appending to a file: {{ \"linuxcommand\": \"echo 'more text' >> file.txt\" }}\n"
        "  - Listing files and filtering for 'txt': {{ \"linuxcommand\": \"ls -l | grep txt\" }}\n"
        "\n"
        "Respond with a valid JSON object with exactly one field:\n"
        "- 'linuxcommand': a single Linux shell command. This command should be relative to '{current_path_for_context}' for most operations, unless an absolute path is explicitly needed (e.g., for 'cd /some/absolute/path').\n"
        "\n"
        "More Examples (assuming current path is /home/user):\n"
        "User: create a directory called 'docs'\n"
        "AI: {{ \"linuxcommand\": \"mkdir docs\" }}\n"
        "User: go into docs\n"
        "AI: {{ \"linuxcommand\": \"cd docs\" }}  (current path becomes /home/user/docs)\n"
        "User: create a file report.txt\n"
        "AI: {{ \"linuxcommand\": \"touch report.txt\" }}\n"
        "User: add 'initial report' to report.txt\n"
        "AI: {{ \"linuxcommand\": \"echo 'initial report' > report.txt\" }}\n"
        "User: list files here\n"
        "AI: {{ \"linuxcommand\": \"ls -l\" }}\n"
        "User: go to /etc\n"
        "AI: {{ \"linuxcommand\": \"cd /etc\" }} (current path becomes /etc)\n"
        "\n"
        "❌ Do NOT output explanations.\n"
        "❌ Do NOT include multiple commands separated by ';' or '&&' (unless it's a single conceptual command with pipe/redirection as shown above).\n"
        "✅ Output only the JSON object."
    )

    # Construct the full message list for the API call
    messages_for_ollama_api = [
        {"role": "system", "content": system_prompt_content}
    ]
    messages_for_ollama_api.extend(conversation_messages)  # Add the actual conversation history

    try:
        response = ollama.chat(
            model='llama3.2',  # Ensure this model is pulled and available
            messages=messages_for_ollama_api,
            format="json"  # Ask Ollama to ensure the output is JSON
        )

        raw_content = response['message']['content'].strip()

        # When format="json", raw_content should be the JSON string itself.
        try:
            data = json.loads(raw_content)
            if isinstance(data, dict) and "linuxcommand" in data:
                return control_linux(data["linuxcommand"])
            else:
                # Fallback if AI didn't adhere to format="json" perfectly
                print(f"⚠️ AI response was not the expected JSON structure despite format='json'. Raw: {raw_content}")
                # Try to extract JSON if embedded (less robust)
                json_start = raw_content.find('{')
                json_end = raw_content.rfind('}') + 1
                if json_start != -1 and json_end > json_start:
                    json_str = raw_content[json_start:json_end]
                    try:
                        data_fallback = json.loads(json_str)
                        if isinstance(data_fallback, dict) and "linuxcommand" in data_fallback:
                            return control_linux(data_fallback["linuxcommand"])
                    except json.JSONDecodeError:
                        pass  # Fall through to main error
                print(
                    f"❌ 'linuxcommand' key not found or invalid structure in AI response. Parsed data: {data if 'data' in locals() else 'N/A'}")
                return None
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON received from AI even with format='json': {e}")
            print(f"Raw AI output: {raw_content}")
            return None
    except Exception as e:
        print(f"❌ Error during Ollama API call: {e}")
        return None