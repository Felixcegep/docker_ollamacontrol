# main_docker_agent.py
import json
import docker
import shlex
from Ollama_model import linux_command
from Masterai import linux_step_planning


def exec_cmd_in_container(container_ref, command_str):
    """Runs command in container, returns (exit_code, stdout_str, stderr_str)."""
    try:
        exit_code, (out_bytes, err_bytes) = container_ref.exec_run(
            f"bash -c {shlex.quote(command_str)}", demux=True, tty=False
        )
        stdout = out_bytes.decode('utf-8', 'ignore').strip() if out_bytes else ""
        stderr = err_bytes.decode('utf-8', 'ignore').strip() if err_bytes else ""
        return exit_code, stdout, stderr
    except Exception as e:
        return -1, "", f"Python error during exec: {e}"


# --- Docker Setup ---
container = None
try:
    client = docker.from_env()
    client.ping()
    print("✅ Docker connected.")
    # Using a more common base image like ubuntu:22.04 or similar
    # Ensure it has common tools or be prepared for the AI to install them
    container = client.containers.run(
        "ubuntu:latest", command="sleep infinity", tty=True, detach=True, remove=True
    )
    print(f"✅ Container '{container.name}' up.")
except docker.errors.DockerException as e:
    print(f"❌ Docker Error: {e}\nPlease ensure Docker is running.")
    exit(1)

# --- Agent State & Loop ---
current_path = "/"
messages = [] # Stores the history of interactions
try:
    while True:
        user_input = input(f"\n[{container.name}:{current_path}]$ ")
        if user_input.lower() == "exit":
            print("👋 Exiting session.")
            break

        messages.append({"role": "user", "content": user_input})

        print("🤔 AI (Planning)...")
        # Pass the conversation history (messages) to the planner
        parsed_plan = linux_step_planning(user_input, current_path, messages)

        if parsed_plan:
            print("\n--- Parsed Planning Steps ---")
            print(json.dumps(parsed_plan, indent=2))

            steps = parsed_plan.get("linuxcommand", [])
            if not steps:
                print("ℹ️ AI planned no steps for the input.")
                # Optional: Remove the last user message if no action is taken
                # if messages and messages[-1]["role"] == "user": messages.pop()
                continue

            all_steps_succeeded_for_this_plan = True
            for step_description in steps:
                print(f"\n➡️ Processing step: '{step_description}'")

                current_step_context_for_llm = [{"role": "user", "content": step_description}]

                print("🤔 AI (Generating Command)...")
                ai_command = linux_command(current_step_context_for_llm, current_path)

                if not ai_command:
                    print(f"❌ AI failed to generate command for step: '{step_description}'. Aborting rest of plan.")
                    all_steps_succeeded_for_this_plan = False
                    break

                executed_successfully = False
                if ai_command.startswith("cd "):
                    path_arg = ai_command[3:].strip()
                    if any(c in path_arg for c in [';', '&&', '||', '|', '`', '$(']):
                        print(f"❌ Invalid 'cd' (multiple actions): '{ai_command}'")
                        all_steps_succeeded_for_this_plan = False
                        break

                    cd_exec_str = f"cd {shlex.quote(current_path)} && cd {shlex.quote(path_arg)} && pwd -P"
                    print(f"⚙️ Exec: '{ai_command}' (from '{current_path}')")
                    ec, new_pwd, err_pwd = exec_cmd_in_container(container, cd_exec_str)

                    if ec == 0 and new_pwd:
                        if new_pwd != current_path:
                            print(f"📁 Path changed to: {new_pwd}")
                            current_path = new_pwd
                        else:
                            print(f"📁 Path unchanged: {current_path}")
                        if err_pwd: print(f"⚠️ CD stderr: {err_pwd}")
                        executed_successfully = True
                    else:
                        print(f"❌ CD Error: {err_pwd or 'Failed to change directory'}")
                        all_steps_succeeded_for_this_plan = False
                        break
                else:
                    full_command_to_run = f"cd {shlex.quote(current_path)} && {ai_command}"
                    print(f"⚙️ Exec: '{ai_command}' (in '{current_path}')")
                    ec, out, err = exec_cmd_in_container(container, full_command_to_run)

                    if ec == 0:
                        if out: print(f"🖥️ Stdout:\n{out}")
                        if err: print(f"⚠️ Stderr:\n{err}")
                        if not out and not err: print("✅ OK (no output).")
                        executed_successfully = True
                    else:
                        print(f"❌ Command Error (code {ec}):")
                        if err: print(f"Stderr:\n{err}")
                        elif out: print(f"Stdout (error?):\n{out}")
                        else: print("(No output from failed command)")
                        all_steps_succeeded_for_this_plan = False
                        break

                if executed_successfully:
                    messages.append({"role": "assistant", "content": ai_command})

            if all_steps_succeeded_for_this_plan and steps:
                print("\n✅ All planned steps executed successfully.")
            elif steps:
                print("\n⚠️ Plan execution stopped due to an error in one of the steps.")

        else:
            print("❌ AI failed to generate a plan. Try rephrasing.")
            # Optional: remove the last user message if planning failed entirely
            # if messages and messages[-1]["role"] == "user" and messages[-1]["content"] == user_input:
            #     messages.pop()
finally:
    if container:
        print(f"\n🛑 Stopping '{container.name}'...")
        try:
            container.stop()
            print("🗑️ Container stopped.")
        except docker.errors.NotFound:
            print("Container already gone.")
        except Exception as e:
            print(f"Error stopping container: {e}")