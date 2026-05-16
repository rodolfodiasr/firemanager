FROM python:3.12-slim

# Criar usuário não-root para segurança
RUN useradd -m -u 1000 fmedge

WORKDIR /app

# Instalar dependências primeiro (cache layer)
COPY edge_agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código do edge agent
COPY edge_agent/ ./edge_agent/

# Trocar para usuário não-root
USER fmedge

ENTRYPOINT ["python", "-m", "edge_agent.main"]
