# Documentazione del Framework

Benvenuto nella documentazione tecnica. Questa guida è strutturata per rispecchiare l'architettura del codice sorgente.

## Indice

### 1. [Application Layer](application/README.md) (`src/application`)
Il cuore della logica di business.
*   [Actions](application/action.md): Come scrivere casi d'uso.
*   [Models](application/model.md): Definizione dei dati.
*   [Repositories](application/repository.md): Interfacce di accesso ai dati.
*   [Policies](application/policy.md): Regole di business.

### 2. [Framework Layer](framework/README.md) (`src/framework`)
Il sistema di orchestrazione.
*   [Managers](framework/manager.md): Executor, Actuator, ecc.
*   [Ports](framework/port.md): Contratti per l'infrastruttura.
*   [Services](framework/service.md): Servizi di dominio condivisi.

### 3. [Infrastructure Layer](infrastructure/README.md) (`src/infrastructure`)
Implementazioni concrete e dettagli tecnici.
*   [Persistence](infrastructure/persistence.md): Database (SQL, Redis, ecc.).
*   [Presentation](infrastructure/presentation.md): API Web, CLI.
*   [Authorization](infrastructure/authorization.md): Sicurezza e permessi.

## Altre Risorse
*   [Panoramica Generale](overview.md)
*   [Guida Introduttiva](getting_started.md)
*   [Architettura](architecture.md)
*   [Guide Pratiche](guides.md)
