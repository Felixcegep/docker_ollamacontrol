# main_docker_agent.py
import docker
import shlex
# No direct need for 'json' or 'os' in this file with the current structure

from Ollama_model import linux_command  # Ensure this matches your file name

# --- Docker Setup ---
try:
    client = docker.from_env()
    client.ping()
    print("✅ Docker client connected.")
except docker.errors.DockerException as e:
    print(f"❌ Error connecting to Docker: {e}")
    print("Please ensure Docker Desktop/Daemon is running and configured correctly.")
    exit(1)

container = None

try:
    print("🚀 Starting Ubuntu container...")
    container = client.containers.run(
        "ubuntu:latest",
        command="sleep infinity",
        tty=True,
        detach=True,
        remove=True  # Automatically remove container on stop
    )
    print(f"✅ Container '{container.name}' started with ID: {container.id}")

    # --- Agent State ---
    current_path = "/"
    messages = []  # This will store the history of {"role": "user", "content": ...}
    # and {"role": "assistant", "content": ...}

    # --- Interaction Loop ---
    while True:
        prompt_display_path = current_path if current_path else "/"
        demande_ia = input(
            f"\n[{container.name}:{prompt_display_path}]$ Décrivez l'action que vous souhaitez effectuer dans Ubuntu (ou 'exit' pour quitter) : ")
        if demande_ia.lower() == "exit":
            print("👋 Exiting session.")
            break

        messages.append({"role": "user", "content": demande_ia})

        print("🤔 Asking AI for command...")
        # --- CRITICAL CHANGE HERE: Pass the `messages` list directly, and `current_path` ---
        command = linux_command(messages, current_path)

        if not command:
            print("❌ AI failed to generate a valid command. Please try rephrasing your request.")
            if messages:  # Remove the last user message if AI failed
                messages.pop()
            continue

        # Add AI's command to history for the next turn's context
        messages.append({"role": "assistant", "content": command})

        # --- Handle 'cd' command specifically ---
        if command.startswith("cd "):
            new_path_arg = command[3:].strip()

            if any(char in new_path_arg for char in [';', '&&', '||', '|', '`', '$(']):
                print(
                    f"❌ Error: AI generated an invalid 'cd' command with multiple actions or dangerous characters: '{command}'")
                print("   (The AI was asked for a single 'cd' operation).")
                if len(messages) >= 2:
                    messages.pop(); messages.pop()  # Pop assistant and user
                elif messages:
                    messages.pop()  # Pop only user if that's all left
                continue

            # Command to execute in bash: go to current_path, then attempt new_path_arg, then print new absolute path
            cd_command_to_exec = f"cd {shlex.quote(current_path)} && cd {shlex.quote(new_path_arg)} && pwd -P"

            print(f"⚙️ Executing CD command in container: '{cd_command_to_exec}'")
            result = container.exec_run(f"bash -c {shlex.quote(cd_command_to_exec)}", demux=True)
            stdout_bytes, stderr_bytes = result.output

            if result.exit_code == 0:
                old_path = current_path
                # pwd -P output is the new current_path
                new_resolved_path = stdout_bytes.decode('utf-8', errors='ignore').strip() if stdout_bytes else ""

                if not new_resolved_path:  # Should not happen with pwd -P on success
                    print(f"⚠️ CD command succeeded but 'pwd -P' gave no output. Path unchanged: '{current_path}'")
                elif new_resolved_path == current_path:
                    print(f"📁 Still in '{current_path}' (path did not change or was already correct).")
                else:
                    current_path = new_resolved_path
                    print(f"📁 Directory changed from '{old_path}' to '{current_path}'")

                if stderr_bytes:  # Print any stderr from cd operation (e.g., bash warnings)
                    stderr_str = stderr_bytes.decode('utf-8', errors='ignore').strip()
                    if stderr_str: print(f"⚠️ CD stderr: {stderr_str}")
            else:
                error_output = stderr_bytes.decode('utf-8',
                                                   errors='ignore').strip() if stderr_bytes else "unknown error (cd failed)"
                print(f"❌ Error changing directory: {error_output}")
                if len(messages) >= 2:
                    messages.pop(); messages.pop()
                elif messages:
                    messages.pop()
            continue  # Go back to input prompt

        # --- Execute other commands (non-cd) ---
        # AI should generate commands relative to `current_path` due to the new system prompt.
        # So, we still `cd` to `current_path` first to ensure the execution environment matches the AI's assumption.
        full_command_for_exec = f"cd {shlex.quote(current_path)} && {command}"

        print(f"⚙️ Executing command in container: '{full_command_for_exec}'")
        try:
            result = container.exec_run(
                f"bash -c {shlex.quote(full_command_for_exec)}",
                demux=True,
                tty=False  # Usually False for non-interactive exec
            )
            stdout_bytes, stderr_bytes = result.output

            # Process stdout
            stdout_content = ""
            if stdout_bytes is not None:
                stdout_content = stdout_bytes.decode('utf-8', errors='ignore').strip()

            # Process stderr
            stderr_content = ""
            if stderr_bytes is not None:
                stderr_content = stderr_bytes.decode('utf-8', errors='ignore').strip()

            if result.exit_code == 0:
                if stdout_content:
                    print("🖥️ Result (stdout):\n", stdout_content)
                if stderr_content:  # Output warnings or other stderr even on success
                    print("⚠️ Result (stderr):\n", stderr_content)
                if not stdout_content and not stderr_content:
                    print("✅ Command executed successfully with no output.")

            else:  # Command failed
                print(f"❌ Command exited with non-zero status ({result.exit_code}).")
                if stderr_content:
                    print("🖥️ Stderr:\n", stderr_content)
                elif stdout_content:  # Some commands output errors to stdout
                    print("🖥️ Stdout (error?):\n", stdout_content)
                else:
                    print("🖥️ (No output on stdout or stderr for the failed command)")

                # Revert last user and assistant message on failure
                if len(messages) >= 2:
                    messages.pop(); messages.pop()
                elif messages:
                    messages.pop()

        except Exception as e:  # Catch any other unexpected Python errors
            print(f"❌ An unexpected Python error occurred during command execution: {e}")
            if len(messages) >= 2:
                messages.pop(); messages.pop()
            elif messages:
                messages.pop()

finally:
    # --- Cleanup ---
    if container:
        print(f"\n🛑 Stopping container '{container.name}' ({container.id})...")
        try:
            container.stop()
            # container.remove() is handled by 'remove=True' in run args
            print("🗑️ Container stopped and removed.")
        except docker.errors.NotFound:
            print("Container already stopped or removed.")
        except Exception as e:
            print(f"Error during container cleanup: {e}")