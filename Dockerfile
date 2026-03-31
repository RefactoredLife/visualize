# -----------------------------
# STAGE 1: Builder
# -----------------------------
FROM python:3.12.9-slim AS builder

# Set working directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    libffi-dev \
    libssl-dev \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    libjpeg-dev \
    libblas-dev \
    liblapack-dev \
    libatlas-base-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# -----------------------------
# STAGE 2: Runtime
# -----------------------------
FROM python:3.12.9-slim AS runtime

# Install only runtime deps
RUN apt-get update && apt-get install -y \
    openjdk-17-jre-headless \
    libxml2 \
    libxslt1.1 \
    libjpeg62-turbo \
    zlib1g \
    libffi-dev \
    libssl3 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set JAVA_HOME
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64

# Set working directory
WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12 /usr/local/lib/python3.12
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /usr/local/include /usr/local/include
COPY --from=builder /usr/local/share /usr/local/share

# Copy application code
COPY . /app

RUN mkdir -p /finance/processed && chmod -R 777 /finance/processed

# Expose port
EXPOSE 8501

# Run Streamlit
#ENTRYPOINT ["streamlit", "run"]
#CMD ["app/visualize.py", "--server.port=8501", "--server.address=0.0.0.0"]
CMD ["python", "-m", "streamlit", "run", "app/visualize.py", "--server.port=8501", "--server.address=0.0.0.0"]

# -----------------------------
# STAGE 3: Debugger
# -----------------------------
FROM runtime AS debugger

# Install debugpy and debugging tools
RUN pip install --no-cache-dir debugpy \
    && apt-get update && apt-get install -y \
       bash \
       curl \
       iputils-ping \
       vim \
       net-tools \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set JAVA_HOME
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64

# Set working directory
WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12 /usr/local/lib/python3.12
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /usr/local/include /usr/local/include
COPY --from=builder /usr/local/share /usr/local/share

# Copy application code
COPY . /app

RUN mkdir -p /finance/processed && chmod -R 777 /finance/processed

# Expose debug port
EXPOSE 5678

# Optional: wait for debugger to attach
CMD ["python", "-m", "debugpy", "--listen", "0.0.0.0:5678", "--wait-for-client", "-m", "streamlit", "run", "app/visualize.py", "--server.port=8501", "--server.address=0.0.0.0"]