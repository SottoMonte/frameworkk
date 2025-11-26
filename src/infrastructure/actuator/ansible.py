import subprocess
import datetime
import importlib
import os
import tempfile
import ansible_runner

modules = {'flow': 'framework.service.flow',}


class adapter:

    def __init__(self, **constants):
        self.config = constants.get('config', {})
        self.capabilities = {'latency': 'high', 'speed': 'low'}

    @flow.asynchronous(outputs='transaction')
    async def load(self, *services, **constants):
        return await self.actuate(**constants | {'method': 'PUT'})

    async def actuate(self, **constants):
        api_key = "your-supabase-api-key"
        endpoint = "https://your-api-endpoint.com/your-function"

        playbook_content = f"""---
- name: Configura cron job per eseguire funzione solo di sabato
  hosts: localhost
  tasks:
    - name: Aggiungi cron job per eseguire la funzione tramite chiamata HTTP
      ansible.builtin.cron:
        name: "Esegui funzione ogni sabato"
        minute: "0"
        hour: "0"
        day: "*"
        month: "*"
        weekday: "6"
        job: >-
          curl -X POST https://
          -H "Authorization: Bearer "
          -H "Content-Type: application/json"
"""
        

        # Usa una directory temporanea in RAM (tipicamente /tmp)
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = os.path.join(temp_dir, 'project')
            inventory_dir = os.path.join(temp_dir, 'inventory')
            os.makedirs(project_dir, exist_ok=True)
            os.makedirs(inventory_dir, exist_ok=True)

            # Scrive il playbook
            playbook_path = os.path.join(project_dir, 'playbook.yml')
            with open(playbook_path, 'w') as f:
                f.write(playbook_content)

            # Scrive l'inventory localhost
            inventory_path = os.path.join(inventory_dir, 'hosts')
            with open(inventory_path, 'w') as f:
                f.write('[local]\nlocalhost ansible_connection=local\n')

            # Esegue Ansible Runner
            r = ansible_runner.run(
                private_data_dir=temp_dir,
                playbook='playbook.yml'
            )

            # Verifica risultato
            if r.status == 'successful':
                print("✅ Cron job creato con successo.")
            else:
                print("❌ Errore nella creazione del cron job.")
                #print(r.stdout.read() if r.stdout else "Nessun output")

    @flow.asynchronous(outputs='transaction')
    async def activate(self, *services, **constants):
        return await self.actuate(**constants | {'method': 'PUT'})

    @flow.asynchronous(outputs='transaction')
    async def deactivate(self, *services, **constants):
        pass

    @flow.asynchronous(outputs='transaction')
    async def calibrate(self, *services, **constants):
        pass

    @flow.asynchronous(outputs='transaction')
    async def status(self, *services, **constants):
        pass

    @flow.asynchronous(outputs='transaction')
    async def reset(self, *services, **constants):
        pass


'''class adapter(message.port):

    def __init__(self, **constants):
        self.config = constants['config']
        self.connection = self.loader()
        self.processable = dict()

    async def act(self, playbook_path, inventory_file=None, extra_vars=None):
        """
        Metodo per eseguire un playbook Ansible utilizzando subprocess.

        :param playbook_path: Il percorso del playbook Ansible.
        :param inventory_file: (Opzionale) Il file di inventario per Ansible.
        :param extra_vars: (Opzionale) Variabili extra da passare al playbook.
        :return: Il risultato dell'esecuzione del playbook.
        """
        command = ['ansible-playbook', playbook_path]

        if inventory_file:
            command.extend(['-i', inventory_file])

        if extra_vars:
            for key, value in extra_vars.items():
                command.extend(['--extra-vars', f"{key}={value}"])

        try:
            # Esegui il playbook utilizzando subprocess
            result = subprocess.run(command, capture_output=True, text=True, check=True, shell=True)
            return result.stdout
        except subprocess.CalledProcessError as e:
            # Gestisci errori in caso di fallimento dell'esecuzione
            return f"Errore durante l'esecuzione del playbook: {e.stderr}"'''