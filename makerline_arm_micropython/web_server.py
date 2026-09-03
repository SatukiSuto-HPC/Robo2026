# =============================================================================
# web_server.py - Ultra Memory-Efficient Non-Blocking HTTP Server & Web UI
# =============================================================================

import socket
import json
import time
import uselect
import gc
import os
import config

class WebServer:
    def __init__(self, line_follower):
        self._line_follower = line_follower
        self._server_s = None
        self._poller = None
        self._stream_buf = bytearray(512)  # Reusable 512-byte buffer for streaming

    def begin(self):
        try:
            addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
            self._server_s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server_s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_s.bind(addr)
            self._server_s.listen(5)
            self._server_s.setblocking(False)

            self._poller = uselect.poll()
            self._poller.register(self._server_s, uselect.POLLIN)
            print("[WEB SERVER] Bound & listening on http://192.168.4.1:80 (RAM-Optimized)")
        except Exception as e:
            print("[WEB SERVER INIT ERROR] Failed to bind/listen:", e)

    def start(self):
        if not self._server_s:
            self.begin()

    def update(self):
        if not self._server_s or not self._poller:
            return

        try:
            res = self._poller.poll(0)
        except Exception:
            return

        if not res:
            return

        for s, event in res:
            if s == self._server_s and (event & uselect.POLLIN):
                cl = None
                try:
                    cl, addr = self._server_s.accept()
                    cl.settimeout(2.0)
                    self._handle_client(cl)
                except Exception as e:
                    print("[WEB SERVER] Client error:", e)
                finally:
                    if cl:
                        try:
                            cl.close()
                        except Exception:
                            pass

    def _handle_client(self, cl):
        try:
            raw_req = cl.recv(1024)
            if not raw_req:
                return

            req_str = raw_req.decode('utf-8', 'ignore')
            lines = req_str.split('\r\n')
            if not lines or not lines[0]:
                return

            parts = lines[0].split(' ')
            if len(parts) < 2:
                return
            method = parts[0]
            full_path = parts[1]
            path = full_path.split('?')[0]  # Strip query string

            if method == "GET" and path == "/":
                try:
                    content_len = os.stat('index.html')[6]
                    header = f"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: {content_len}\r\nConnection: close\r\n\r\n"
                    cl.send(header.encode('utf-8'))
                    with open('index.html', 'rb') as f:
                        while True:
                            n = f.readinto(self._stream_buf)
                            if n <= 0:
                                break
                            cl.send(memoryview(self._stream_buf)[:n])
                except Exception as e:
                    print("[WEB SERVER] Failed to stream index.html:", e)
                    cl.send(b"HTTP/1.1 500 Internal Error\r\nConnection: close\r\n\r\nError")

            elif method == "GET" and path == "/api/status":
                st_map = {0: "IDLE", 1: "TRACKING", 2: "TURN_LEFT"}
                st_str = st_map.get(self._line_follower.get_state(), "UNKNOWN")

                data = {
                    "state": st_str,
                    "pattern": self._line_follower.get_sensor_pattern(),
                    "base_delay": self._line_follower.get_base_delay(),
                    "trim": self._line_follower.get_motor_trim()
                }
                resp_bytes = json.dumps(data).encode('utf-8')
                header = f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(resp_bytes)}\r\nConnection: close\r\n\r\n"
                cl.send(header.encode('utf-8'))
                cl.send(resp_bytes)

            elif method == "POST" and path == "/api/command":
                # [FIX] Wrap JSON parse in try-except to return 400 instead of silently dropping
                try:
                    body = req_str.split('\r\n\r\n')[-1]
                    req_json = json.loads(body) if body.strip() else {}
                except Exception:
                    cl.send(b"HTTP/1.1 400 Bad Request\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
                    return
                cmd = req_json.get("command", "").upper()

                if cmd == "START":
                    self._line_follower.start_tracking()
                elif cmd == "STOP":
                    self._line_follower.stop()

                resp_bytes = b'{"status":"ok"}'
                header = f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(resp_bytes)}\r\nConnection: close\r\n\r\n"
                cl.send(header.encode('utf-8'))
                cl.send(resp_bytes)

            elif method == "POST" and path == "/api/param":
                # [FIX] Wrap JSON parse in try-except; cast val to int explicitly
                try:
                    body = req_str.split('\r\n\r\n')[-1]
                    req_json = json.loads(body) if body.strip() else {}
                except Exception:
                    cl.send(b"HTTP/1.1 400 Bad Request\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
                    return
                param = req_json.get("param", "")
                val = int(req_json.get("value", 0))  # [FIX] explicit int cast

                if param == "delay":
                    self._line_follower.set_base_delay(val)
                elif param == "trim":
                    self._line_follower.set_motor_trim(val)

                resp_bytes = b'{"status":"ok"}'
                header = f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(resp_bytes)}\r\nConnection: close\r\n\r\n"
                cl.send(header.encode('utf-8'))
                cl.send(resp_bytes)

            else:
                resp = b"HTTP/1.1 404 Not Found\r\nContent-Type: text/plain\r\nContent-Length: 9\r\nConnection: close\r\n\r\nNot Found"
                cl.send(resp)

            # [FIX] Removed unconditional gc.collect() that was causing motor step stalls.
            # GC is handled by MicroPython's automatic allocator; force-collect only when needed.

        except Exception as e:
            print("[WEB SERVER] Exception in request handler:", e)

