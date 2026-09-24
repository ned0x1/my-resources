#!/usr/bin/env python3
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import argparse
import logging


class PutHTTPRequestHandler(SimpleHTTPRequestHandler):
    def do_PUT(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length <= 0:
                self.send_error(400, "Missing or invalid Content-Length")
                return

            # Resolve path safely (prevents ../ traversal)
            target_path = Path(self.translate_path(self.path)).resolve()
            base_path = Path(self.directory).resolve()

            if not str(target_path).startswith(str(base_path)):
                self.send_error(403, "Forbidden")
                return

            target_path.parent.mkdir(parents=True, exist_ok=True)

            with open(target_path, "wb") as f:
                f.write(self.rfile.read(length))

            self.send_response(201)
            self.end_headers()
            self.wfile.write(b"OK\n")

            logging.info("Saved file: %s (%d bytes)", target_path, length)

        except Exception as e:
            logging.exception("PUT failed")
            self.send_error(500, str(e))


def run():
    parser = argparse.ArgumentParser(description="Simple HTTP PUT file server")
    parser.add_argument("-p", "--port", type=int, default=8000)
    parser.add_argument("-b", "--bind", default="")
    parser.add_argument("-d", "--directory", default=".")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    handler = lambda *h_args, **h_kwargs: PutHTTPRequestHandler(
        *h_args, directory=args.directory, **h_kwargs
    )

    server = HTTPServer((args.bind, args.port), handler)

    logging.info("Serving PUT on %s:%d (dir=%s)", args.bind or "0.0.0.0", args.port, args.directory)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logging.info("Shutting down")
        server.server_close()


if __name__ == "__main__":
    run()