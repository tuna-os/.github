#!/usr/bin/env python3
"""Run the reusable release verifier against local GitHub API fixtures."""

import json
import os
import re
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/reusable-release-verification.yml"
FIXTURES = ROOT / "tests/fixtures/release-verification"
CONTRACT = json.dumps(
    [
        {
            "name": "example.tar.gz",
            "checksum": "example.tar.gz.sha256",
            "signature": "example.tar.gz.sig",
            "provenance": "example.tar.gz.intoto.jsonl",
            "sbom": "example.tar.gz.spdx.json",
        }
    ]
)


def verifier_source() -> str:
    text = WORKFLOW.read_text(encoding="utf-8")
    match = re.search(r"python3 - <<'PYEOF'\n(?P<body>.*?)\n          PYEOF", text, re.DOTALL)
    if not match:
        raise RuntimeError("could not locate verifier in reusable workflow")
    lines = match.group("body").splitlines()
    if not lines or any(line and not line.startswith("          ") for line in lines):
        raise RuntimeError("unexpected verifier indentation")
    return "\n".join(line[10:] for line in lines) + "\n"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def run_fixture(name: str, expected_returncode: int, expected_text: str) -> None:
    fixture = load_fixture(name)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            response = fixture["routes"].get(self.path, {"status": 404, "json": {"message": "not found"}})
            status = response["status"]
            if "json" in response:
                body = json.dumps(response["json"]).replace("{base}", base_url).encode()
                content_type = "application/json"
            else:
                body = response.get("text", "").replace("{base}", base_url).encode()
                content_type = "application/octet-stream"
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    base_url = f"http://127.0.0.1:{server.server_port}"
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            summary = Path(temp_dir) / "summary.md"
            env = os.environ.copy()
            env.update(
                {
                    "API_URL": base_url,
                    "EXPECTED_ARTIFACTS": CONTRACT,
                    "EXPECTED_COMMIT": "1" * 40,
                    "GH_TOKEN": "fixture-token",
                    "GITHUB_STEP_SUMMARY": str(summary),
                    "RELEASE_REPOSITORY": "tuna-os/example",
                    "RELEASE_TAG": "v1.2.3",
                }
            )
            result = subprocess.run(
                [sys.executable, "-c", verifier_source()],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            output = result.stdout + result.stderr
            if result.returncode != expected_returncode:
                raise AssertionError(f"{name}: expected exit {expected_returncode}, got {result.returncode}\n{output}")
            if expected_text not in output:
                raise AssertionError(f"{name}: expected {expected_text!r} in output\n{output}")
            summary_text = summary.read_text(encoding="utf-8")
            expected_status = "PASSED" if expected_returncode == 0 else "FAILED"
            if expected_status not in summary_text:
                raise AssertionError(f"{name}: summary did not report {expected_status}\n{summary_text}")
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def main() -> None:
    run_fixture("success", 0, "Verified release tuna-os/example@v1.2.3")
    run_fixture("missing-artifact", 1, "missing required assets: example.tar.gz.spdx.json")
    run_fixture("api-failure", 1, "HTTP 503")
    print("release verification fixtures passed")


if __name__ == "__main__":
    main()
