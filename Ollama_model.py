from ollama import chat
import json

def control_linux(linuxcommand):
    print("✅ Linux command to execute:")
    return linuxcommand
def linux_command(user_question):
    response = chat(model='llama3.2', messages = [
    {
        "role": "system",
        "content": (
            "You are a command-line assistant. Your job is to provide exactly one simple Linux command based on the user's request.\n"
            "⚠️ Do not combine multiple commands using ';', '&&', or '|' — only one single action is allowed per response.\n"
            "\n"
            "Respond with a valid JSON object with exactly one field:\n"
            "- 'linuxcommand': a single Linux shell command that performs just one atomic action.\n"
            "\n"
            "Examples:\n"
            "{ \"linuxcommand\": \"mkdir myfolder\" }\n"
            "{ \"linuxcommand\": \"cd test\" }\n"
            "{ \"linuxcommand\": \"ls -l\" }\n"
            "\n"
            "❌ Do NOT output explanations.\n"
            "❌ Do NOT include multiple commands.\n"
            "✅ Output only the JSON object."
        )
    },
    {"role": "user", "content": user_question}
])

    raw = response['message']['content'].strip()

    try:
        data = json.loads(raw)
        if "linuxcommand" in data:
            return control_linux(data["linuxcommand"])
        else:
            print("❌ 'linuxcommand' key not found in the response.")
            print("Full response:", data)
    except json.JSONDecodeError as e:
        print("❌ Invalid JSON:", e)
        print("Raw output:", raw)
