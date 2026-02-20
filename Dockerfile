FROM python:3.11-slim

WORKDIR /code

# Instalar dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código e estáticos
COPY ./backend ./backend
COPY ./frontend ./frontend

# Variáveis de ambiente
ENV PYTHONPATH=/code
ENV PYTHONUNBUFFERED=1

# Porta exposta
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

