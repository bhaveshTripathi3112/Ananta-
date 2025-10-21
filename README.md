# Ananta – Offline AI Assistant & File Manager

**Ananta** is an offline-capable AI assistant platform powered by LLaMA 3 models.  
It allows multiple clients to connect over LAN, chat with a large language model, and manage file uploads/downloads through a browser interface.  

The name "Ananta" means “infinite” in Sanskrit, reflecting the endless possibilities of AI interaction.

---

## Features

- **AI Chat**: Interact with `llama3:8b` through a WebSocket interface.
- **Offline/LAN Support**: Works fully offline on your local network.
- **File Manager**: Upload and download files directly from the browser.
- **Client-specific Chat History**: Stores conversation history per client in JSON format.
- **Cross-platform**: Works on Windows, Linux, and macOS with Python.
- **Customizable**: Users can select the model, adjust max tokens, and tweak temperature.

---

## Project Structure

```
Ananta/
│
├─ server/
│ ├─ websocket_server.py # WebSocket server for LLM interaction
│ ├─ main.py # Proxy server for file uploads/downloads
│ ├─ http_hanlder.py 
│ ├─ proxy_parse.py 
│ ├─ cache.py 
│ ├─ file_share.py 
│ ├─ Files/ # Folder to store uploaded/downloaded files
│ └─ Model/
│ └─ finetune_ananta.py # Script for fine-tuning LLaMA 3 models
│
├─ frontend/
│ └─ index.html # Web-based chat & file manager interface
│ └─ script.js    
├─ requirements.txt # Python dependencies
├─ .gitignore
├─ README.md
└─ LICENSE 
```

---
## Requirements

- **OS:** Windows, Linux, or MacOS
- **CPU:** 6+ cores recommended
- **GPU:** NVIDIA with 4GB+ VRAM (for GPU acceleration)
- **RAM:** 8 GB recommended for LLaMA 3:8B
- **Python:** 3.10+
- **Node (optional):** for frontend development

> ⚠️ Note: LLaMA 3:8B requires around 2.5–3 GB of free memory to load. Smaller models like SmolLM2-360M can run on lower-spec systems.

---

## Installation

1. **Install Ollama and download LLaMA 3 models**
```bash
ollama install llama3:8b
```

2 . ***Create a virtual environment***
```bash
# Create and activate a virtual environment
python -m venv venv

# Windows
.\venv\Scripts\activate

# Linux / Mac
source venv/bin/activate
```
3. ***Install Python dependencies***
```bash
pip install -r requirements.txt
```
4 . ***Download LLaMA 3:8B model***
```bash
Use Ollama to download and manage models:

ollama pull llama3:8b
```

---
### Running the Server
1. ***Start Ollama***
```
ollama list  // to check models which are present

set OLLAMA_HOST=0.0.0.0:11434

ollama serve
```

2. ***Start the WebSocket Server***
```
python websocket_server.py
```
Listens on 0.0.0.0:8765 for WebSocket clients.

Maintains chat history per client in memory.

Streams prompts to Ollama and sends responses back.

3. ***Running Proxy Server***
```
python main.py 8000
```

---

## Frontend Usage

1. **Open the Frontend**

   Open the `index.html` file in any modern web browser (e.g., Chrome, Edge, or Firefox).

2. **Connect to the WebSocket Server**

   - Set the WebSocket URL in the input field:  
     ```
     ws://<server_ip>:8765
     ```
   - Replace `<server_ip>` with the IP address of the machine running the WebSocket server.

3. **Chat with the Model**

   - Type your message in the text area.  
   - Click **Send** or press **Enter** to communicate with the LLaMA model.

4. **File Management**

   - Use the **left panel** to upload files to the proxy server.  
   - Download any available files from the displayed list.

5. **View Chat History**

   - All messages and AI responses are displayed in the **main chat panel** for easy reference.