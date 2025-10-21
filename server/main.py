import os
import socket
import threading
import sys
import json
from http_handler import handle_put, handle_file_upload, handle_options
from proxy_parse import parse_http_request

DEFAULT_PORT = 8000
MAX_CLIENTS = 1000
RECV_BUFFER = 4096
SOCKET_TIMEOUT = 30  # seconds

FILES_DIR = "./Files"
os.makedirs(FILES_DIR, exist_ok=True)

semaphore = threading.Semaphore(MAX_CLIENTS)
thread_count_lock = threading.Lock()
thread_counter = 0

CORS_HEADERS = (
    "Access-Control-Allow-Origin: *\r\n"
    "Access-Control-Allow-Methods: GET, POST, PUT, OPTIONS\r\n"
    "Access-Control-Allow-Headers: Content-Type, Authorization\r\n"
)

def send_json_response(client_socket, data, status=200):
    body = json.dumps(data)
    response = (
        f"HTTP/1.1 {status} OK\r\n"
        f"Content-Type: application/json\r\n"
        f"{CORS_HEADERS}"
        f"Content-Length: {len(body)}\r\n"
        "Connection: close\r\n\r\n"
        f"{body}"
    )
    client_socket.sendall(response.encode())

def send_file_response(client_socket, filepath, filename):
    try:
        with open(filepath, "rb") as f:
            file_data = f.read()
        header = (
            "HTTP/1.1 200 OK\r\n"
            f"{CORS_HEADERS}"
            "Content-Type: application/octet-stream\r\n"
            f"Content-Disposition: attachment; filename=\"{filename}\"\r\n"
            f"Content-Length: {len(file_data)}\r\n"
            "Connection: close\r\n\r\n"
        )
        client_socket.sendall(header.encode() + file_data)
        print(f"[GET] Served file: {filename}")
    except Exception as e:
        client_socket.sendall(b"HTTP/1.1 500 Internal Server Error\r\nContent-Length: 0\r\n\r\n")
        print(f"[GET] Failed to serve file {filename}: {e}")

def threaded_client_fn(client_socket: socket.socket, client_addr):
    global thread_counter
    acquired = False
    try:
        semaphore.acquire()
        acquired = True
        client_socket.settimeout(SOCKET_TIMEOUT)

        # Read HTTP request
        data = bytearray()
        try:
            while True:
                chunk = client_socket.recv(RECV_BUFFER)
                if not chunk:
                    break
                data.extend(chunk)
                if b"\r\n\r\n" in data:
                    break
                if len(data) > 2_000_000:
                    break
        except Exception as e:
            print(f"[THREAD {client_addr}] recv error: {e}")
            client_socket.close()
            return

        if not data:
            client_socket.close()
            return

        parsed, headers_bytes, body_bytes = parse_http_request(bytes(data))
        if parsed is None:
            client_socket.sendall(b"HTTP/1.1 400 Bad Request\r\nContent-Length: 0\r\n\r\n")
            client_socket.close()
            return

        # Extract Content-Length from headers list
        content_length = 0
        for header in parsed.headers:
            if header.lower().startswith("content-length:"):
                content_length = int(header.split(":", 1)[1].strip())
                break

        already = len(body_bytes)
        to_read = content_length - already
        while to_read > 0:
            chunk = client_socket.recv(min(RECV_BUFFER, to_read))
            if not chunk:
                break
            body_bytes += chunk
            to_read -= len(chunk)

        raw_request = headers_bytes + b"\r\n\r\n" + body_bytes if headers_bytes else bytes(data)
        method = parsed.method.upper()
        print(f"[THREAD {client_addr}] Handling {method} for {parsed.path}")

        # -------------------- GET --------------------
        if method == "GET":
            if parsed.path == "/list":
                # Return JSON array of files
                try:
                    files = [f for f in os.listdir(FILES_DIR) if os.path.isfile(os.path.join(FILES_DIR, f))]
                    send_json_response(client_socket, files)
                except Exception as e:
                    client_socket.sendall(b"HTTP/1.1 500 Internal Server Error\r\nContent-Length: 0\r\n\r\n")
                    print(f"[GET] Failed to list files: {e}")
            elif parsed.path.startswith("/Files/"):
                filename = os.path.basename(parsed.path)
                filepath = os.path.join(FILES_DIR, filename)
                if os.path.exists(filepath):
                    send_file_response(client_socket, filepath, filename)
                else:
                    client_socket.sendall(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n")
            else:
                client_socket.sendall(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n")

        # -------------------- PUT --------------------
        elif method == "PUT":
            handle_put(client_socket, parsed, raw_request)

        # -------------------- POST --------------------
        elif method == "POST":
            handle_file_upload(client_socket, parsed, body_bytes, len(body_bytes))

        # -------------------- OPTIONS --------------------
        elif method == "OPTIONS":
            handle_options(client_socket, parsed, raw_request)

        else:
            client_socket.sendall(b"HTTP/1.1 405 Method Not Allowed\r\nContent-Length: 0\r\n\r\n")

    except Exception as e:
        print(f"[THREAD {client_addr}] Exception in handler: {e}")
        client_socket.sendall(b"HTTP/1.1 500 Internal Server Error\r\nContent-Length: 0\r\n\r\n")
    finally:
        try:
            client_socket.close()
        except Exception:
            pass
        if acquired:
            semaphore.release()
        with thread_count_lock:
            thread_counter += 1
        print(f"[THREAD {client_addr}] Connection closed")


def start_server(listen_host: str = "0.0.0.0", listen_port: int = DEFAULT_PORT):
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_sock.bind((listen_host, listen_port))
        server_sock.listen(MAX_CLIENTS)
    except Exception as e:
        print(f"[MAIN] Failed to bind/listen on {listen_host}:{listen_port} -> {e}")
        server_sock.close()
        return

    print(f"[MAIN] File server listening on {listen_host}:{listen_port}")

    try:
        while True:
            try:
                client_sock, client_addr = server_sock.accept()
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"[MAIN] accept error: {e}")
                continue

            print(f"[MAIN] Connection accepted from {client_addr[0]}:{client_addr[1]}")

            t = threading.Thread(
                target=threaded_client_fn,
                args=(client_sock, f"{client_addr[0]}:{client_addr[1]}"),
                daemon=True,
            )
            t.start()

    except KeyboardInterrupt:
        print("\n[MAIN] Shutting down due to KeyboardInterrupt")
    finally:
        try:
            server_sock.close()
        except Exception:
            pass
        print("[MAIN] Server closed")


if __name__ == "__main__":
    port = DEFAULT_PORT
    if len(sys.argv) >= 2:
        try:
            port_arg = int(sys.argv[1])
            if 1 <= port_arg <= 65535:
                port = port_arg
            else:
                print("[MAIN] Invalid port number, using default 8080")
        except ValueError:
            print("[MAIN] Invalid port arg, using default 8080")

    start_server(listen_port=port)
