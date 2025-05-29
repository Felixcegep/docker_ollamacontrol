import ollama
import json

def linux_step_planning(user_message, current_path, conversation_history=None):
    """Generate planning steps using Ollama"""

    # Build context from recent history
    history_str = ""
    if conversation_history:
        recent = conversation_history[-6:]  # Last 6 messages
        history_entries = [f"- {msg['role']}: {msg['content']}" for msg in recent if 'role' in msg]
        if history_entries:
            history_str = f"Previous interactions:\n{chr(10).join(history_entries)}\n\n"

    system_prompt = f"""You are a Linux action planner for Ubuntu Docker container (root access).
Current directory: '{current_path}'

{history_str}Task: Break down this request into actionable steps: '{user_message}'

CRITICAL RULES:
- For simple commands (which, ls, pwd, mkdir), create just ONE step
- For checking if something is installed, use "Check if X is installed" 
- For package installation, use "Install X package"
- For creating folders, use "Create directory X"
- Output ONLY JSON: {{"linuxcommand": ["step1", "step2", ...]}}

EXAMPLES:
User: "check if wget is installed" → {{"linuxcommand": ["Check if wget is installed"]}}
User: "which wget" → {{"linuxcommand": ["Check location of wget command"]}}
User: "make a new folder" → {{"linuxcommand": ["Create a new directory"]}}
User: "install curl wget" → {{"linuxcommand": ["Install curl and wget packages"]}}
User: "list files" → {{"linuxcommand": ["List files in current directory"]}}
User: "create project folder and install git" → {{"linuxcommand": ["Create project directory", "Install git package"]}}"""

    try:
        response = ollama.chat(
            model='qwen2.5-coder:7b',
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            format="json",
            options={"temperature": 0.1}
        )

        content = response.get('message', {}).get('content')
        if not content:
            return None

        # Clean JSON response
        if '{' in content:
            content = content[content.find('{'):content.rfind('}') + 1]

        parsed = json.loads(content)
        commands = parsed.get("linuxcommand", [])

        if isinstance(commands, list) and all(isinstance(cmd, str) for cmd in commands):
            return {"linuxcommand": [cmd.strip() for cmd in commands if cmd.strip()]}

        return None

    except (json.JSONDecodeError, Exception) as e:
        print(f"Planning error: {e}")
        return None