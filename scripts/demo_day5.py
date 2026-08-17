#!/usr/bin/env python3
"""Create and assess a Day 5 demo project through the public API."""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def request_json(
    url: str,
    *,
    method: str = "GET",
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> dict:
    request = Request(url, data=body, headers=headers or {}, method=method)
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API returned HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Cannot reach {url}: {exc.reason}") from exc


def multipart_file(path: Path) -> tuple[bytes, str]:
    boundary = f"----migration-copilot-{uuid.uuid4().hex}"
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    prefix = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode()
    body = prefix + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--api",
        default="http://localhost:8000/api/v1",
        help="API base URL (default: %(default)s)",
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=repo_root / "sample-data/day5_cvi_ready_customers.csv",
        help="CSV or XLSX source extract",
    )
    args = parser.parse_args()
    source_file = args.file.resolve()
    if not source_file.is_file():
        parser.error(f"file does not exist: {source_file}")

    api = args.api.rstrip("/")
    project_payload = json.dumps(
        {
            "project_name": "Day 5 CVI Readiness Demo",
            "client_name": "Northwind Transformation Lab",
            "source_system": "SAP ECC",
            "target_system": "SAP S/4HANA",
            "migration_object": "Customer Master",
            "country": "IN",
            "description": "Repeatable demo created by scripts/demo_day5.py",
        }
    ).encode()
    project = request_json(
        f"{api}/projects",
        method="POST",
        body=project_payload,
        headers={"Content-Type": "application/json"},
    )

    upload_body, upload_type = multipart_file(source_file)
    uploaded = request_json(
        f"{api}/projects/{project['id']}/files/ecc",
        method="POST",
        body=upload_body,
        headers={"Content-Type": upload_type},
    )
    file_base = f"{api}/projects/{project['id']}/files/{uploaded['id']}"
    assessment = request_json(f"{file_base}/assessment", method="POST", body=b"")
    readiness = request_json(f"{file_base}/readiness")
    cvi = request_json(f"{file_base}/cvi-readiness")

    result = {
        "project": {
            "id": project["id"],
            "code": project["project_code"],
            "status": "assessed",
        },
        "file": {
            "id": uploaded["id"],
            "name": uploaded["file_name"],
            "rows": uploaded["row_count"],
        },
        "assessment": assessment,
        "migration_readiness": readiness,
        "cvi_readiness": cvi,
        "open_in_browser": f"http://localhost:5173/projects/{project['id']}/assessment",
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"demo failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
