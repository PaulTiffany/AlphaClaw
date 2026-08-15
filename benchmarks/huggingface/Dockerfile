FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY app.py analyze.py LICENSE README.md ./

EXPOSE 7860
CMD ["python", "app.py"]
