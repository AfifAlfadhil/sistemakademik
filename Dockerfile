# Dockerfile untuk deployment Railway
FROM python:3.11-slim

# Install dependency system (Tesseract OCR, bahasa Indonesia, dan library pendukung)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-ind \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Salin requirements.txt dan install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Salin seluruh kode aplikasi ke dalam container
COPY . .

# Expose port yang digunakan oleh uvicorn
EXPOSE 8000

# Jalankan uvicorn server
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
