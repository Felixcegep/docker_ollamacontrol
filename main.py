# main.py
import json
import docker
import shlex
import time  # Added for potential delays/retries if needed
from datetime import datetime, timezone  # For timezone-aware UTC time
from Ollama_model import linux_command
from Masterai import linux_step_planning


# --- Helper Functions ---
def exec_cmd_in_container(container_ref, command_str, log_prefix="⚙️ Exec:"):
    """Runs command in container, returns (exit_code, stdout_str, stderr_str)."""
    # Ensure DEBIAN_FRONTEND is set for apt commands if not already in command_str
    # However, for general commands, it's not needed.
    # For apt, it's better to prefix it in the command itself during setup.
    full_command = f"bash -c {shlex.quote(command_str)}"
    # print(f"{log_prefix} '{command_str}'") # Verbose logging if needed
    try:
        exit_code, (out_bytes, err_bytes) = container_ref.exec_run(
            full_command, demux=True, tty=False
        )
        stdout = out_bytes.decode('utf-8', 'ignore').strip() if out_bytes else ""
        stderr = err_bytes.decode('utf-8', 'ignore').strip() if err_bytes else ""
        return exit_code, stdout, stderr
    except Exception as e:
        print(f"❌ Python error during exec: {e} (Command: {command_str})")
        return -1, "", f"Python error during exec: {e}"


def perform_initial_container_setup(container_ref):
    """Configures apt, Canadian mirrors, and updates the system in the container."""
    print(f"🔧 Performing initial setup for container '{container_ref.name}'...")

    mirror_url = "http://mirror.csclub.uwaterloo.ca/ubuntu/"
    release_name = "jammy"  # For Ubuntu 22.04

    sources_list_content = f"""
deb {mirror_url} {release_name} main restricted universe multiverse
deb {mirror_url} {release_name}-updates main restricted universe multiverse
deb {mirror_url} {release_name}-backports main restricted universe multiverse
deb {mirror_url} {release_name}-security main restricted universe multiverse
"""
    setup_steps = [
        ("echo 'Setting up sources.list for Canadian mirror (Waterloo)...'",
         f"echo {shlex.quote(sources_list_content)} > /etc/apt/sources.list"),
        ("echo 'Cleaning up additional source lists directories...' && rm -f /etc/apt/sources.list.d/*",
         "rm -f /etc/apt/sources.list.d/* || true"),  # Allow to pass if dir is empty or no files
        (
        "echo 'Ensuring DEBIAN_FRONTEND is noninteractive for apt operations...' && echo 'DEBIAN_FRONTEND=noninteractive' >> /etc/environment",
        "echo 'DEBIAN_FRONTEND=noninteractive' >> /etc/environment"),
        ("echo 'Updating package lists from new mirror...' && apt-get update -y",
         "apt-get update -y"),
        (
        "echo 'Upgrading system packages (non-interactive)...' && apt-get upgrade -y -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold",
        "apt-get upgrade -y -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold"),
        ("echo 'Cleaning up unused packages...' && apt-get autoremove -y && apt-get clean -y",
         "apt-get autoremove -y && apt-get clean -y"),
        ("echo 'Verifying apt configuration...' && apt-cache policy",  # Helps to see current sources
         "apt-cache policy")
    ]

    for i, (log_msg, cmd) in enumerate(setup_steps):
        print(f"🔄 [{i + 1}/{len(setup_steps)}] {log_msg}")
        # Prefix with DEBIAN_FRONTEND for apt commands to be safe
        exec_prefix = "DEBIAN_FRONTEND=noninteractive " if "apt-get" in cmd else ""
        ec, out, err = exec_cmd_in_container(container_ref, exec_prefix + cmd, log_prefix=f"🔧 Setup:")

        if ec != 0:
            print(f"❌ Error during setup step: {cmd}")
            print(f"   Exit Code: {ec}")
            if out: print(f"   Stdout: {out}")
            if err: print(f"   Stderr: {err}")
            print("🚨 Initial container setup failed. Exiting.")
            container_ref.stop()
            container_ref.remove()
            exit(1)
        else:
            if out and "apt-cache policy" not in cmd: print(
                f"   ✅ Output: {out[:200]}...")  # Print some output for success
            if err: print(f"   ⚠️ Stderr (Warning): {err}")  # Some apt commands produce warnings on stderr
            print(f"   ✅ Step completed successfully.")

    print("✅ Initial container setup completed successfully!")
    return True


# --- Docker Setup ---
container = None
client = None
try:
    client = docker.from_env()
    client.ping()
    print("✅ Docker connected.")

    # Use a specific Ubuntu version for stability (Jammy Jellyfish)
    image_name = "ubuntu:22.04"
    print(f"🚀 Pulling Docker image '{image_name}' if not present (this might take a moment)...")
    try:
        client.images.get(image_name)
        print(f"✅ Image '{image_name}' found locally.")
    except docker.errors.ImageNotFound:
        print(f"Image '{image_name}' not found locally. Pulling...")
        client.images.pull(image_name)
        print(f"✅ Image '{image_name}' pulled successfully.")

    container = client.containers.run(
        image_name, command="sleep infinity", tty=True, detach=True, remove=True
    )
    print(f"✅ Container '{container.name}' (ID: {container.id[:12]}) is up from image '{image_name}'.")

    # Perform initial setup
    perform_initial_container_setup(container)

