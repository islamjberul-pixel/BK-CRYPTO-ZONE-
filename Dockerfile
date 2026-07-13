FROM python:3.11.9-slim

WORKDIR /app

# pip update করো যাতে Library পায়
RUN pip install --upgrade pip

# requirements install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# বাকি সব ফাইল Copy
COPY . .

# Bot Run
CMD ["python", "main.py"]
