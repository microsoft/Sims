# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Set environment variables to reduce Python buffering and ensure UTF-8 encoding
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

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
    dos2unix \
    && rm -rf /var/lib/apt/lists/*

# Install Miniforge with architecture detection
RUN if [ "$(uname -m)" = "x86_64" ]; then \
        curl -L --retry 5 --retry-delay 5 --retry-max-time 60 -o miniforge.sh https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh; \
    elif [ "$(uname -m)" = "aarch64" ]; then \
        curl -L --retry 5 --retry-delay 5 --retry-max-time 60 -o miniforge.sh https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-aarch64.sh; \
    else \
        echo "Unsupported architecture: $(uname -m)" && exit 1; \
    fi && \
    chmod +x miniforge.sh && \
    ./miniforge.sh -b -p /opt/conda && \
    rm miniforge.sh

# Add conda to path
ENV PATH="/opt/conda/bin:$PATH"

# Initialize conda and install mamba
RUN conda init bash && \
    conda install -n base -c conda-forge mamba -y

# Create the environment and install GDAL
RUN mamba create -n sims python=3.12.3 -y && \
    mamba install -n sims -c conda-forge gdal -y

# Install gcloud (Google Cloud SDK)
RUN echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | tee -a /etc/apt/sources.list.d/google-cloud-sdk.list && \
    curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key --keyring /usr/share/keyrings/cloud.google.gpg add - && \
    apt-get update -y && \
    apt-get install google-cloud-cli -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt /app/
RUN conda run -n sims pip install -r requirements.txt

# Copy the rest of the project files
COPY . /app/

# Install the current package
RUN conda run -n sims pip install -e .

# Create a non-root user
RUN useradd -m -s /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# Activate the conda environment
SHELL ["/bin/bash", "--login", "-c"]
RUN echo "conda activate sims" >> ~/.bashrc

# Setup a healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/ || exit 1

# Expose the port for the app
EXPOSE 8080

# Create entrypoint script
RUN echo '#!/bin/bash' > /app/entrypoint.sh && \
    echo 'source /opt/conda/etc/profile.d/conda.sh' >> /app/entrypoint.sh && \
    echo 'conda activate sims' >> /app/entrypoint.sh && \
    echo '' >> /app/entrypoint.sh && \
    echo '# If GOOGLE_CREDENTIALS environment variable exists, create a credentials file' >> /app/entrypoint.sh && \
    echo 'if [ ! -z "$GOOGLE_CREDENTIALS" ]; then' >> /app/entrypoint.sh && \
    echo '    echo "$GOOGLE_CREDENTIALS" | base64 -d > /app/credentials.json' >> /app/entrypoint.sh && \
    echo '    export GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json' >> /app/entrypoint.sh && \
    echo 'fi' >> /app/entrypoint.sh && \
    echo '' >> /app/entrypoint.sh && \
    echo '# Run the application' >> /app/entrypoint.sh && \
    echo 'exec solara run scripts/app.py --production --host 0.0.0.0 --port 8080' >> /app/entrypoint.sh && \
    chmod +x /app/entrypoint.sh && \
    dos2unix /app/entrypoint.sh

# Set the entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]