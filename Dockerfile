FROM nvcr.io/nvidia/pytorch@sha256:2140e699b3beaf7f96a0081fd9c9406bc3832b435cdb60dfa2d261f7d2f34a1c

# Keep NVIDIA's GB10-enabled torch/torchvision; upstream torch==2.10.0 is different.
COPY requirements.txt /recipe/requirements.txt
RUN python -m pip install --no-cache-dir -r /recipe/requirements.txt
COPY scripts /recipe/scripts
ENV PYTHONUNBUFFERED=1 HF_HOME=/tmp/huggingface
WORKDIR /recipe
CMD ["python", "/recipe/scripts/serve.py"]
