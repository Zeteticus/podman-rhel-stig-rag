podman run --rm -d \
  --replace \
  --device /dev/nvidia0 \
  --memory 8g \
  --security-opt=label=disable \
  -v ollama:/root/.ollama \
  -p 11434:11434 \
  --name ollama \
  ollama/ollama
