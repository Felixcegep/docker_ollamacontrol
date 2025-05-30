import ollama
import json


def linux_command(original_request, current_step, step_number, total_steps, all_steps,
                  previous_results, current_path, user_login, current_time, container_state=None):
    """Generate Linux command with full context and intelligence"""

    # Build context from previous steps
    previous_context = ""
    if previous_results:
        previous_context = "\nPrevious steps completed:\n"
        for result in previous_results:
            previous_context += f"- {result['step']}: {result['command']} → {result['result']}\n"

    # Build container state context
    state_context = ""
    if container_state:
        state_context = f"""
CONTAINER STATE AWARENESS:
- Existing directories: {', '.join(container_state.get('directories', [])) or 'none'}
- Existing files: {', '.join(container_state.get('files', [])) or 'none'}
- Python packages installed: {', '.join(container_state.get('python_packages', [])) or 'none'}
"""

    # Build full plan overview
    all_steps_text = "\n".join([f"{i + 1}. {step}" for i, step in enumerate(all_steps)])

    # Create comprehensive prompt
    prompt = f"""Generate ONE INTELLIGENT Linux command for Ubuntu container.

ORIGINAL USER REQUEST: "{original_request}"

FULL PLAN:
{all_steps_text}

CURRENT CONTEXT:
- Current directory: {current_path}
- Current step: {step_number}/{total_steps}
- Current step description: "{current_step}"
- Date/Time (UTC - YYYY-MM-DD HH:MM:SS formatted): {current_time}
- Current User's Login: {user_login}
{state_context}{previous_context}

CRITICAL INTELLIGENCE RULES:
1. For Python packages (pytest, requests, flask, etc.) → Use pip3 install [package]
2. For system packages (python3-pip, git, curl, etc.) → Use apt-get install [package]
3. For file creation with content → Use echo 'content' > filename (NOT nano/vim)
4. For directory navigation → Use exact paths from previous steps
5. Check container state - don't create existing files/directories
6. Ensure pip3 is available before installing Python packages

COMMAND GENERATION RULES:
- Output JSON only: {{"linuxcommand": "command"}}
- Use apt-get not apt for system packages
- Add DEBIAN_FRONTEND=noninteractive for apt-get installs
- Use mkdir -p for directories (but check if they exist first)
- Use echo commands for file content, never interactive editors
- Use pip3 for Python packages, apt-get for system packages

INTELLIGENT EXAMPLES:
"Install pytest using pip3" → {{"linuxcommand": "pip3 install pytest"}}
"Install python3-pip system package" → {{"linuxcommand": "DEBIAN_FRONTEND=noninteractive apt-get install -y python3-pip"}}
"Create src/main.py with add function" → {{"linuxcommand": "echo 'def add(a, b):\\n    return a + b' > src/main.py"}}
"Run pytest on tests directory" → {{"linuxcommand": "python3 -m pytest tests/"}}
"Check if pytest is installed" → {{"linuxcommand": "pip3 show pytest"}}
"Create project directory" (if src exists) → {{"linuxcommand": "echo 'Directory src already exists'"}}
"Navigate to project directory" → {{"linuxcommand": "cd testpy"}}"""

    try:
        response = ollama.chat(
            model='qwen2.5-coder:7b',
            messages=[{"role": "user", "content": prompt}],
            format="json",
            options={"temperature": 0.1, "top_p": 0.9}
        )

        content = response.get('message', {}).get('content', '').strip()

        # Extract JSON from response
        if '{' in content:
            start = content.find('{')
            end = content.rfind('}') + 1
            content = content[start:end]

        data = json.loads(content)
        cmd = data.get("linuxcommand", "").strip()

        if cmd:
            # Apply intelligent command optimizations
            cmd = optimize_command_intelligently(cmd, container_state)
            print(f"🤖 Command: {cmd}")
            return cmd
        else:
            print("❌ Empty command in response")
            return None

    except json.JSONDecodeError as e:
        print(f"❌ JSON parsing error: {e}")
        return None
    except Exception as e:
        print(f"❌ Command generation error: {e}")
        return None


def optimize_command_intelligently(cmd, container_state=None):
    """Apply intelligent optimizations to commands"""

    # Skip if trying to create existing directories
    if container_state and cmd.startswith('mkdir -p '):
        dir_name = cmd.replace('mkdir -p ', '').strip()
        if dir_name in container_state.get('directories', []):
            return f"echo 'Directory {dir_name} already exists'"

    # Skip if trying to create existing files
    if container_state and cmd.startswith('touch '):
        file_name = cmd.replace('touch ', '').strip()
        if file_name in container_state.get('files', []):
            return f"echo 'File {file_name} already exists'"

    # Replace apt with apt-get for scripting
    if cmd.startswith('apt '):
        cmd = cmd.replace('apt ', 'apt-get ', 1)

    # Add DEBIAN_FRONTEND for apt installs
    if 'apt-get install' in cmd and 'DEBIAN_FRONTEND' not in cmd:
        cmd = f'DEBIAN_FRONTEND=noninteractive {cmd}'

    # Add -p flag to mkdir for safety
    if cmd.startswith('mkdir ') and '-p' not in cmd:
        cmd = cmd.replace('mkdir ', 'mkdir -p ', 1)

    # Add -y flag to apt-get operations if missing
    if 'apt-get' in cmd and cmd.endswith('apt-get update'):
        cmd += ' -y'
    elif 'apt-get install' in cmd and ' -y' not in cmd:
        cmd = cmd.replace('install', 'install -y')

    # Fix common Python package installation mistakes
    if 'apt-get install' in cmd:
        python_packages = ['pytest', 'requests', 'flask', 'django', 'numpy', 'pandas']
        for pkg in python_packages:
            if pkg in cmd:
                return f"pip3 install {pkg}"

    return cmd