const fileInput = document.getElementById('fileInput');
const uploadButton = document.getElementById('uploadButton');
const fileList = document.getElementById('fileList');
const wsUrlInput = document.getElementById('ws-url');
const modelInput = document.getElementById('model');
const promptInput = document.getElementById('prompt');
const sendMessageBtn = document.getElementById('sendMessageBtn');
const chatContainer = document.getElementById('chat-container');
const proxyAddress = document.getElementById('proxy-address');

// Server configuration
const serverHost = '192.168.250.200'; 
const httpPort = 8000;  // proxy server port
const wsPort = 8765;

wsUrlInput.value = `ws://${serverHost}:${wsPort}`;
proxyAddress.textContent = `http://${serverHost}:${httpPort}`;

// --- Fetch list of files from /list endpoint ---
 async function fetchFileList() {
   try {
       const response = await fetch(`http://${serverHost}:${httpPort}/list`);
       if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
       const files = await response.json();
        fileList.innerHTML = '';
        if (files.length === 0) {
            fileList.innerHTML = '<li class="text-gray-400 text-sm">No files available.</li>';
           return;
       }
        files.forEach(file => {
           const li = document.createElement('li');
            li.className = 'flex items-center justify-between bg-gray-800 p-2 rounded-md text-sm';

           const fileNameSpan = document.createElement('span');
          fileNameSpan.textContent = file;
           fileNameSpan.className = "truncate pr-2";
            li.appendChild(fileNameSpan);

            const downloadLink = document.createElement('a');
           downloadLink.href = `http://${serverHost}:${httpPort}/Files/${file}`;
            downloadLink.textContent = 'Download';
          downloadLink.target = '_blank';
          downloadLink.className = 'bg-blue-500 hover:bg-blue-600 text-white font-bold py-1 px-3 rounded-full text-xs transition-colors no-underline flex-shrink-0';
         li.appendChild(downloadLink);
            fileList.appendChild(li);
       });
    } catch (error) {
        console.error("Failed to fetch file list:", error);
        fileList.innerHTML = '<li class="text-red-400 text-sm">Error loading files.</li>';
    }
} 

// --- Upload file ---
uploadButton.addEventListener('click', async () => {
    const file = fileInput.files[0];
    if (!file) return alert("Please select a file to upload.");
    try {
        const response = await fetch(`http://${serverHost}:${httpPort}/${file.name}`, {
            method: 'PUT',
            body: file,
            headers: {'Content-Type': 'application/octet-stream'}
        });
        if (response.ok) {
            alert('File uploaded successfully!');
            fetchFileList();
            fileInput.value = '';
        } else {
            throw new Error(`Upload failed with status: ${response.status}`);
        }
    } catch (error) {
        console.error("Upload error:", error);
        // alert("File upload failed.");
    }
});

// --- WebSocket Chat ---
let socket = null;

function connectSocket() {
    const url = wsUrlInput.value;
    if (!url) return alert("WebSocket URL cannot be empty.");
    socket = new WebSocket(url);

    socket.onopen = () => addMessage("System", `Connected to WebSocket server at ${url}`);
    socket.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            if (data.response) addMessage("Ollama", data.response);
            else if (data.error) addMessage("Error", `${data.error}\n${data.detail || ''}`);
            else addMessage("Unknown", event.data);
        } catch { addMessage("Raw", event.data); }
    };
    socket.onerror = (err) => addMessage("System", "WebSocket error occurred. Check console.");
    socket.onclose = () => addMessage("System", "WebSocket connection closed.");
}

function addMessage(sender, text) {
    if (chatContainer.querySelector('.text-gray-400')) chatContainer.innerHTML = '';
    const messageElem = document.createElement('div');
    messageElem.className = 'p-3 rounded-lg';
    const senderSpan = document.createElement('span');
    senderSpan.className = 'font-bold block mb-1';
    if (sender === 'You') { messageElem.className += ' bg-indigo-800 self-end'; senderSpan.textContent = 'You'; senderSpan.className += ' text-indigo-300'; }
    else if (sender === 'Ollama') { messageElem.className += ' bg-gray-700'; senderSpan.textContent = 'Ollama'; senderSpan.className += ' text-green-300'; }
    else { messageElem.className += ' bg-red-900'; senderSpan.textContent = sender; senderSpan.className += ' text-red-300'; }
    const textNode = document.createElement('pre');
    textNode.className = 'whitespace-pre-wrap font-sans text-sm';
    textNode.textContent = text;
    messageElem.appendChild(senderSpan);
    messageElem.appendChild(textNode);
    chatContainer.appendChild(messageElem);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function handleSend() {
    const message = promptInput.value;
    const model = modelInput.value;
    if (!message.trim()) return;
    addMessage('You', message);
    if (!socket || socket.readyState !== WebSocket.OPEN) {
        connectSocket();
        setTimeout(() => { if (socket && socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ message, model })); }, 1000);
    } else socket.send(JSON.stringify({ message, model }));
    promptInput.value = '';
}

sendMessageBtn.addEventListener('click', handleSend);
promptInput.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } });

document.addEventListener('DOMContentLoaded', () => {
    fetchFileList();
    connectSocket();
});