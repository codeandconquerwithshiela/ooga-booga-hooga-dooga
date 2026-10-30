import argparse
import json
import random
import secrets
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROUNDS = 50
WINNING_SCORE = 100
HTML_FILE = Path(__file__).with_name("index.html")


def new_game():
    return {"round": 0, "candy": 0, "finished": False, "won": False, "last_reward": None}


class GameServer(ThreadingHTTPServer):
    def __init__(self, address, handler):
        super().__init__(address, handler)
        self.games = {}


class GameHandler(BaseHTTPRequestHandler):
    def get_game(self):
        cookies = SimpleCookie()
        cookies.load(self.headers.get("Cookie", ""))
        cookie = cookies.get("pumpkin_session")
        session_id = cookie.value if cookie else None
        set_cookie = None

        if not session_id or session_id not in self.server.games:
            session_id = secrets.token_urlsafe(18)
            self.server.games[session_id] = new_game()
            set_cookie = f"pumpkin_session={session_id}; Path=/; HttpOnly; SameSite=Lax"

        return self.server.games[session_id], set_cookie

    def send_json(self, data, status=200, set_cookie=None):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if set_cookie:
            self.send_header("Set-Cookie", set_cookie)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/state":
            game, set_cookie = self.get_game()
            self.send_json(game, set_cookie=set_cookie)
            return

        if self.path != "/":
            self.send_error(404)
            return

        game, set_cookie = self.get_game()
        body = HTML_FILE.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if set_cookie:
            self.send_header("Set-Cookie", set_cookie)
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path not in {"/api/new-game", "/api/pick"}:
            self.send_error(404)
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length > 1024:
                self.send_json({"error": "Request is too large."}, status=413)
                return
            payload = json.loads(self.rfile.read(content_length) or b"{}")
            if not isinstance(payload, dict):
                raise ValueError("Expected a JSON object.")
        except (json.JSONDecodeError, ValueError):
            self.send_json({"error": "Please send a valid game request."}, status=400)
            return

        game, set_cookie = self.get_game()
        if self.path == "/api/new-game":
            game.clear()
            game.update(new_game())
            self.send_json(game, set_cookie=set_cookie)
            return

        choice = payload.get("choice")
        if isinstance(choice, bool) or not isinstance(choice, int) or choice not in range(3):
            self.send_json({"error": "Choose one of the three pumpkins."}, status=400)
            return
        if game["finished"]:
            self.send_json({"error": "This game is finished. Start a new game to play again."}, status=409)
            return

        reward = random.randint(1, 3)
        game["candy"] += reward
        game["round"] += 1
        game["last_reward"] = reward
        game["finished"] = game["round"] == ROUNDS
        game["won"] = game["finished"] and game["candy"] >= WINNING_SCORE
        self.send_json(game, set_cookie=set_cookie)


def main():
    parser = argparse.ArgumentParser(description="Play Pumpkin Patch Party in your browser.")
    parser.add_argument("--host", default="0.0.0.0", help="Address to serve on (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port to serve on (default: 8000)")
    args = parser.parse_args()

    server = GameServer((args.host, args.port), GameHandler)
    print(f"Pumpkin Patch Party is ready at http://localhost:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nGame server stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()