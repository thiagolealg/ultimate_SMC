# SMC Realtime API - Dockerfile
# ==============================

FROM python:3.11-slim

# Metadados
LABEL maintainer="SMC Trading"
LABEL version="1.0.0"
LABEL description="Smart Money Concepts Realtime Trading API"

# Variáveis de ambiente
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Diretório de trabalho
WORKDIR /app

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements e instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código da aplicação
COPY main.py .
COPY smc_engine.py .
COPY settings.py .
COPY alerts.py .

# Criar diretórios necessários
RUN mkdir -p /app/data /app/logs

# Expor porta
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Comando de inicialização
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
