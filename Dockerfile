# Stage 1: Build
FROM python:3-alpine AS builder

ARG REPO_URL="https://github.com/ldmtecknoit-lab/e-commerce"

WORKDIR /app

# 1. COPIA SOLO I FILE DI DIPENDENZA (Massimizza il caching)
COPY pyproject.toml .
COPY requirements.txt .

# --- NUOVE ISTRUZIONI PER LA CACHE DELLE DIPENDENZE ---
# NUOVO PASSO 5: Crea VENV e aggiorna pip (dovrebbe andare in cache facilmente)
RUN mkdir -p /venv && \
    pip install --no-cache-dir --upgrade pip

# NUOVO PASSO 6: Installa le dipendenze (l'istruzione lunga)
ENV VIRTUAL_ENV=/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
RUN pip install --target /venv --no-cache-dir -r requirements.txt
# --- FINE NUOVE ISTRUZIONI ---


# 🚩 PUNTO DI INVALICAMENTO FORZATO (CACHE-BUSTER)
# Il resto rimane uguale, ma con il numero di passo aggiornato.
# PASSO 7 (Prima era il 6)
ARG BUILD_TIMESTAMP=

RUN echo "Forzo l'invalicamento della cache per il codice con il timestamp: ${BUILD_TIMESTAMP}" \
    && apk add --no-cache git \
    && git clone ${REPO_URL} /tmp/repo

# 4. SPOSTA IL CODICE SORGENTE
RUN mkdir -p src/application && mv /tmp/repo/src/application/* src/application/

# Sposta il contenuto della cartella 'assets' in public/assets
RUN mkdir -p public/assets && cp -R /tmp/repo/assets/* public/assets/ 2>/dev/null || true

# Rimuovi git per mantenere l'immagine più leggera possibile.
RUN apk del git

# Stage 2: Runtime (Leggermente modificato per riflettere l'installazione senza venv)
FROM python:3-alpine AS runner

# Imposta le variabili d'ambiente per l'ambiente virtuale fittizio e la porta.
ENV VIRTUAL_ENV=/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
ENV PORT=8000



# Imposta la directory di lavoro.
WORKDIR /app

# Variabili d'Ambiente cruciali per Python
# Aggiunge la directory dove sono installate le dipendenze al PYTHONPATH
ENV PYTHONPATH=/venv
# Aggiunge i binari di Python (se non già presenti nel path)
ENV PATH="/venv/bin:$PATH"

# Copia l'ambiente virtuale (che ora è solo una directory con le librerie)
COPY --from=builder /venv /venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/pyproject.toml /app/
COPY --from=builder /app/public public

COPY public/main.py /app/public/main.py
COPY src /app/src

EXPOSE ${PORT}

# Comando per lanciare l'applicazione.
CMD ["python3", "public/main.py"]