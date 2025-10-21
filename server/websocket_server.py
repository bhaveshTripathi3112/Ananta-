import asyncio
import json
import traceback
from typing import Dict
import requests
import websockets

OLLAMA_API_URL = "http://192.168.250.200:11434/api/generate" 

WS_HOST = "0.0.0.0"   
WS_PORT = 8765

OLLAMA_TIMEOUT = 300

# Store history per client
client_histories: Dict[str, list] = {}

async def call_ollama(prompt: str, model: str = "llama3:8b") -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": True,       
        "max_tokens": 100,    
        "num_ctx": 1024,      
        "temperature": 0.5   
    }

    def sync_request():
        with requests.post(OLLAMA_API_URL, json=payload, stream=True, timeout=OLLAMA_TIMEOUT) as r:
            r.raise_for_status()

            full_output = ""
            for line in r.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    text_piece = chunk.get("response") or chunk.get("text") or ""
                    full_output += text_piece
                except Exception:
                    pass
            return full_output.strip()

    return await asyncio.to_thread(sync_request)

async def ws_handler(ws):
    client_id = f"{ws.remote_address}"
    print(f"[WS] Connection from {client_id}")

    # Initialize history for this client
    if client_id not in client_histories:
        client_histories[client_id] = []

    try:
        async for message in ws:
            try:
                data = json.loads(message)
                if isinstance(data, dict) and "message" in data:
                    prompt = data["message"]
                    model = data.get("model", "llama3:8b")
                else:
                    prompt = str(data)
                    model = "llama3:8b"
            except json.JSONDecodeError:
                prompt = message
                model = "llama3:8b"

            # Add user prompt to history
            client_histories[client_id].append({"role": "user", "content": prompt})
            print(f"[WS] Prompt from {client_id}: {prompt[:100]}")

            try:
                # Combine history into a single prompt for Ollama
                full_prompt = "\n".join([f"{entry['role']}: {entry['content']}" for entry in client_histories[client_id]])
                ai_text = await call_ollama(full_prompt, model=model)
                if not isinstance(ai_text, str):
                    ai_text = str(ai_text)
 
                client_histories[client_id].append({"role": "ai", "content": ai_text})

                resp = {"response": ai_text}

            except Exception as e:
                traceback.print_exc()
                resp = {"error": "Failed to call Ollama", "detail": str(e)}

            try:
                await ws.send(json.dumps(resp))
            except Exception:
                print(f"[WS] Failed to send response to {client_id}")
                break

    except websockets.ConnectionClosed:
        pass
    except Exception:
        traceback.print_exc()
    finally:
        print(f"[WS] Connection closed: {client_id}")

def start_ws_server_forever(host: str = WS_HOST, port: int = WS_PORT):
    async def runner():
        server = await websockets.serve(ws_handler, host, port)
        print(f"[WS] WebSocket server listening on ws://{host}:{port}")
        await server.wait_closed()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(runner())
    finally:
        loop.close()

if __name__ == "__main__":
    start_ws_server_forever()
