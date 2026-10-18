FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

# cpu only torch for now, swap to cuda index later when we set up gpu training
RUN pip install --no-cache-dir --default-timeout=120 --retries 5 \
    torch torchvision --index-url https://download.pytorch.org/whl/cpu

# ultralytics drags in the GUI opencv-python, which clashes with headless -- swap it back out
RUN pip install --no-cache-dir --default-timeout=120 --retries 5 -r requirements.txt && \
    pip uninstall -y opencv-python opencv-python-headless && \
    pip install --no-cache-dir opencv-python-headless==5.0.0.93

# eclipse-sumo ships the sumo binaries inside the python package
ENV SUMO_HOME=/usr/local/lib/python3.12/site-packages/sumo

COPY . .

# data/ (weights, sample clips) is dockerignored, so the default command is the
# self-contained SUMO comparison rather than the detection check
CMD ["sh", "-c", "python sumo/run_experiment.py --mode fixed && python sumo/run_experiment.py --mode adaptive"]
