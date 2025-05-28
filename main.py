import docker
from Ollama_model import control_linux, linux_command
import shlex
client = docker.from_env()
container = client.containers.run("ubuntu", command="sleep 600", tty=True, detach=True)

current_path = "/"

while True:
    #changer usercommand par la fonction control_linux
    demande_ia = input("entré se que vous voulez a l'ia ")
    usercommand = linux_command(demande_ia)
    print("commande utiliser :", usercommand)

    if usercommand.startswith("cd "):
        new_path = usercommand[3:].strip()
        # Vérifie si le dossier existe
        result = container.exec_run(f"bash -c 'cd {current_path} && cd {new_path} && pwd'", demux=True)
        out, err = result.output
        if result.exit_code == 0:
            current_path = out.decode().strip()
        else:
            print("Erreur :", err.decode() if err else "Dossier invalide")
    else:
        # Exécute dans le chemin courant
        raw_command = f"cd {current_path} && {usercommand}"
        safe_command = shlex.quote(raw_command)
        result = container.exec_run(f"bash -c {safe_command}")
        print("docker : ", result.output.decode())


container.stop()
container.remove()