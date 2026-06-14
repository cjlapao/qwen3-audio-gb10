FROM python:3.12-slim

RUN pip install --no-cache-dir \
    'gradio>=5.0,<6.0' \
    'requests>=2.31' \
    'soundfile>=0.12' \
    'numpy>=1.26,<3'

WORKDIR /app
COPY app.py /app/app.py

EXPOSE 7860
ENV PYTHONUNBUFFERED=1

CMD ["python", "app.py"]
