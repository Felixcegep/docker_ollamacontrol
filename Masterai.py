# Masterai.py
import ollama
import json


def linux_step_planning(user_message, current_path, conversation_history=None):
    """Generate planning steps using Ollama"""

    history_context = ""
    if conversation_history:
        recent_messages = conversation_history[-6:]
        history_entries = [f"- {msg['role']}: {msg['content']}"
                           for msg in recent_messages if 'role' in msg]
        if history_entries:
            history_context = f"Recent conversation:\n{chr(10).join(history_entries)}\n\n"

    system_prompt = f"""You are a Linux action planner for Ubuntu Docker container (root access).
Current directory: '{current_path}'

{history_context}Task: Break down this request into clear, actionable steps: '{user_message}'

PLANNING RULES:
- For simple single commands (ls, pwd, which), create ONE step only
- For installations, use "Install X package" format
- For file/folder operations, be specific about names
- For navigation, use "Navigate to X directory" format
- Keep steps concise but descriptive
- Output ONLY valid JSON: {{"linuxcommand": ["step1", "step2", ...]}}

STEP EXAMPLES:
"check if wget exists" → {{"linuxcommand": ["Check if wget is installed"]}}
"make project folder and go there" → {{"linuxcommand": ["Create project directory", "Navigate to project directory"]}}
"install git and curl" → {{"linuxcommand": ["Install git package", "Install curl package"]}}
"list files in current directory" → {{"linuxcommand": ["List files in current directory"]}}
"create config file" → {{"linuxcommand": ["Create configuration file"]}}"""

    try:
        response = ollama.chat(
            model='qwen2.5-coder:7b',
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
    """Create a recovery plan to fix the error"""

    # Build context from what was done before the error
    previous_context = ""
    if step_results:
        previous_context = "\nPrevious successful steps:\n"
        for result in step_results:
            previous_context += f"- {result['step']}: {result['command']} → {result['result']}\n"

    system_prompt = f"""You are an error recovery specialist for Linux Ubuntu container.

ERROR ANALYSIS:
- Failed command: {error_info['failed_command']}
- Error message: {error_info['error_message']}
- Exit code: {error_info['exit_code']}
- Failed step: {error_info['failed_step']}
- Current path: {error_info['current_path']}
- Time: {current_time}

ORIGINAL REQUEST: "{original_request}"
{previous_context}

TASK: Analyze the error and create recovery steps to fix the problem.

COMMON ERROR PATTERNS & SOLUTIONS:
- Missing python3-venv package → Install python3-venv package
- Missing dependencies → Install required dependencies
- Permission errors → Fix permissions or use sudo
- Package not found → Update package list first
- Directory not exists → Create missing directories
- Service not running → Start required services

RECOVERY RULES:
- Create minimal steps to fix ONLY the immediate error
- Focus on installing missing packages/dependencies
- Use specific package names mentioned in error messages
- Don't repeat steps that already succeeded
- Output ONLY JSON: {{"recovery_steps": ["fix1", "fix2", ...]}}

EXAMPLES:
Error "python3-venv not available" → {{"recovery_steps": ["Install python3-venv package"]}}
Error "curl: command not found" → {{"recovery_steps": ["Install curl package"]}}
Error "permission denied" → {{"recovery_steps": ["Fix file permissions"]}}
Error "No such file or directory" → {{"recovery_steps": ["Create missing directory"]}}"""

    try:
        response = ollama.chat(
            model='qwen2.5-coder:7b',
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