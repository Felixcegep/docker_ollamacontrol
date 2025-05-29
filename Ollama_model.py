# Ollama_model.py
import ollama
import json


def linux_command(conversation_messages: list, current_path: str) -> str | None:
    """
    Generates a single Linux command from a step description.
    'conversation_messages' should be a list like: [{"role": "user", "content": "step description"}]
    """
    system_prompt = (
        f"You are an AI assistant that generates a single, specific Linux command. "
        f"You are operating inside a minimal Ubuntu Docker container with a root shell. "
        f"The current working directory is '{current_path}'.\n\n"
        f"**CRITICAL INSTRUCTIONS (MUST FOLLOW):**\n"
        f"1.  **ROOT Shell Context:** You are running as root. Therefore, `sudo` is NOT required for any command, including `apt` package management. Using `sudo` will cause errors.\n"
        f"2.  **JSON Output ONLY:** You MUST output ONLY a single JSON object and NOTHING ELSE. No introductory text, no explanations, no apologies, just the JSON. "
        f"    This JSON object MUST contain exactly one key: `\"linuxcommand\"`. The value for this key MUST be a string containing the complete Linux command.\n"
        f"    CORRECT Output Example: `{{\"linuxcommand\": \"ls -la\"}}`\n"
        f"    INCORRECT Output Example 1: `Here is the command: {{\"linuxcommand\": \"ls -la\"}}` (Contains extra text before JSON)\n"
        f"    INCORRECT Output Example 2: `{{\"command\": \"ls -la\"}}` (Wrong key name)\n"
        f"    INCORRECT Output Example 3: `{{\"linuxcommand\": \"echo \\\"Hello\\\"\"}}` (Ensure proper JSON string escaping if command contains quotes)\n"
        f"3.  **Command Specificity:** The command must directly and completely achieve the task described in the user's message (which represents one step of a plan from another AI).\n"
        f"4.  **Paths:** Use relative paths for files/directories in '{current_path}' when appropriate. Use absolute paths if the step specifies them or for system directories (e.g., /tmp, /etc).\n\n"
        f"**Examples based on user's step description (which is a plan step):**\n"
        f"- User step: 'Create an empty directory named my_data in the current location.'\n"
        f"  Your JSON Output: `{{\"linuxcommand\": \"mkdir my_data\"}}`\n"
        f"- User step: 'List all files and folders, including hidden ones, with detailed information in the current directory.'\n"
        f"  Your JSON Output: `{{\"linuxcommand\": \"ls -la\"}}`\n"
        f"- User step: 'Change current directory to /opt/app.'\n"
        f"  Your JSON Output: `{{\"linuxcommand\": \"cd /opt/app\"}}`\n"
        f"- User step: 'Write the exact text \\'Final report content.\\' into a new file named final_report.txt in the current directory.'\n"  # Escaped for Python string
        f"  Your JSON Output: `{{\"linuxcommand\": \"echo 'Final report content.' > final_report.txt\"}}`\n"
        f"- User step: 'Update package lists and install the nano text editor using apt.'\n"
        f"  Your JSON Output: `{{\"linuxcommand\": \"apt update && apt install -y nano\"}}`\n"
        f"- User step: 'Check if bash shell is available and print its version.'\n"
        f"  Your JSON Output: `{{\"linuxcommand\": \"bash --version\"}}`\n"
        f"- User step: 'Start a bash shell.' (If this is the step, interpret as checking availability or a simple non-interactive command. This agent doesn't support interactive sub-shells.)\n"
        f"  Your JSON Output: `{{\"linuxcommand\": \"bash -c 'echo Bash is available'\"}}`\n\n"
        f"Adhere strictly to ALL these instructions. Generate ONLY the JSON object."
    )

    messages_api = [{"role": "system", "content": system_prompt}] + conversation_messages

    try:
        response = ollama.chat(
            model='llama3.2',  # Or a specific version like llama3:8b. The user's log had llama3.2
            messages=messages_api,
            format="json",  # This is crucial for Ollama to try and enforce JSON output
            options={"temperature": 0.0}  # Lower temperature for more deterministic command generation
        )
        raw_response_content = response.get('message', {}).get('content', '')

        # Attempt to parse the JSON
        data = json.loads(raw_response_content)
        cmd = data.get("linuxcommand")

        if cmd and isinstance(cmd, str) and cmd.strip():  # Ensure command is a non-empty string
            print(f"🤖 AI Command: '{cmd}'")
            return cmd.strip()  # Return stripped command

        # If cmd is missing, not a string, or empty after stripping
        error_reason = "Unknown issue"
        if not cmd:
            error_reason = "'linuxcommand' key missing or value is null"
        elif not isinstance(cmd, str):
            error_reason = "'linuxcommand' value is not a string"
        elif not cmd.strip():
            error_reason = "'linuxcommand' value is an empty string"

        print(f"❌ AI Error (command generation): {error_reason} in response. Full data: {data}")
        print(f"Raw response from AI (command generation): {raw_response_content}")
        return None

    except json.JSONDecodeError as e:
        raw_content_for_log = raw_response_content if 'raw_response_content' in locals() else "N/A"
        print(f"❌ JSON Decode Error (command generation): {e}. Raw AI response was: {raw_content_for_log}")
        return None
    except ollama.ResponseError as e:
        print(
            f"❌ Ollama API Error (command generation): {e.status_code} - {e.error if hasattr(e, 'error') else str(e)}")
        return None
    except Exception as e:
        print(f"❌ Unexpected Error (command generation): {e}")
        return None