import ollama
import json
import re
from datetime import datetime, timezone


def linux_command(conversation_messages, current_path):
    """Generate appropriate Linux command based on user input"""

    current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    current_user = "Felixcegep"

    system_prompt = f"""Generate ONE Linux command for Ubuntu Docker container (root shell).
Current directory: '{current_path}'
Current Date/Time (UTC): {current_time}
Current User: {current_user}

COMMAND GENERATION RULES:
- Generate the EXACT command needed for the user's request
- Use apt-get instead of apt for scripts
- Use DEBIAN_FRONTEND=noninteractive for package operations
- Output ONLY JSON: {{"linuxcommand": "command here"}}
- NO explanations or extra text

COMMON PATTERNS:
- Check if package installed: "which PACKAGE" or "dpkg -l | grep PACKAGE"
- Install packages: "DEBIAN_FRONTEND=noninteractive apt-get install -y PACKAGE"
- Create folder: "mkdir -p FOLDERNAME"
- List files: "ls -la" or "ls -l"
- Show current directory: "pwd"
- Check file existence: "ls -la FILENAME" or "test -f FILENAME && echo 'exists' || echo 'not found'"
- Show version: "COMMAND --version"
- Create file: "touch FILENAME" or "echo 'content' > FILENAME"
- Move/copy: "mv SOURCE DEST" or "cp SOURCE DEST"

EXAMPLES based on user requests:
User: "check if wget is installed" → {{"linuxcommand": "which wget"}}
User: "which wget" → {{"linuxcommand": "which wget"}}
User: "make a new folder" → {{"linuxcommand": "mkdir -p new_folder"}}
User: "create directory called projects" → {{"linuxcommand": "mkdir -p projects"}}
User: "install curl" → {{"linuxcommand": "DEBIAN_FRONTEND=noninteractive apt-get install -y curl"}}
User: "list files" → {{"linuxcommand": "ls -la"}}
User: "show current directory" → {{"linuxcommand": "pwd"}}
User: "create file test.txt" → {{"linuxcommand": "touch test.txt"}}"""

    max_retries = 3

    for attempt in range(max_retries):
        try:
            response = ollama.chat(
                model='llama3.2',
                messages=[{"role": "system", "content": system_prompt}] + conversation_messages,
                format="json",
                options={
                    "temperature": 0.1,  # Slightly higher for better variety
                    "top_p": 0.9,
                    "num_predict": 100
                }
            )

            content = response.get('message', {}).get('content', '').strip()

            if not content:
                if attempt < max_retries - 1:
                    print(f"⚠️ Empty response, retrying ({attempt + 1}/{max_retries})")
                    continue
                return None

            # Clean and parse JSON
            content = clean_json_response(content)
            data = json.loads(content)
            cmd = data.get("linuxcommand", "").strip()

            if not cmd:
                if attempt < max_retries - 1:
                    print(f"⚠️ Empty command, retrying ({attempt + 1}/{max_retries})")
                    continue
                return None

            # Optimize the command
            cmd = optimize_command(cmd)

            print(f"🤖 AI Command: '{cmd}'")
            return cmd

        except json.JSONDecodeError as e:
            if attempt < max_retries - 1:
                print(f"⚠️ JSON error, retrying ({attempt + 1}/{max_retries})")
                continue
            print(f"❌ JSON decode error: {e}")
            return None

        except Exception as e:
            if attempt < max_retries - 1:
                print(f"⚠️ Error, retrying ({attempt + 1}/{max_retries}): {e}")
                continue
            print(f"❌ Command generation error: {e}")
            return None

    return None


def clean_json_response(content):
    """Clean up JSON formatting"""
    # Find JSON object boundaries
    if '{' in content:
        start = content.find('{')
        end = content.rfind('}') + 1
        content = content[start:end]

    # Fix common escape issues
    content = content.replace('\\"', '"')
    content = content.replace('\\n', '\\\\n')

    return content.strip()


def optimize_command(cmd):
    """Optimize commands for better execution"""

    # Replace apt with apt-get for scripts
    if cmd.startswith('apt '):
        cmd = cmd.replace('apt ', 'apt-get ', 1)

    # Add DEBIAN_FRONTEND for apt operations if not present
    if 'apt-get install' in cmd and 'DEBIAN_FRONTEND' not in cmd:
        cmd = f'DEBIAN_FRONTEND=noninteractive {cmd}'

    # Add -p flag to mkdir for safety
    if cmd.startswith('mkdir ') and '-p' not in cmd:
        cmd = cmd.replace('mkdir ', 'mkdir -p ', 1)

    return cmd


# Test function to verify command generation
def test_command_generation():
    """Test various user inputs"""
    test_cases = [
        [{"role": "user", "content": "check if wget is installed"}],
        [{"role": "user", "content": "which wget"}],
        [{"role": "user", "content": "make a new folder"}],
        [{"role": "user", "content": "create directory called projects"}],
        [{"role": "user", "content": "install python3"}],
        [{"role": "user", "content": "list files"}],
        [{"role": "user", "content": "show current directory"}]
    ]

    for test in test_cases:
        print(f"\nTesting: {test[0]['content']}")
        result = linux_command(test, "/")
        print(f"Result: {result}")

# Uncomment to test
# if __name__ == "__main__":
#     test_command_generation()