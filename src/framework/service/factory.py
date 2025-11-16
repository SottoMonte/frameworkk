import re

class repository():
    def __init__(self, **constants):
        self.location = constants.get('location',{})
        self.mapper = constants.get('mapper',{})
        self.values = constants.get('values',{})
        self.payloads = constants.get('payloads',{})
        self.functions = constants.get('functions',{})
        self.schema = constants.get('model')

    def can_format(self,template, data):
            """
            Verifica se una singola stringa `template` può essere formattata utilizzando le chiavi di un dizionario `data`.
            """
            try:
                placeholders = re.findall(r'\{([\w\.]+)\}', template)
                gg = []
                for key in placeholders:
                    a = language.get(data,key)
                    print('=================================',a,key)
                    if a:
                        gg.append(True)
                    else:
                         gg.append(False)

                # Controlla che tutti i placeholder siano presenti nelle chiavi del dizionario
                #return all(key in data for key in placeholders)
                #print(f"Template: {template}, all, Stato: {all(gg)}",data)
                return (all(gg),len(placeholders))
            except Exception as e:
                print(f"Errore durante la verifica: {e}")
                return False
            
    def do_format(self,template, data):
            """
            Verifica se una singola stringa `template` può essere formattata utilizzando le chiavi di un dizionario `data`.
            """
            try:
                #placeholders = re.findall(r'\{(\w+)\}', template)
                placeholders = re.findall(r'\{([\w\.]+)\}', template)
                print(f"Template: {template}, Placeholders: {placeholders}")
                for key in placeholders:
                    print('Key',key)
                    a = language.get(key,data)
                    print(f"Key: {key}, Value: {a}")
                    if a:
                        template = template.replace(f'{key}',str(a))
                print(f"Template: {template},",data)
                return template
            except Exception as e:
                print(f"Errore durante la verifica: {e}")
                return False
            
    def find_first_formattable_template(self, templates, data):
        """
        Trova il template con il più alto numero di placeholder formattabili e con True.

        :param templates: Lista di stringhe che contengono i placeholder.
        :param data: Dizionario con le chiavi e i valori per il formato.
        :return: Il template con il massimo numero di placeholder formattabili o None se nessuno è valido.
        """
        best_template = None
        max_placeholders = 0
        #print(f"Templates: {templates}")
        for template in templates:
            can_format_result, num_placeholders = self.can_format(template, data)
            print(f"Template: {template}, Stato: {can_format_result}, Numero di placeholder: {num_placeholders}",data)
            if can_format_result and num_placeholders >= max_placeholders:
                best_template = template
                max_placeholders = num_placeholders
        #print(f"Template: {best_template}, Stato: {max_placeholders}",data)
        return best_template

    async def results(self, **data):
        print("RESULTS",data)
        try:
            # Recupera il profilo e i risultati dalla transazione
            profile = data.get('profile', '')
            transaction = data.get('transaction', {})
            results = transaction.get('result', [])

            # Verifica che i risultati siano una lista
            if not isinstance(results, list):
                raise ValueError("Il campo 'result' deve essere una lista.")

            # Elabora i risultati
            r = []
            for item in results:
                if isinstance(item, dict):
                    try:
                        #(data_dict, mapper, values, input, output)
                        '''translated_item = language.transform(
                            item, self.mapper, self.values, self.schema, self.schema
                        )
                        r.append(translated_item)'''
                        r.append(item)
                    except Exception as e:
                        print(f"Errore durante la traduzione dell'elemento {item}: {e}")
                        continue  # Salta l'elemento corrente in caso di errore

            # Aggiorna i risultati nella transazione
            transaction['result'] = r
            data['transaction'] = transaction

            return transaction

        except KeyError as e:
            print(f"Chiave mancante nei dati: {e}")
            raise
        except Exception as e:
            print(f"Errore generico in 'results': {e}")
            raise
    
    async def parameters(self, ops_crud, profile, **inputs) -> object:
        try:
            # Carica lo schema se non è già stato caricato
            '''if not self.schema:
                self.schema = await language.load_module(language, path=f'application.model.{self.model}')
                self.schema = getattr(self.schema, self.model, None)
                if not self.schema:
                    raise ValueError(f"Schema non trovato per il modello: {self.model}")'''
            print(self.schema)
            #self.fields = [field['name'] for field in self.schema if 'name' in field]

            # Ottieni il payload iniziale
            payload = inputs.get('payload', {})
            para = {}
            print(self.schema)
            # Traduzione del payload
            #translated_payload = language.translation(payload, self.schema.keys(), self.mapper, self.values, 'MODEL', profile)
            #print("Translated payload:", translated_payload,payload)

            # Applica la funzione payload specifica, se esiste
            func_payload = self.payloads.get(ops_crud, None)
            if func_payload:
                payload = await func_payload(**inputs)

            func_payload = self.functions.get(ops_crud, None)
            if func_payload:
                para = await func_payload(**inputs)

            # Combina inputs e payload
            combined_parameters = {**inputs, **payload}
            print("Combined parameters:", combined_parameters)

            # Trova il template formattabile
            templates = self.location.get(profile, [''])
            template = self.find_first_formattable_template(templates, combined_parameters)
            if not template:
                raise ValueError(f"Nessun template formattabile trovato per il profilo: {profile}")
            print("Selected template:", template)

            # Format il percorso
            #path = self.do_format(template, combined_parameters)

            path = await language.format(template,**combined_parameters)

            print("BOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO",path)
            
            
            # Restituisci i risultati
            return para|{**inputs, 'location': path, 'provider': profile, 'payload': payload}

        except Exception as e:
            print(f"Errore in parameters: {e}")
            raise