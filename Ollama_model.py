from ollama import chat
import json

def control_linux(linuxcommand):
    print("✅ Linux command to execute:")
    return linuxcommand
def linux_command(user_question):
    response = chat(model='llama3.2', messages=[
        {
            "role": "system",
            "content": (
                "You are a command-line assistant. Your job is to provide a valid Linux command based on the user's request.\n"
                "Respond with a valid JSON object with exactly one field:\n"
                "- 'linuxcommand': a single Linux shell command that solves or answers the user's request.\n\n"
                "Example:\n"
                "{\n"
                "  \"linuxcommand\": \"ls -la\"\n"
                "}\n\n"
                "⚠️ Do NOT include markdown, code blocks, or explanations.\n"
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
