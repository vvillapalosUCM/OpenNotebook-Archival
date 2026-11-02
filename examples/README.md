# Docker Compose Examples

This folder contains different `docker-compose.yml` configurations for various use cases.

## 📋 Available Examples

### `docker-compose-full-local.yml` - 100% Local AI (No Cloud APIs) 🌟
**Use this if:** You want complete privacy with zero external API dependencies

**Features:**
- **Ollama**: Local LLM and embeddings (mistral, llama, etc.)
- **Speaches**: Local TTS (text-to-speech) and STT (speech-to-text)
- Everything runs on your machine - nothing sent to cloud
- Perfect for privacy, offline work, or air-gapped environments

**Setup:**
1. Copy to the repository root as `docker-compose.yml`
2. Copy `.env.example` to `.env` and replace every `CHANGE_ME` value with a long random string (the API refuses to start with template or weak values)
3. Run: `docker compose up -d --build`
4. Download models (see file comments for commands)
5. Configure all providers in UI (detailed instructions in file)

**Requirements:**
- Minimum: 8GB RAM, 20GB disk, 4 CPU cores
- Recommended: 16GB+ RAM, NVIDIA GPU (8GB+ VRAM), 50GB disk

**Documentation:**
- [Local TTS Guide](../docs/5-CONFIGURATION/local-tts.md)
- [Local STT Guide](../docs/5-CONFIGURATION/local-stt.md)

---

### `docker-compose-speaches.yml` - Local Speech Processing
**Use this if:** You want free TTS/STT but use cloud LLMs

**Features:**
- **Speaches**: Local text-to-speech and speech-to-text
- Use with cloud LLM providers (OpenAI, Anthropic, etc.)
- Great for podcast generation without TTS API costs
- Private audio processing

**Setup:**
1. Copy to the repository root as `docker-compose.yml`
2. Copy `.env.example` to `.env` and replace every `CHANGE_ME` value with a long random string (the API refuses to start with template or weak values)
3. Run: `docker compose up -d --build`
4. Download speech models (see file for commands)
5. Configure cloud LLM + local Speaches in UI

**Documentation:**
- [Local TTS Guide](../docs/5-CONFIGURATION/local-tts.md)
- [Local STT Guide](../docs/5-CONFIGURATION/local-stt.md)

---

### `docker-compose-ollama.yml` - Free Local AI with Ollama
**Use this if:** You want to run AI models locally without API costs

**Features:**
- Includes Ollama service for local AI models
- No external API keys needed (for LLM and embeddings)
- Full privacy - everything runs on your machine
- Great for testing or privacy-focused deployments

**Setup:**
1. Copy to the repository root as `docker-compose.yml`
2. Copy `.env.example` to `.env` and replace every `CHANGE_ME` value with a long random string (the API refuses to start with template or weak values)
3. Run: `docker compose up -d --build`
4. Pull a model: `docker compose exec ollama ollama pull mistral`
5. Configure in UI: Settings → API Keys → Add Ollama (URL: `http://ollama:11434`)

**Recommended models:**
- **LLM**: `mistral`, `llama3.1`, `qwen2.5`
- **Embeddings**: `nomic-embed-text`, `mxbai-embed-large`

---

### `docker-compose-single.yml` - Single Container (Deprecated)
**Use this if:** You need all services in one container (not recommended)

**⚠️ Deprecated:** We recommend using the standard multi-container setup (`docker-compose.yml` in root) for better reliability and easier troubleshooting.

**Features:**
- Single container includes SurrealDB, API, and Frontend
- Simpler for very constrained environments
- Less flexible for debugging and scaling

---

### `docker-compose-dev.yml` - Development Setup
**Use this if:** You're contributing to Open Notebook or developing custom features

**Features:**
- Hot-reload for code changes
- Separate backend and frontend services
- Build from source instead of using pre-built images
- Includes development tools and debugging

**Prerequisites:**
- Python 3.11+
- Node.js 18+
- uv (Python package manager)

**Setup:**
See [Development Guide](../docs/7-DEVELOPMENT/index.md)

---

## 🔄 How to Use These Examples

1. **Choose** the example that fits your use case
2. **Copy** the file to your project folder:
   ```bash
   cp examples/docker-compose-ollama.yml docker-compose.yml
   ```
3. **Create** `.env` from `.env.example` and replace every `CHANGE_ME` value
   with a long random string (for example `openssl rand -base64 32`).
   The API refuses to start with template or well-known weak values.
4. **Run** the services:
   ```bash
   docker compose up -d --build
   ```

All examples publish ports on `127.0.0.1` only. Do not change that to
`0.0.0.0` or remove the address: this project is designed for use on the
same computer, not as a network service.

---

## 💡 Need a Custom Setup?

You can combine features from multiple examples. Common customizations:

### Add Ollama to Standard Setup
Add this to the main `docker-compose.yml`:

```yaml
  ollama:
    image: ollama/ollama:latest
    ports:
      - "127.0.0.1:11434:11434"
    volumes:
      - ollama_models:/root/.ollama
    restart: unless-stopped

volumes:
  ollama_models:
```

### Add Reverse Proxy
See [Reverse Proxy Guide](../docs/5-CONFIGURATION/reverse-proxy.md)

### Authentication
The API always requires `OPEN_NOTEBOOK_PASSWORD` (set it in `.env`). There is
no separate basic-auth layer: variables such as `BASIC_AUTH_USERNAME` are not
read by this project.

---

## 📚 Documentation

- [Installation Guide](../docs/1-INSTALLATION/index.md)
- [Configuration Reference](../docs/5-CONFIGURATION/environment-reference.md)
- [Troubleshooting](../docs/6-TROUBLESHOOTING/index.md)

---

## 🆘 Need Help?

- **Discord**: [Join our community](https://discord.gg/37XJPXfz2w)
- **Issues**: [GitHub Issues](https://github.com/lfnovo/open-notebook/issues)
