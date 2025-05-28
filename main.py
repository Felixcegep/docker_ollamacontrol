import docker
from Ollama_model import control_linux, linux_command
import shlex
client = docker.from_env()
container = client.containers.run("ubuntu", command="sleep 600", tty=True, detach=True)

current_path = "/"
historique = ""
messages = []
#    {"role": "system", "content": ""},
#   {"role": "user", "content": "Can you create a folder?"},
#    {"role": "assistant", "content": '{"linuxcommand": "mkdir myfolder"}'},
#    {"role": "user", "content": "Can you go in the folder you just created ?"},
#
#user       demande_ia
#system     usercommand
while True:
    #changer usercommand par la fonction control_linux
    demande_ia = input("Décrivez l'action que vous souhaitez effectuer dans Ubuntu : ")
    messages.append({"role": "user", "content": demande_ia})
    # CONTEXT SERVIRAIT A AIDER LE LLM
    messages.append({"role": "CURRENT PATH", "content": current_path})
    usercommand = linux_command(str(messages))
    print("commande utiliser :", usercommand)
    messages.append({"role": "System", "content": usercommand})



        # Exécute dans le chemin courant
    raw_command = f"cd {current_path} && {usercommand}"
    safe_command = shlex.quote(raw_command)
    result = container.exec_run(f"bash -c {safe_command}")
    print("docker : ", result.output.decode())


container.stop()
container.remove()