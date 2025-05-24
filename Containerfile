FROM registry.access.redhat.com/ubi9/ubi:latest

WORKDIR /app

RUN dnf update -y && \
    dnf install -y python3 python3-pip curl && \
    dnf clean all

RUN useradd -r -u 1001 -g 0 -m -d /app -s /bin/bash stigrag && \
    chown -R stigrag:0 /app && \
    chmod -R g=u /app

COPY --chown=stigrag:0 requirements.txt /app/
RUN python3 -m pip install --no-cache-dir --ignore-installed -r requirements.txt

COPY --chown=stigrag:0 rhel_stig_rag.py /app/

# Create stig_data directory with proper permissions
RUN mkdir -p /app/stig_data /app/templates && \
    chown -R stigrag:0 /app && \
    chmod -R 777 /app/stig_data

USER stigrag

ENV PYTHONUNBUFFERED=1 PORT=8000

EXPOSE 8000

CMD ["python3", "/app/rhel_stig_rag.py"]
