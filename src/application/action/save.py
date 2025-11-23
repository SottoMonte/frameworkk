modules = {'flow': 'framework.service.flow'}

@flow.asynchronous(managers=('messenger', 'storekeeper', 'presenter', 'tester'))
async def save(messenger, storekeeper, presenter, tester, **constants):
    """
    Funzione asincrona per salvare un file dopo aver eseguito i test, se necessario.

    Args:
        messenger: Servizio di messaggistica per notifiche.
        storekeeper: Servizio di archiviazione per gestire i file.
        presenter: Servizio per ottenere i componenti dell'interfaccia.
        tester: Servizio per eseguire i test.
        **constants: Dizionario di parametri costanti.
    """
    identifier = constants.get('path', '')
    target = constants.get('target', '')
    field = constants.get('field', 'editor')
    location = constants.get('location', 'local')

    # Recupera i valori dal componente
    component = await presenter.component(name=target)
    value = component[field].getValue()
    test_value = component['block-test-'].getValue()

    # Se il file è un test, salvalo direttamente
    if identifier.endswith('.test.py'):
        await _save_file(messenger, storekeeper, identifier, value,location)
    else:
        # Esegui i test prima di salvare
        test_result = await tester.unittest(test_value)
        if test_result['state']:
            await _save_file(messenger, storekeeper, identifier, value,location)
        else:
            # Notifica gli errori dei test
            error_messages = "\n".join(
                [f"Errore nel test '{test}': {message}" for test, message in test_result['errors']] +
                [f"Fallimento nel test '{test}': {message}" for test, message in test_result['failures']]
            )
            await messenger.post(domain='error', message=error_messages)


async def _save_file(messenger, storekeeper, path, content,location):
    """
    Funzione di supporto per salvare un file e notificare il risultato.

    Args:
        messenger: Servizio di messaggistica per notifiche.
        storekeeper: Servizio di archiviazione per gestire i file.
        path: Percorso del file da salvare.
        content: Contenuto del file da salvare.
    """
    response = await storekeeper.change(repository='file', payload={'path': path, 'location':location,'content': content})
    if response.get('state', False):
        await messenger.post(domain='success', message=f"Salvato con successo file {path}")
    else:
        await messenger.post(domain='error', message=f"Errore durante il salvataggio del file {path}")