except docker.errors.DockerException as e:
    print(f"❌ Docker Error: {e}\nPlease ensure Docker is running and you have permissions.")
    if container:  # If container was created but setup failed before this catch
        try:
            container.stop()
            # container.remove() # remove=True in run() handles this
        except:
            pass
    exit(1)
except Exception as e:
    print(f"❌ An unexpected error occurred during setup: {e}")
    if container:
        try:
            container.stop()
        except:
            pass
    exit(1)

# --- Agent State & Loop ---
current_path = "/"  # Default to root, as it's a clean container
messages = []  # Stores the history of interactions

try:
    print(f"\n🎉 Docker Agent Ready. Current directory: {current_path}")
    while True:
        user_input = input(f"\n[{container.name}:{current_path}]$ ")
        if user_input.lower() == "exit":
            print("👋 Exiting session.")
            break

        messages.append({"role": "user", "content": user_input})

        print("🤔 AI (Planning)...")
        # Pass the conversation history (messages) to the planner
        # Also pass current_path as planner might use it
        parsed_plan = linux_step_planning(user_input, current_path, messages)

        if parsed_plan and parsed_plan.get("linuxcommand"):
            steps = parsed_plan.get("linuxcommand", [])
            if not steps:
                print("ℹ️ AI planned no steps for the input.")
                if messages and messages[-1]["role"] == "user": messages.pop()  # Remove user message if no action
                continue

            print(f"\n📋 AI Plan ({len(steps)} steps):")
            for i, step_desc in enumerate(steps): print(f"  [{i + 1}] {step_desc}")

            all_steps_succeeded = True
            for step_description in steps:
                print(f"\n➡️ Processing step: '{step_description}'")

                # Context for this specific step for command generation
                current_step_context_for_llm = [{"role": "user", "content": step_description}]

                print("🤔 AI (Generating Command)...")
                ai_command = linux_command(current_step_context_for_llm, current_path)

                if not ai_command:
                    print(f"❌ AI failed to generate command for step: '{step_description}'. Aborting rest of plan.")
                    all_steps_succeeded = False
                    break

                # Special handling for 'cd'
                if ai_command.startswith("cd "):
                    path_arg = ai_command[3:].strip()
                    # Basic validation for cd to prevent complex chained commands via 'cd'
                    if any(c in path_arg for c in [';', '&&', '||', '|', '`', '$(']):
                        print(f"❌ Invalid 'cd' (potential multiple actions): '{ai_command}'. Skipping.")
                        all_steps_succeeded = False  # Or just skip this step and continue
                        break  # Or continue, depending on desired strictness

                    # To correctly resolve paths (absolute, relative, ..), execute `cd` and then `pwd`
                    # Ensure `cd` is relative to current_path first
                    cd_exec_str = f"cd {shlex.quote(current_path)} && cd {shlex.quote(path_arg)} && pwd -P"
                    print(f"⚙️ Exec (cd): '{ai_command}' (from '{current_path}')")
                    ec, new_pwd, err_pwd = exec_cmd_in_container(container, cd_exec_str, log_prefix="💿 CD Exec:")

                    if ec == 0 and new_pwd:
                        if new_pwd != current_path:
                            print(f"📁 Path changed to: {new_pwd}")
                            current_path = new_pwd
                        else:
                            print(f"📁 Path unchanged: {current_path}")
                        if err_pwd: print(f"⚠️ CD stderr: {err_pwd}")
                        messages.append({"role": "assistant",
                                         "content": f"Changed directory to {current_path}"})  # Log successful cd
                    else:
                        print(f"❌ CD Error: {err_pwd or 'Failed to change directory'}")
                        all_steps_succeeded = False
                        break
                else:
                    # Prepend `cd` to the current path for other commands
                    full_command_to_run = f"cd {shlex.quote(current_path)} && {ai_command}"
                    print(f"⚙️ Exec: '{ai_command}' (in '{current_path}')")
                    ec, out, err = exec_cmd_in_container(container, full_command_to_run)

                    if ec == 0:
                        if out: print(f"🖥️ Stdout:\n{out}")
                        if err: print(
                            f"⚠️ Stderr:\n{err}")  # Often, successful commands might output to stderr (e.g., progress)
                        if not out and not err: print("✅ OK (no output).")
                        messages.append({"role": "assistant",
                                         "content": f"Executed: {ai_command}\nOutput:\n{out}\nError (if any):\n{err}"})
                    else:
                        print(f"❌ Command Error (code {ec}):")
                        if err:
                            print(f"Stderr:\n{err}")
                        elif out:
                            print(f"Stdout (error?):\n{out}")  # Sometimes errors go to stdout
                        else:
                            print("(No output from failed command)")
                        all_steps_succeeded = False
                        break  # Stop plan on error

            if all_steps_succeeded and steps:
                print("\n✅ All planned steps executed successfully.")
            elif steps:  # Implies not all_steps_succeeded
                print("\n⚠️ Plan execution stopped due to an error in one of the steps.")

        else:
            print("❌ AI failed to generate a plan or plan was empty. Try rephrasing or a different task.")
            if messages and messages[-1]["role"] == "user": messages.pop()

finally:
    if container:
        print(f"\n🛑 Stopping container '{container.name}'...")
        try:
            container.stop()
            # container.remove() # remove=True in run() ensures it's removed on stop or Docker daemon exit
            print("🗑️ Container stopped and will be removed.")
        except docker.errors.NotFound:
            print("ℹ️ Container already gone.")
        except Exception as e:
            print(f"Error stopping/removing container: {e}")
    print("👋 Session ended.")