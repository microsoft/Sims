# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Install necessary system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev \
    gdal-bin \
    git \
    wget \
    unzip \
    curl \
    ca-certificates \
    gnupg \
    lsb-release \
    && rm -rf /var/lib/apt/lists/*

# Install Miniforge (which includes mamba)
RUN curl -L --retry 5 --retry-delay 5 --retry-max-time 60 -O https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh && \
    chmod +x Miniforge3-Linux-x86_64.sh && \
    ./Miniforge3-Linux-x86_64.sh -b && \
    rm Miniforge3-Linux-x86_64.sh

# Initialize conda and install mamba
ENV PATH="/root/miniforge3/bin:$PATH"
RUN conda init bash && conda install mamba -n base -c conda-forge

# Create the environment and install GDAL
RUN mamba create -n sims python=3.12.3 && \
    conda run -n sims mamba install -c conda-forge gdal

# Install gcloud (Google Cloud SDK)
RUN echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | tee -a /etc/apt/sources.list.d/google-cloud-sdk.list && \
    curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key --keyring /usr/share/keyrings/cloud.google.gpg add - && \
    apt-get update -y && apt-get install google-cloud-cli -y

# Copy the project files into the container
COPY . /app

# Install Python dependencies from requirements.txt
RUN conda run -n sims pip install -r requirements.txt

# Install the current package (region_similarity) in editable mode
RUN conda run -n sims pip install -e .

# Activate the conda environment in every new shell
RUN echo "source activate sims" >> ~/.bashrc
SHELL ["/bin/bash", "--login", "-c"]

# Expose the port for the app
EXPOSE 8080

# Run gcloud init before the solara app
CMD ["bash", "-c", "source activate sims && gcloud init && solara run scripts/app.py --production --host 0.0.0.0 --port 8080"]
