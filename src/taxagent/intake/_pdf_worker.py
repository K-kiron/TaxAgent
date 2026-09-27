"""Subprocess entry point for one local PDF import."""

from __future__ import annotations

import ctypes
import json
import os
import pickle
import sys
from typing import Any

WORKER_MEMORY_LIMIT_ENV = "TAXAGENT_PDF_WORKER_MEMORY_LIMIT_BYTES"
_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
_JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x100
_JOB_OBJECT_LIMIT_JOB_MEMORY = 0x200
_WINDOWS_JOB_HANDLE: int | None = None


def _run_payload(payload: dict[str, Any]) -> dict[str, Any]:
    from .pdf import OcrSession, _import_one_pdf

    ocr_session = OcrSession(
        int(payload["max_ocr_pages"]),
        int(payload["max_rendered_pixels"]),
        float(payload["max_ocr_seconds"]),
    )
    document, candidates = _import_one_pdf(
        str(payload["document_id"]),
        str(payload["filename"]),
        str(payload["digest"]),
        bytes(payload["pdf_bytes"]),
        max_pages=int(payload["max_pages"]),
        enable_ocr=bool(payload["enable_ocr"]),
        ocr_session=ocr_session,
    )
    return {
        "document": document.model_dump(mode="json"),
        "candidates": [candidate.model_dump(mode="json") for candidate in candidates],
        "ocr_pages_used": ocr_session.pages_used,
        "ocr_pixels_used": ocr_session.pixels_used,
        "ocr_exhausted": ocr_session.exhausted,
    }


def _apply_configured_memory_limit() -> bool:
    raw_limit = os.environ.get(WORKER_MEMORY_LIMIT_ENV)
    if not raw_limit:
        return True
    try:
        limit_bytes = int(raw_limit)
    except ValueError:
        return False
    if limit_bytes <= 0:
        return False

    if os.name == "nt":
        return _apply_windows_job_memory_limit(limit_bytes)
    if sys.platform.startswith("linux"):
        return _apply_linux_address_space_limit(limit_bytes)
    return False


def _apply_linux_address_space_limit(limit_bytes: int) -> bool:
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (limit_bytes, limit_bytes))
    except (OSError, ValueError):
        return False
    return True


def _apply_windows_job_memory_limit(limit_bytes: int) -> bool:
    global _WINDOWS_JOB_HANDLE

    class IoCounters(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_ulonglong),
            ("WriteOperationCount", ctypes.c_ulonglong),
            ("OtherOperationCount", ctypes.c_ulonglong),
            ("ReadTransferCount", ctypes.c_ulonglong),
            ("WriteTransferCount", ctypes.c_ulonglong),
            ("OtherTransferCount", ctypes.c_ulonglong),
        ]

    class BasicLimitInformation(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong),
            ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", ctypes.c_ulong),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", ctypes.c_ulong),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", ctypes.c_ulong),
            ("SchedulingClass", ctypes.c_ulong),
        ]

    class ExtendedLimitInformation(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", BasicLimitInformation),
            ("IoInfo", IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
    kernel32.CreateJobObjectW.restype = ctypes.c_void_p
    kernel32.SetInformationJobObject.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_ulong,
    ]
    kernel32.SetInformationJobObject.restype = ctypes.c_int
    kernel32.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    kernel32.AssignProcessToJobObject.restype = ctypes.c_int
    kernel32.GetCurrentProcess.argtypes = []
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int

    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        return False

    info = ExtendedLimitInformation()
    info.BasicLimitInformation.LimitFlags = (
        _JOB_OBJECT_LIMIT_PROCESS_MEMORY | _JOB_OBJECT_LIMIT_JOB_MEMORY
    )
    info.ProcessMemoryLimit = limit_bytes
    info.JobMemoryLimit = limit_bytes
    if not kernel32.SetInformationJobObject(
        job,
        _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
        ctypes.byref(info),
        ctypes.sizeof(info),
    ):
        kernel32.CloseHandle(job)
        return False

    if not kernel32.AssignProcessToJobObject(job, kernel32.GetCurrentProcess()):
        kernel32.CloseHandle(job)
        return False

    _WINDOWS_JOB_HANDLE = job
    return True


def main() -> int:
    if not _apply_configured_memory_limit():
        return 2
    payload = pickle.loads(sys.stdin.buffer.read())
    sys.stdout.buffer.write(json.dumps(_run_payload(payload), separators=(",", ":")).encode())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
