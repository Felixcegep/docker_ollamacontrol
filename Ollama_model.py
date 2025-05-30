# Ollama_model.py
import ollama
import json


def linux_command(original_request, current_step, step_number, total_steps, all_steps,
                  previous_results, current_path, user_login, current_time):
    """Generate Linux command with full context"""

    # Build context from previous steps
    previous_context = ""
    if previous_results:
        previous_context = "\nPrevious steps completed:\n"
        for result in previous_results:
            previous_context += f"- {result['step']}: {result['command']} → {result['result']}\n"

    # Build full plan overview
    all_steps_text = "\n".join([f"{i + 1}. {step}" for i, step in enumerate(all_steps)])

    # Create comprehensive prompt
    prompt = f"""Generate ONE Linux command for Ubuntu container.

ORIGINAL USER REQUEST: "{original_request}"

FULL PLAN:
{all_steps_text}

CURRENT CONTEXT:
- Current directory: {current_path}
- Current step: {step_number}/{total_steps}
- Current step description: "{current_step}"
- Date/Time (UTC - YYYY-MM-DD HH:MM:SS formatted): {current_time}
- Current User's Login: {user_login}
{previous_context}

CRITICAL REQUIREMENTS:
1. Generate command for ONLY the current step: "{current_step}"
2. Consider what was accomplished in previous steps
3. Use exact names/paths from previous step outputs
4. Ensure consistency across all steps

RULES:
- Output JSON only: {{"linuxcommand": "command"}}
- Use apt-get not apt
- Add DEBIAN_FRONTEND=noninteractive for package installs
- Use mkdir -p for directories
- For cd commands, use exact folder names from previous steps
- For Python virtual environments, ensure python3-venv is installed first

EXAMPLES:
Previous created "project_folder" + current "go into project folder" → {{"linuxcommand": "cd project_folder"}}
Current "create project directory" → {{"linuxcommand": "mkdir -p project_folder"}}
Current "install curl package" → {{"linuxcommand": "DEBIAN_FRONTEND=noninteractive apt-get install -y curl"}}
Current "install python3-venv package" → {{"linuxcommand": "DEBIAN_FRONTEND=noninteractive apt-get install -y python3-venv"}}
Current "create virtual environment" → {{"linuxcommand": "python3 -m venv myenv"}}
Current "list files" → {{"linuxcommand": "ls -la"}}"""

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
            # Apply command optimizations
            cmd = optimize_command(cmd)
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


def optimize_command(cmd):
    """Apply standard optimizations to commands"""
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

    return cmd