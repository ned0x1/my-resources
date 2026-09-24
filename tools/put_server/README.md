# Simple HTTP PUT Server

A basic Python server to upload and download files using HTTP.

---

## How to start

```bash
python3 server.py
```

Start on a custom port and directory:

```bash
python3 server.py -p 8080 -d /tmp/uploads
```

Retrieve it and spin it directly :

```bash
curl -o server.py https://gist.githubusercontent.com/tristanqtn/8ba4e6954f16d21a7cec2a6748e5abb6/raw/88c0fb08d0489b227eba9bdcf9725e33b8cab6c6/server.py && python3 server.py
``` 

By default:
- Port: `8000`
- Directory: current directory
- Bind: all interfaces (`0.0.0.0`)

---

## Useful File Transfer Commands

### Linux / macOS (curl)

Upload:

```bash
curl -T file.txt http://SERVER_IP:8000/file.txt
```

Download:

### Linux / macOS (curl)

```bash
curl http://SERVER_IP:8000/file.txt -o file.txt
```

---

### Windows (PowerShell – Invoke-WebRequest)

Upload:

```powershell
Invoke-WebRequest `
  -Uri http://SERVER_IP:8000/file.txt `
  -Method PUT `
  -InFile file.txt
```

Download:

```powershell
Invoke-WebRequest `
  -Uri http://SERVER_IP:8000/file.txt `
  -OutFile file.txt
```