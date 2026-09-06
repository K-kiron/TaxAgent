from __future__ import annotations

import ctypes
from io import BytesIO
import os
from pathlib import Path
import textwrap
import time

from reportlab.pdfgen import canvas

import taxagent.intake.execution as intake_execution
import taxagent.intake.pdf as pdf_intake


def _text_pdf() -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(612, 792))
    pdf.drawString(72, 750, "T4 Statement of Remuneration Paid")
    pdf.drawString(72, 730, "Tax year 2025")
    pdf.drawString(72, 710, "Employer name Example Robotics Inc.")
    pdf.drawString(72, 690, "Box 14 Employment income 45,000.00")
    pdf.save()
    return buffer.getvalue()


def _process_is_running(pid: int) -> bool:
    if os.name != "nt":
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(0x1000, False, pid)
    if not handle:
        return False
    exit_code = ctypes.c_ulong()
    try:
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return False
        return exit_code.value == 259
    finally:
        kernel32.CloseHandle(handle)


def test_import_pdf_batch_kills_stalled_worker_and_keeps_prior_valid_file(
    monkeypatch, tmp_path: Path
):
    worker = tmp_path / "stalling_pdf_worker.py"
    worker.write_text(
        textwrap.dedent(
            """
            from pathlib import Path
            import json
            import os
            import pickle
            import sys
            import time

            payload = pickle.loads(sys.stdin.buffer.read())
            if payload["filename"] == "stall.pdf":
                Path(os.environ["TAXAGENT_STALL_PID_FILE"]).write_text(str(os.getpid()))
                time.sleep(60)

            from taxagent.intake._pdf_worker import _run_payload

            response = _run_payload(payload)
            sys.stdout.buffer.write(json.dumps(response, separators=(",", ":")).encode())
            """
        ),
        encoding="utf-8",
    )
    src_dir = Path(__file__).resolve().parents[1] / "src"
    pythonpath = os.pathsep.join(
        [str(tmp_path), str(src_dir), os.environ.get("PYTHONPATH", "")]
    )
    pid_file = tmp_path / "stall.pid"
    monkeypatch.setenv("PYTHONPATH", pythonpath)
    monkeypatch.setenv("TAXAGENT_STALL_PID_FILE", str(pid_file))
    monkeypatch.setattr(pdf_intake, "_PDF_WORKER_MODULE", "stalling_pdf_worker")

    start = time.monotonic()
    result = pdf_intake.import_pdf_batch(
        [("valid.pdf", _text_pdf()), ("stall.pdf", b"%PDF-stalls")],
        enable_ocr=False,
        max_ocr_seconds=2.0,
    )
    elapsed = time.monotonic() - start

    assert elapsed < 6.0
    assert [document.status for document in result.documents] == [
        "processed",
        "resource_limited",
    ]
    assert result.documents[1].message == "PDF import exceeded the configured processing time limit."
    assert len(result.candidates) == 1
    assert result.candidates[0].fields["14"].value == "45000.00"

    deadline = time.monotonic() + 2.0
    stalled_pid = int(pid_file.read_text(encoding="utf-8"))
    while _process_is_running(stalled_pid) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not _process_is_running(stalled_pid)


def test_import_pdf_batch_reaps_memory_limited_worker_and_keeps_prior_valid_file(
    monkeypatch, tmp_path: Path
):
    worker = tmp_path / "memory_pdf_worker.py"
    worker.write_text(
        textwrap.dedent(
            """
            from pathlib import Path
            import json
            import os
            import pickle
            import sys

            from taxagent.intake._pdf_worker import _apply_configured_memory_limit

            if not _apply_configured_memory_limit():
                raise SystemExit(3)

            payload = pickle.loads(sys.stdin.buffer.read())
            if payload["filename"] == "oom.pdf":
                Path(os.environ["TAXAGENT_MEMORY_PID_FILE"]).write_text(str(os.getpid()))
                bytearray(int(os.environ["TAXAGENT_ALLOCATE_BYTES"]))

            sys.stdout.buffer.write(json.dumps({
                "document": {
                    "document_id": payload["document_id"],
                    "filename": payload["filename"],
                    "sha256": payload["digest"],
                    "status": "processed",
                    "page_count": 1,
                    "message": "PDF processed.",
                },
                "candidates": [],
                "ocr_pages_used": 0,
                "ocr_pixels_used": 0,
                "ocr_exhausted": False,
            }, separators=(",", ":")).encode())
            """
        ),
        encoding="utf-8",
    )
    src_dir = Path(__file__).resolve().parents[1] / "src"
    pythonpath = os.pathsep.join(
        [str(tmp_path), str(src_dir), os.environ.get("PYTHONPATH", "")]
    )
    pid_file = tmp_path / "memory.pid"
    monkeypatch.setenv("PYTHONPATH", pythonpath)
    monkeypatch.setenv("TAXAGENT_MEMORY_PID_FILE", str(pid_file))
    monkeypatch.setenv("TAXAGENT_ALLOCATE_BYTES", str(256 * 1024 * 1024))
    monkeypatch.setattr(
        intake_execution,
        "DEFAULT_WORKER_MEMORY_LIMIT_BYTES",
        96 * 1024 * 1024,
        raising=False,
    )
    monkeypatch.setattr(pdf_intake, "_PDF_WORKER_MODULE", "memory_pdf_worker")

    result = pdf_intake.import_pdf_batch(
        [("valid.pdf", _text_pdf()), ("oom.pdf", _text_pdf())],
        enable_ocr=False,
        max_ocr_seconds=10.0,
    )

    assert [document.status for document in result.documents] == [
        "processed",
        "resource_limited",
    ]
    assert result.documents[1].message == "PDF import exceeded the configured processing time limit."
    assert result.candidates == []

    deadline = time.monotonic() + 2.0
    limited_pid = int(pid_file.read_text(encoding="utf-8"))
    while _process_is_running(limited_pid) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not _process_is_running(limited_pid)
