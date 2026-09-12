FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY otlab_sim ./otlab_sim
COPY examples ./examples

EXPOSE 5020/tcp 4840/tcp

ENTRYPOINT ["python", "-m", "otlab_sim", "run"]
CMD ["--config", "examples/pump_station.yaml"]
