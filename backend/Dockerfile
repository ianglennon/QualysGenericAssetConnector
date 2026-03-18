FROM python:3.12-slim
WORKDIR /app

# Install qualys_client package (changes rarely -> good cache layer)
COPY QualysAPIConnectionManager/ /tmp/qualys_pkg/
RUN pip install --no-cache-dir /tmp/qualys_pkg/ \
    && rm -rf /tmp/qualys_pkg/

# Install backend dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/ .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
