# main.py
import json
import docker
import shlex
from datetime import datetime, timezone
from Ollama_model import linux_command
from Masterai import linux_step_planning, create_error_recovery_plan

# Configuration constants
UBUNTU_MIRROR = "http://mirror.csclub.uwaterloo.ca/ubuntu/"
UBUNTU_VERSION = "jammy"
DOCKER_IMAGE = "ubuntu:22.04"
USER_LOGIN = "Felixcegep"


def get_current_time():
    """Get current UTC time in specified format"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def exec_cmd(container, command, current_path="/"):
    """Execute command in container from current_path"""
    full_cmd = f"cd {shlex.quote(current_path)} && {command}"
    try:
        exit_code, (stdout, stderr) = container.exec_run(
            f"bash -c {shlex.quote(full_cmd)}", demux=True
        )
        out = stdout.decode('utf-8').strip() if stdout else ""
        err = stderr.decode('utf-8').strip() if stderr else ""
        return exit_code, out, err
    except Exception as e:
        return -1, "", str(e)


def setup_container(container):
    """Setup Ubuntu container with Canadian mirror and updates"""
    print("🔧 Setting up container...")

    sources = f"""deb {UBUNTU_MIRROR} {UBUNTU_VERSION} main restricted universe multiverse
deb {UBUNTU_MIRROR} {UBUNTU_VERSION}-updates main restricted universe multiverse
deb {UBUNTU_MIRROR} {UBUNTU_VERSION}-backports main restricted universe multiverse
deb {UBUNTU_MIRROR} {UBUNTU_VERSION}-security main restricted universe multiverse"""

    setup_commands = [
        f"echo {shlex.quote(sources)} > /etc/apt/sources.list",
        "rm -f /etc/apt/sources.list.d/* || true",
        "echo 'DEBIAN_FRONTEND=noninteractive' >> /etc/environment",
        "DEBIAN_FRONTEND=noninteractive apt-get update -y",
        "DEBIAN_FRONTEND=noninteractive apt-get upgrade -y -o Dpkg::Options::=--force-confdef",
        "DEBIAN_FRONTEND=noninteractive apt-get autoremove -y && apt-get clean -y"
    ]

    for i, cmd in enumerate(setup_commands, 1):
        print(f"[{i}/{len(setup_commands)}] Running setup step...")
        exit_code, out, err = exec_cmd(container, cmd)
        if exit_code != 0:
            print(f"❌ Setup failed: {err}")
            container.stop()
            raise RuntimeError(f"Container setup failed: {err}")

    print("✅ Container setup complete")


def handle_cd(container, command, current_path):
    """Handle directory changes and return new path"""
    target = command[3:].strip()

    # Security check for command injection
    dangerous_chars = [';', '&&', '||', '|', '`', '$(', '&', '<', '>']
    if any(char in target for char in dangerous_chars):
        print(f"❌ Invalid cd command: {command}")
        return current_path

    cd_cmd = f"cd {shlex.quote(current_path)} && cd {shlex.quote(target)} && pwd -P"
    exit_code, new_path, err = exec_cmd(container, cd_cmd, "/")

    if exit_code == 0 and new_path:
        print(f"📁 Changed to: {new_path}")
        return new_path
    else:
        print(f"❌ CD failed: {err}")
        return current_path


def execute_step(container, cmd, current_path):
    """Execute a single step and return result info"""
    if cmd.startswith("cd "):
        new_path = handle_cd(container, cmd, current_path)
        return {
            "success": True,
            "new_path": new_path,
            "result": f"Changed directory to: {new_path}",
            "output": "",
            "error": ""
        }
    else:
        print(f"⚙️ Running: {cmd}")
        exit_code, out, err = exec_cmd(container, cmd, current_path)

        if exit_code == 0:
            if out: print(f"🖥️ Output:\n{out}")
            if err: print(f"⚠️ Warnings:\n{err}")
            if not out and not err: print("✅ OK")

            return {
                "success": True,
                "new_path": current_path,
                "result": f"Executed '{cmd}' successfully",
                "output": out,
                "error": err
            }
        else:
            error_msg = err or out
            print(f"❌ Failed (exit {exit_code}): {error_msg}")
            return {
                "success": False,
                "new_path": current_path,
                "result": f"Failed '{cmd}' - Error: {error_msg}",
                "output": out,
                "error": error_msg,
                "exit_code": exit_code,
                "failed_command": cmd
            }


def execute_plan_with_recovery(container, steps, user_input, current_path, step_results, messages):
    """Execute plan with automatic error recovery"""

    for step_index, step in enumerate(steps, 1):
        print(f"\n➡️ [{step_index}/{len(steps)}] {step}")

        # Generate command with full context
        print("🤔 Generating command...")
        cmd = linux_command(
            original_request=user_input,
            current_step=step,
            step_number=step_index,
            total_steps=len(steps),
            all_steps=steps,
            previous_results=step_results,
            current_path=current_path,
            user_login=USER_LOGIN,
            current_time=get_current_time()
        )

        if not cmd:
            print("❌ No command generated")
            return False, current_path

        # Execute the command
        execution_result = execute_step(container, cmd, current_path)
        current_path = execution_result["new_path"]

        if execution_result["success"]:
            # Track successful results
            step_results.append({
                "step": step,
                "command": cmd,
                "result": execution_result["result"],
                "output": execution_result["output"]
            })
            messages.append({"role": "assistant", "content": execution_result["result"]})
        else:
            # Handle failure with recovery
            print("\n🔧 Attempting error recovery...")

            recovery_success = attempt_error_recovery(
                container, execution_result, user_input, step,
                current_path, step_results, messages
            )

            if recovery_success:
                # Retry the original step after recovery
                print(f"\n🔄 Retrying original step: {step}")
                retry_result = execute_step(container, cmd, current_path)
                current_path = retry_result["new_path"]

                if retry_result["success"]:
                    step_results.append({
                        "step": step,
                        "command": cmd,
                        "result": retry_result["result"],
                        "output": retry_result["output"]
                    })
                    messages.append({"role": "assistant", "content": retry_result["result"]})
                    print("✅ Recovery successful, continuing with plan")
                else:
                    print("❌ Recovery failed, stopping execution")
                    return False, current_path
            else:
                print("❌ Could not recover from error, stopping execution")
                return False, current_path

    return True, current_path


def attempt_error_recovery(container, execution_result, user_input, failed_step, current_path, step_results, messages):
    """Attempt to recover from execution error"""

    error_info = {
        "failed_command": execution_result["failed_command"],
        "error_message": execution_result["error"],
        "exit_code": execution_result["exit_code"],
        "failed_step": failed_step,
        "current_path": current_path
    }

    print("🤔 Analyzing error and creating recovery plan...")
    recovery_plan = create_error_recovery_plan(
        error_info=error_info,
        original_request=user_input,
        step_results=step_results,
        current_time=get_current_time()
    )

    if not recovery_plan or not recovery_plan.get("recovery_steps"):
        print("❌ No recovery plan could be generated")
        return False

    recovery_steps = recovery_plan["recovery_steps"]
    print(f"\n🛠️ Recovery Plan ({len(recovery_steps)} steps):")
    for i, step in enumerate(recovery_steps, 1):
        print(f"  [R{i}] {step}")

    # Execute recovery steps
    for step_index, recovery_step in enumerate(recovery_steps, 1):
        print(f"\n🔧 [R{step_index}/{len(recovery_steps)}] {recovery_step}")

        print("🤔 Generating recovery command...")
        recovery_cmd = linux_command(
            original_request=f"Recovery: {recovery_step}",
            current_step=recovery_step,
            step_number=step_index,
            total_steps=len(recovery_steps),
            all_steps=recovery_steps,
            previous_results=step_results,
            current_path=current_path,
            user_login=USER_LOGIN,
            current_time=get_current_time()
        )

        if not recovery_cmd:
            print("❌ No recovery command generated")
            return False

        # Execute recovery command
        recovery_result = execute_step(container, recovery_cmd, current_path)
        current_path = recovery_result["new_path"]

        if not recovery_result["success"]:
            print(f"❌ Recovery step failed: {recovery_result['error']}")
            return False

        # Add recovery step to results
        step_results.append({
            "step": f"Recovery: {recovery_step}",
            "command": recovery_cmd,
            "result": recovery_result["result"],
            "output": recovery_result["output"]
        })
        messages.append({"role": "assistant", "content": f"Recovery: {recovery_result['result']}"})

    print("✅ Recovery plan completed successfully")
    return True


def initialize_docker():
    """Initialize Docker client and container"""
    try:
        client = docker.from_env()
        client.ping()
        print("✅ Docker connected")

        try:
            client.images.get(DOCKER_IMAGE)
            print(f"✅ Image {DOCKER_IMAGE} found locally")
        except docker.errors.ImageNotFound:
            print(f"📥 Pulling {DOCKER_IMAGE}...")
            client.images.pull(DOCKER_IMAGE)
            print(f"✅ Image {DOCKER_IMAGE} pulled successfully")

        container = client.containers.run(
            DOCKER_IMAGE, "sleep infinity", tty=True, detach=True, remove=True
        )
        print(f"✅ Container {container.name} started")

        setup_container(container)
        return container

    except Exception as e:
        print(f"❌ Docker initialization error: {e}")
        raise


def main():
    """Main execution loop"""
    container = None

    try:
        container = initialize_docker()
        current_path = "/"
        messages = []

        print(f"\n🎉 Ready. Current directory: {current_path}")
        print(f"📅 Current time: {get_current_time()} UTC")
        print(f"👤 User: {USER_LOGIN}")

        while True:
            user_input = input(f"\n[{container.name}:{current_path}]$ ")
            if user_input.lower() in ["exit", "quit", "q"]:
                break

            if not user_input.strip():
                continue

            messages.append({"role": "user", "content": user_input})

            # Get AI plan
            print("🤔 Planning...")
            plan = linux_step_planning(user_input, current_path, messages)

            if not plan or not plan.get("linuxcommand"):
                print("❌ No plan generated")
                messages.pop()
                continue

            steps = plan["linuxcommand"]
            print(f"\n📋 Plan ({len(steps)} steps):")
            for i, step in enumerate(steps, 1):
                print(f"  [{i}] {step}")

            # Execute plan with automatic recovery
            step_results = []
            success, current_path = execute_plan_with_recovery(
                container, steps, user_input, current_path, step_results, messages
            )

            print(
                f"\n{'✅ All steps completed successfully' if success else '⚠️ Execution failed and could not be recovered'}")

    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
    finally:
        if container:
            print(f"\n🛑 Stopping container...")
            try:
                container.stop()
                print("🗑️ Container stopped")
            except Exception as e:
                print(f"⚠️ Error stopping container: {e}")
        print("👋 Goodbye")


if __name__ == "__main__":
    main()