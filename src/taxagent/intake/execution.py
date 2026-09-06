"""Hard process limits for local PDF intake workers."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import json
import os
import pickle
from queue import Queue
import subprocess
import sys
from threading import Thread
from typing import Any

from .models import ImportedDocument, ImportedSlipCandidate

DEFAULT_WORKER_MODULE = "taxagent.intake._pdf_worker"
DEFAULT_WORKER_MEMORY_LIMIT_BYTES = 1536 * 1024 * 1024
WORKER_MEMORY_LIMIT_ENV = "TAXAGENT_PDF_WORKER_MEMORY_LIMIT_BYTES"
MAX_WORKER_OUTPUT_BYTES = 2_000_000
_WORKER_STDOUT_CHUNK_BYTES = 64 * 1024


@dataclass(frozen=True)
class PdfWorkerResult:
    document: ImportedDocument
    candidates: list[ImportedSlipCandidate]
    ocr_pages_used: int = 0
    ocr_pixels_used: int = 0
    ocr_exhausted: bool = False


def run_import_one_pdf_worker(
    payload: dict[str, Any],
    *,
    timeout_seconds: float,
    worker_module: str = DEFAULT_WORKER_MODULE,
    memory_limit_bytes: int | None = None,
) -> PdfWorkerResult:
    if timeout_seconds <= 0:
        return _resource_limited(payload)

    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    worker_env = os.environ.copy()
    worker_env[WORKER_MEMORY_LIMIT_ENV] = str(
        DEFAULT_WORKER_MEMORY_LIMIT_BYTES if memory_limit_bytes is None else memory_limit_bytes
    )
    process = subprocess.Popen(
        [sys.executable, "-m", worker_module],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
        env=worker_env,
    )
    request = pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL)

    stdout, output_exceeded = _communicate_bounded(process, request, timeout_seconds)
    if stdout is None:
        return _resource_limited(payload)

    if process.returncode != 0 or output_exceeded:
        return _resource_limited(payload)

    try:
        response = json.loads(stdout.decode("utf-8"))
        return PdfWorkerResult(
            document=ImportedDocument.model_validate(response["document"]),
            candidates=[
                ImportedSlipCandidate.model_validate(candidate)
                for candidate in response.get("candidates", [])
            ],
            ocr_pages_used=int(response.get("ocr_pages_used", 0)),
            ocr_pixels_used=int(response.get("ocr_pixels_used", 0)),
            ocr_exhausted=bool(response.get("ocr_exhausted", False)),
        )
    except Exception:
        return _resource_limited(payload)


def _resource_limited(payload: dict[str, Any]) -> PdfWorkerResult:
    return PdfWorkerResult(
        document=ImportedDocument(
            document_id=str(payload["document_id"]),
            filename=str(payload["filename"]),
            sha256=str(payload["digest"]),
            status="resource_limited",
            page_count=0,
            message="PDF import exceeded the configured processing time limit.",
        ),
        candidates=[],
        ocr_exhausted=True,
    )


def _communicate_bounded(
    process: subprocess.Popen[bytes],
    request: bytes,
    timeout_seconds: float,
) -> tuple[bytes | None, bool]:
    stdout_buffer = BytesIO()
    output_exceeded = Queue[bool](maxsize=1)
    writer_errors = Queue[BaseException](maxsize=1)

    def read_stdout() -> None:
        assert process.stdout is not None
        total = 0
        try:
            while True:
                chunk = process.stdout.read(_WORKER_STDOUT_CHUNK_BYTES)
                if not chunk:
                    break
                remaining = MAX_WORKER_OUTPUT_BYTES + 1 - total
                if remaining > 0:
                    stdout_buffer.write(chunk[:remaining])
                    total += min(len(chunk), remaining)
                if total > MAX_WORKER_OUTPUT_BYTES:
                    output_exceeded.put(True)
                    _kill_process(process)
                    break
        except OSError as exc:
            writer_errors.put(exc)

    def write_stdin() -> None:
        assert process.stdin is not None
        try:
            process.stdin.write(request)
            process.stdin.close()
        except (BrokenPipeError, OSError) as exc:
            writer_errors.put(exc)

    reader = Thread(target=read_stdout, daemon=True)
    writer = Thread(target=write_stdin, daemon=True)
    reader.start()
    writer.start()
    try:
        process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        _kill_process(process)
        process.wait()
        writer.join(timeout=1.0)
        reader.join(timeout=1.0)
        return None, False

    writer.join(timeout=1.0)
    reader.join(timeout=1.0)
    if not writer_errors.empty() and process.returncode == 0:
        return None, False
    return stdout_buffer.getvalue(), not output_exceeded.empty()


def _kill_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is None:
        process.kill()
