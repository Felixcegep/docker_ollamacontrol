import ollama
import json


def linux_step_planning(user_message, current_path, conversation_history=None, container_state=None):
    """Generate planning steps using Ollama with state awareness"""

    history_context = ""
    if conversation_history:
        recent_messages = conversation_history[-6:]
        history_entries = [f"- {msg['role']}: {msg['content']}"
                           for msg in recent_messages if 'role' in msg]
        if history_entries:
            history_context = f"Recent conversation:\n{chr(10).join(history_entries)}\n\n"

    # Build container state context
    state_context = ""
    if container_state:
        state_context = f"""
CURRENT CONTAINER STATE:
- Existing directories: {', '.join(container_state.get('directories', [])) or 'none'}
- Existing files: {', '.join(container_state.get('files', [])) or 'none'}
- Installed Python packages: {', '.join(container_state.get('python_packages', [])) or 'none'}
"""

    system_prompt = f"""You are a Linux action planner for Ubuntu Docker container (root access).
Current directory: '{current_path}'

{history_context}{state_context}

Task: Break down this request into clear, actionable steps: '{user_message}'

IMPORTANT STATE-AWARE RULES:
- Do NOT create directories/files that already exist (check CURRENT CONTAINER STATE)
- For Python packages (pytest, requests, etc.), use pip3, NOT apt-get
- For system packages (python3-pip, git, curl), use apt-get
- Avoid interactive editors (nano, vim) - use echo commands for file content
- Be specific about file paths (e.g., src/main.py not just main.py)

PLANNING RULES:
- For simple single commands (ls, pwd, which), create ONE step only
- For Python package installations, use "Install [package] using pip3"
- For system package installations, use "Install [package] system package"
- For file creation with content, use "Create [file] with [content]"
- For navigation, use "Navigate to [directory]"
- Skip steps for things that already exist
- Output ONLY valid JSON: {{"linuxcommand": ["step1", "step2", ...]}}

EXAMPLES:
"install pytest using pip" → {{"linuxcommand": ["Install python3-pip system package", "Install pytest using pip3"]}}
"create main.py with add function" → {{"linuxcommand": ["Create src/main.py with add function"]}}
"run pytest tests" → {{"linuxcommand": ["Run pytest on tests directory"]}}
"check if pytest exists" → {{"linuxcommand": ["Check if pytest is installed"]}}"""

    try:
        response = ollama.chat(
            model='deepseek-r1:8b-0528-qwen3-fp16',
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            format="json",
            options={"temperature": 0.1, "top_p": 0.9}
        )

        content = response.get('message', {}).get('content', '').strip()

        if '{' in content:
            start = content.find('{')
            end = content.rfind('}') + 1
            content = content[start:end]

        parsed = json.loads(content)
        commands = parsed.get("linuxcommand", [])

        if isinstance(commands, list) and all(isinstance(cmd, str) and cmd.strip() for cmd in commands):
            return {"linuxcommand": [cmd.strip() for cmd in commands]}
        else:
            print("❌ Invalid command format in plan")
            return None

    except json.JSONDecodeError as e:
        print(f"❌ Planning JSON error: {e}")
        return None
    except Exception as e:
        print(f"❌ Planning error: {e}")
        return None


def create_error_recovery_plan(error_info, original_request, step_results, current_time):
    """Create an intelligent recovery plan to fix the error"""

    # Build context from what was done before the error
    previous_context = ""
    if step_results:
        previous_context = "\nPrevious successful steps:\n"
        for result in step_results:
            previous_context += f"- {result['step']}: {result['command']} → {result['result']}\n"

    # Build container state context
    state_context = ""
    container_state = error_info.get('container_state', {})
    if container_state:
        state_context = f"""
CONTAINER STATE:
- Python packages installed: {', '.join(container_state.get('python_packages', [])) or 'none'}
- Directories: {', '.join(container_state.get('directories', [])) or 'none'}
- Files: {', '.join(container_state.get('files', [])) or 'none'}
"""

    system_prompt = f"""You are an intelligent error recovery specialist for Linux Ubuntu container.

ERROR ANALYSIS:
- Failed command: {error_info['failed_command']}
- Error message: {error_info['error_message']}
- Exit code: {error_info['exit_code']}
- Failed step: {error_info['failed_step']}
- Current path: {error_info['current_path']}
- Time: {current_time}
{state_context}
ORIGINAL REQUEST: "{original_request}"
{previous_context}

TASK: Analyze the error and create INTELLIGENT recovery steps.

CRITICAL ERROR PATTERNS & CORRECT SOLUTIONS:
1. "pytest: command not found" → Install pytest using pip3 (NOT apt-get)
2. "pip3: command not found" → Install python3-pip system package first
3. "python3-venv not available" → Install python3-venv system package
4. "nano: command not found" → Use echo commands instead of interactive editors
5. "Too many errors from stdin" → Command needs non-interactive approach
6. "No such file or directory" → Create missing directories/files
7. "E: Unable to locate package [python-package]" → Use pip3, not apt-get

INTELLIGENT RECOVERY RULES:
- Python packages (pytest, requests, flask, etc.) → Use pip3 install [package]
- System packages (python3-pip, git, curl, etc.) → Use apt-get install [package]
- For file editing errors → Use echo commands to write content
- Check if pip3 is installed before trying to install Python packages
- Don't repeat failed approaches - learn from the error
- Output ONLY JSON: {{"recovery_steps": ["fix1", "fix2", ...]}}

SMART EXAMPLES:
Error "pytest: command not found" → {{"recovery_steps": ["Install pytest using pip3"]}}
Error "pip3: command not found" → {{"recovery_steps": ["Install python3-pip system package", "Install pytest using pip3"]}}
Error "nano main.py failed" → {{"recovery_steps": ["Create main.py using echo command"]}}
Error "E: Unable to locate package pytest" → {{"recovery_steps": ["Install pytest using pip3 instead of apt-get"]}}"""

    try:
        response = ollama.chat(
            model='deepseek-r1:8b-0528-qwen3-fp16',
            messages=[{"role": "user", "content": system_prompt}],
            format="json",
            options={"temperature": 0.2, "top_p": 0.9}
        )

        content = response.get('message', {}).get('content', '').strip()

        if '{' in content:
            start = content.find('{')
            end = content.rfind('}') + 1
            content = content[start:end]

        parsed = json.loads(content)
        recovery_steps = parsed.get("recovery_steps", [])

        if isinstance(recovery_steps, list) and all(isinstance(step, str) and step.strip() for step in recovery_steps):
            return {"recovery_steps": [step.strip() for step in recovery_steps]}
        else:
            print("❌ Invalid recovery plan format")
            return None

    except json.JSONDecodeError as e:
        print(f"❌ Recovery plan JSON error: {e}")
        return None
    except Exception as e:
        print(f"❌ Recovery plan error: {e}")
        return None