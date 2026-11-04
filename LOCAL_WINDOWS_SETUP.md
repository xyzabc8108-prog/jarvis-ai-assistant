# JARVIS local Windows install (8 GB RAM + GTX 1650, 4 GB VRAM)

This setup runs the existing JARVIS dashboard and its AI brain **entirely on your Windows computer**. No OpenAI API key or Render account is needed locally.

## 1. Install Ollama

Download the Windows installer from https://ollama.com/download/windows. Install it and restart PowerShell.

Check:
```powershell
ollama --version
```

Download the recommended 3B language model (about 2 GB):
```powershell
ollama pull llama3.2
```

If memory use is too high or responses are too slow, install the smaller alternative:
```powershell
ollama pull llama3.2:1b
```

Ollama normally starts in the background on Windows and serves an API on http://127.0.0.1:11434. Check readiness:
```powershell
Invoke-RestMethod http://127.0.0.1:11434/api/tags
```

If Ollama is not running, start the Ollama application from the Start menu. Do **not** expose port 11434 to the public internet.

## 2. Install Python and Git

Install Python 3.11+ and Git for Windows if not already installed. Check:
```powershell
py --version
git --version
```

Clone the existing project into your user profile:
```powershell
cd $HOME
git clone https://github.com/xyzabc8108-prog/jarvis-ai-assistant.git
cd jarvis-ai-assistant
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

If the folder already exists, use `git pull` inside it instead of cloning again.

## 3. Start JARVIS with Ollama

In the same PowerShell window:
```powershell
$env:JARVIS_AI_PROVIDER = "ollama"
$env:OLLAMA_MODEL = "llama3.2"
$env:JARVIS_LOCAL_DEV = "1"
$env:JARVIS_OWNER_PASSWORD = Read-Host "Enter a new local JARVIS password"
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Browse to **http://127.0.0.1:8000** (not the Render URL), sign in using the password you just entered, and type "Introduce yourself".

For the 1B model, set `$env:OLLAMA_MODEL = "llama3.2:1b"` before starting the server.

### Notes

- The local AI provider is selected only in the PowerShell environment of your PC. It does **not** change Render environment variables or access to the public Render site.
- This version keeps sessions, conversation memory and task planning in RAM; server restarts erase them. The existing task planner still does not execute external actions.
- The local backend connects only to `127.0.0.1:11434`, not other network hosts. Do not make the local API publicly accessible.
- Keep both PowerShell and Ollama running while using JARVIS. Press Ctrl+C to stop the JARVIS server.
- `JARVIS_LOCAL_DEV=1` relaxes cookie settings for localhost only. Bind the server to `127.0.0.1`, never `0.0.0.0` with this setting.
- The initial Ollama model download requires internet. Subsequent text generation can work offline.
- Browser speech-recognition and voice synthesis may depend on the browser and external services; offline voice is not yet implemented.
- GPU offloading depends on installed drivers and memory availability. GPU use is not guaranteed.

## Troubleshooting

- "Ollama is not running": launch the Ollama app, then retry.
- "Model is missing": run `ollama pull llama3.2`.
- "Local AI timed out": close memory-heavy apps or switch to `llama3.2:1b`.
- Password/login issues: restart local JARVIS and set `JARVIS_OWNER_PASSWORD` again.
- Website still says "API credit limit": you are using the Render deployment or started the local server without `JARVIS_AI_PROVIDER=ollama`.

**Never put your owner password or keys into the repository or a screenshot.**
