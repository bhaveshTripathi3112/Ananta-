import os
import socket
from cache import cache

MAX_BYTES = 4096
MAX_RESPONSE_SIZE = 50 * 1024 * 1024  # 50MB
FILES_DIR = "./Files"
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# Ensure the Files directory exists
os.makedirs(FILES_DIR, exist_ok=True)

# --- common reusable CORS header string ---
CORS_HEADERS = (
    "Access-Control-Allow-Origin: *\r\n"
    "Access-Control-Allow-Methods: GET, POST, PUT, OPTIONS\r\n"
    "Access-Control-Allow-Headers: Content-Type, Authorization\r\n"
)

def send_error_response(client_socket, status_code, message):
    status_texts = {
        400: "Bad Request",
        404: "Not Found",
        405: "Method Not Allowed",
        500: "Internal Server Error",
        502: "Bad Gateway",
        504: "Gateway Timeout",
    }
    status_text = status_texts.get(status_code, "Error")
    body = (
        f"<html><head><title>{status_code} {status_text}</title></head>"
        f"<body><h1>{status_code} {status_text}</h1><p>{message}</p></body></html>"
    )
    response = (
        f"HTTP/1.1 {status_code} {status_text}\r\n"
        f"Content-Type: text/html\r\n"
        f"{CORS_HEADERS}"
        f"Content-Length: {len(body)}\r\n"
        "Connection: close\r\n\r\n"
        f"{body}"
    )
    client_socket.sendall(response.encode())

def connect_remote_server(host, port):
    try:
        s = socket.create_connection((host, int(port)), timeout=30)
        return s
    except Exception as e:
        print(f"[HTTP] Failed to connect to {host}:{port} -> {e}")
        return None

def parse_host_port(host_header):
    if ':' in host_header:
        host, port = host_header.split(':', 1)
        return host, int(port)
    return host_header, 8080

# -------------------- OPTIONS HANDLER (CORS preflight) --------------------
def handle_options(client_socket, request, raw_request):
    response = (
        "HTTP/1.1 204 No Content\r\n"
        f"{CORS_HEADERS}"
        "Access-Control-Max-Age: 86400\r\n"
        "Connection: keep-alive\r\n\r\n"
    )
    client_socket.sendall(response.encode())
    print(f"[OPTIONS] Handled preflight for {request.path}")
    return 0

# -------------------- GET HANDLER --------------------
def handle_get(client_socket, request, raw_request):
    # Serve local file first
    filename = os.path.basename(request.path)
    filepath = os.path.join(FILES_DIR, filename)

    if os.path.exists(filepath):
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
        full_response = header.encode() + file_data
        client_socket.sendall(full_response)
        cache.cache_add(full_response, request.path)
        print(f"[GET] Served local file {filename}")
        return 0

    # If not local, try remote server (optional)
    host, port = parse_host_port(request.host)
    remote_sock = connect_remote_server(host, port)
    if not remote_sock:
        send_error_response(client_socket, 502, "Failed to connect remote server")
        return -1

    http_req = (
        f"GET {request.path} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        f"Connection: close\r\n"
        f"User-Agent: ProxyServer/1.0\r\n\r\n"
    )
    remote_sock.sendall(http_req.encode())

    full_response = b""
    while True:
        data = remote_sock.recv(MAX_BYTES)
        if not data:
            break
        client_socket.sendall(data)
        full_response += data
        if len(full_response) > MAX_RESPONSE_SIZE:
            full_response = b""
            break

    remote_sock.close()
    if full_response:
        cache.cache_add(full_response, f"{host}:{port}{request.path}")
    return 1

# -------------------- POST HANDLER --------------------
def handle_post(client_socket, request, raw_request):
    host, port = parse_host_port(request.host)
    remote_sock = connect_remote_server(host, port)
    if not remote_sock:
        send_error_response(client_socket, 502, "Failed to connect remote server")
        return -1

    remote_sock.sendall(raw_request.encode())
    while True:
        data = remote_sock.recv(MAX_BYTES)
        if not data:
            break
        client_socket.sendall(data)
    remote_sock.close()
    return 1

# -------------------- PUT HANDLER (UPLOAD) --------------------
def handle_put(client_socket, request, raw_request):
    filename = os.path.basename(request.path)
    filepath = os.path.join(FILES_DIR, filename)

    split_data = raw_request.split(b"\r\n\r\n", 1)
    body = split_data[1] if len(split_data) > 1 else b""

    try:
        with open(filepath, "wb") as f:
            f.write(body[:MAX_FILE_SIZE])

        response_body = (
            f"<html><body><h1>✅ File '{filename}' uploaded successfully!</h1></body></html>"
        )
        response = (
            "HTTP/1.1 201 Created\r\n"
            f"{CORS_HEADERS}"
            "Content-Type: text/html\r\n"
            f"Content-Length: {len(response_body)}\r\n"
            "Connection: close\r\n\r\n"
            f"{response_body}"
        )
        client_socket.sendall(response.encode())
        print(f"[PUT] File saved: {filepath}")
        return 0
    except Exception as e:
        send_error_response(client_socket, 500, f"Failed to save file: {e}")
        return -1

# -------------------- FILE UPLOAD HELPER --------------------
def handle_file_upload(client_socket, request, body, body_len):
    filename = os.path.basename(request.path)
    if not filename:
        send_error_response(client_socket, 400, "No filename specified")
        return -1

    filepath = os.path.join(FILES_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(body[:MAX_FILE_SIZE])

    response_body = f"<html><body><h1>File uploaded successfully: {filename}</h1></body></html>"
    response = (
        "HTTP/1.1 200 OK\r\n"
        f"{CORS_HEADERS}"
        "Content-Type: text/html\r\n"
        f"Content-Length: {len(response_body)}\r\n"
        "Connection: close\r\n\r\n"
        f"{response_body}"
    )
    client_socket.sendall(response.encode())
    print(f"[UPLOAD] File saved as {filepath}")
    return 1



