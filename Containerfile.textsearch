FROM registry.access.redhat.com/ubi9/ubi:latest

WORKDIR /app

# Install minimal dependencies
RUN dnf update -y && \
    dnf install -y python3 python3-pip && \
    dnf clean all

# Create user
RUN useradd -r -u 1001 -g 0 -m -d /app -s /bin/bash stigrag && \
    chown -R stigrag:0 /app && \
    chmod -R g=u /app

# Copy requirements and install
COPY --chown=stigrag:0 requirements-textsearch.txt /app/requirements.txt
RUN python3 -m pip install --no-cache-dir --ignore-installed -r requirements.txt

# Copy application
COPY --chown=stigrag:0 rhel_stig_rag.py /app/

# Create directories
RUN mkdir -p /app/stig_data /app/templates && \
    chown -R stigrag:0 /app

USER stigrag

ENV PYTHONUNBUFFERED=1 PORT=8000

EXPOSE 8000

CMD ["python3", "/app/rhel_stig_rag.py"]
