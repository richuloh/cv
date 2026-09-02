#!/usr/bin/env python3
"""Local-only form editor for the bilingual CV content."""

from __future__ import annotations

import argparse
import json
import secrets
import shutil
import subprocess
import sys
import threading
import webbrowser
from datetime import datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from sync_orcid import validate_orcid


ROOT = Path(__file__).resolve().parents[1]
CONTENT_DIR = ROOT / "content"
BACKUP_DIR = ROOT / ".editor-backups"
CONTENT_FILES = {
    "profile": CONTENT_DIR / "profile.json",
    "ko": CONTENT_DIR / "cv.ko.json",
    "en": CONTENT_DIR / "cv.en.json",
    "publications": CONTENT_DIR / "publication_overrides.json",
}
DATA_DIR = ROOT / "data"
BUILD_STEPS = [
    ("ORCID 공개 데이터 동기화", ROOT / "scripts" / "sync_orcid.py", False),
    ("한·영 웹페이지 생성", ROOT / "scripts" / "build_site.py", True),
    ("한·영 PDF 생성", ROOT / "scripts" / "render_pdfs.py", True),
    ("결과 검증", ROOT / "scripts" / "check_output.py", True),
]


def load_content() -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, path in CONTENT_FILES.items():
        with path.open(encoding="utf-8") as handle:
            result[key] = json.load(handle)
    return result


def validate_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("저장 데이터가 올바른 객체 형식이 아닙니다.")
    for key in CONTENT_FILES:
        if not isinstance(payload.get(key), dict):
            raise ValueError(f"{key} 데이터가 없습니다.")

    profile = payload["profile"]
    ko = payload["ko"]
    en = payload["en"]
    orcid_id = str(profile.get("orcid_id") or "").strip()
    validate_orcid(orcid_id)
    profile["orcid_id"] = orcid_id
    profile.setdefault("links", {})["orcid"] = f"https://orcid.org/{orcid_id}"

    if ko.get("lang") != "ko" or en.get("lang") != "en":
        raise ValueError("한글/영문 CV의 언어 코드가 올바르지 않습니다.")
    for key, cv in (("한글", ko), ("영문", en)):
        for required in ("name", "role", "affiliation", "labels"):
            if not cv.get(required):
                raise ValueError(f"{key} CV의 {required} 값이 비어 있습니다.")
        for section in ("experience", "education", "licenses", "projects", "awards", "presentations"):
            if not isinstance(cv.get(section), list):
                raise ValueError(f"{key} CV의 {section} 항목이 목록 형식이 아닙니다.")
    return payload


def save_content(payload: dict[str, Any]) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup = BACKUP_DIR / timestamp
    backup.mkdir(parents=True, exist_ok=False)
    for source in CONTENT_FILES.values():
        shutil.copy2(source, backup / source.name)

    for key, target in CONTENT_FILES.items():
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(json.dumps(payload[key], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(target)
    return backup


def run_build() -> tuple[bool, str]:
    logs: list[str] = []
    for label, script, required in BUILD_STEPS:
        logs.append(f"\n[{label}]")
        try:
            completed = subprocess.run(
                [sys.executable, str(script)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=180,
            )
        except subprocess.TimeoutExpired:
            logs.append("시간 제한(180초)을 초과했습니다.")
            if required:
                return False, "\n".join(logs).strip()
            logs.append("기존 ORCID 스냅샷으로 계속 진행합니다.")
            continue

        output = "\n".join(part.strip() for part in (completed.stdout, completed.stderr) if part.strip())
        logs.append(output or f"완료 (exit {completed.returncode})")
        if completed.returncode != 0:
            if required:
                return False, "\n".join(logs).strip()
            logs.append("ORCID 연결 실패: 기존 스냅샷으로 계속 진행합니다.")
    return True, "\n".join(logs).strip()


class EditorHandler(SimpleHTTPRequestHandler):
    server_version = "RichulCVEditor/1.0"

    def __init__(self, *args: Any, token: str, **kwargs: Any) -> None:
        self.editor_token = token
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, format_string: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {format_string % args}")

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        super().end_headers()

    def authorized(self) -> bool:
        return secrets.compare_digest(self.headers.get("X-Editor-Token", ""), self.editor_token)

    def send_json(self, value: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/":
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", f"/editor/?token={self.editor_token}")
            self.end_headers()
            return
        if path == "/api/content":
            if not self.authorized():
                self.send_json({"error": "편집기 인증 토큰이 올바르지 않습니다."}, HTTPStatus.FORBIDDEN)
                return
            try:
                payload = load_content()
                orcid_path = DATA_DIR / "orcid.json"
                if orcid_path.exists():
                    with orcid_path.open(encoding="utf-8") as handle:
                        payload["orcid_works"] = json.load(handle).get("works", [])
                else:
                    payload["orcid_works"] = []
                self.send_json(payload)
            except (OSError, json.JSONDecodeError) as error:
                self.send_json({"error": str(error)}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        if not (path.startswith("/editor/") or path.startswith("/dist/")):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        super().do_GET()

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if path != "/api/save":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not self.authorized():
            self.send_json({"error": "편집기 인증 토큰이 올바르지 않습니다."}, HTTPStatus.FORBIDDEN)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > 2_000_000:
            self.send_json({"error": "저장 데이터 크기가 올바르지 않습니다."}, HTTPStatus.BAD_REQUEST)
            return

        try:
            raw = self.rfile.read(length).decode("utf-8")
            payload = validate_payload(json.loads(raw))
            backup = save_content(payload)
            ok, log = run_build()
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, OSError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        except Exception as error:  # Keep the local editor responsive and report the unexpected failure.
            self.send_json({"error": f"예상하지 못한 오류: {error}"}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        response = {
            "ok": ok,
            "saved": True,
            "backup": str(backup.relative_to(ROOT)),
            "log": log,
        }
        if ok:
            self.send_json(response)
        else:
            response["error"] = "입력 내용은 저장했지만 사이트 재생성 단계에서 오류가 발생했습니다."
            self.send_json(response, HTTPStatus.INTERNAL_SERVER_ERROR)

    def list_directory(self, path: str) -> None:
        self.send_error(HTTPStatus.NOT_FOUND)
        return None


def serve(port: int, token: str, open_browser: bool) -> int:
    handler = lambda *args, **kwargs: EditorHandler(*args, token=token, **kwargs)  # noqa: E731
    server: ThreadingHTTPServer | None = None
    selected_port = port
    for candidate in range(port, port + 10):
        try:
            server = ThreadingHTTPServer(("127.0.0.1", candidate), handler)
            selected_port = candidate
            break
        except OSError:
            continue
    if server is None:
        raise OSError(f"127.0.0.1:{port}–{port + 9} 포트를 사용할 수 없습니다.")

    url = f"http://127.0.0.1:{selected_port}/editor/?token={token}"
    print("\nRichul Oh CV 편집기가 실행되었습니다.")
    print(f"브라우저 주소: {url}")
    print("종료하려면 이 창에서 Ctrl+C를 누르세요.\n")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n편집기를 종료합니다.")
    finally:
        server.server_close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local CV form editor")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--token", help=argparse.SUPPRESS)
    args = parser.parse_args()
    token = args.token or secrets.token_urlsafe(24)
    return serve(args.port, token, not args.no_browser)


if __name__ == "__main__":
    raise SystemExit(main())
