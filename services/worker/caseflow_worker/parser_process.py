"""Private child process: install OS limits before importing the PDF parser."""
import json
import os
import sys

_job_handle = None


def limits():
    global _job_handle
    memory = 512 * 1024 * 1024
    if os.name == "nt":
        import ctypes as c
        from ctypes import wintypes as w
        class Basic(c.Structure):
            _fields_ = [("process_time", c.c_int64), ("job_time", c.c_int64),
                        ("flags", w.DWORD), ("min_ws", c.c_size_t), ("max_ws", c.c_size_t),
                        ("active", w.DWORD), ("affinity", c.c_size_t), ("priority", w.DWORD), ("scheduling", w.DWORD)]
        class IO(c.Structure):
            _fields_ = [(n, c.c_uint64) for n in ("read_ops", "write_ops", "other_ops", "read_bytes", "write_bytes", "other_bytes")]
        class Extended(c.Structure):
            _fields_ = [("basic", Basic), ("io", IO), ("process_memory", c.c_size_t),
                        ("job_memory", c.c_size_t), ("peak_process", c.c_size_t), ("peak_job", c.c_size_t)]
        kernel = c.WinDLL("kernel32", use_last_error=True)
        kernel.CreateJobObjectW.argtypes = [c.c_void_p, w.LPCWSTR]
        kernel.CreateJobObjectW.restype = w.HANDLE
        kernel.SetInformationJobObject.argtypes = [w.HANDLE, c.c_int, c.c_void_p, w.DWORD]
        kernel.SetInformationJobObject.restype = w.BOOL
        kernel.GetCurrentProcess.restype = w.HANDLE
        kernel.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
        kernel.AssignProcessToJobObject.restype = w.BOOL
        _job_handle = kernel.CreateJobObjectW(None, None)
        info = Extended()
        info.basic.flags = 0x100 | 0x8  # PROCESS_MEMORY and ACTIVE_PROCESS
        info.basic.active = 1
        info.process_memory = memory
        if not _job_handle or not kernel.SetInformationJobObject(_job_handle, 9, c.byref(info), c.sizeof(info)):
            raise RuntimeError("Memory limit unavailable")
        if not kernel.AssignProcessToJobObject(_job_handle, kernel.GetCurrentProcess()):
            raise RuntimeError("Process limit unavailable")
    else:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
        resource.setrlimit(resource.RLIMIT_CPU, (15, 15))


if __name__ == "__main__":
    limits()  # Fail closed if this host cannot enforce parser isolation.
    from .parsing import MAX_BYTES, parse
    try:
        result = parse(sys.stdin.buffer.read(MAX_BYTES + 1), sys.argv[1])
    except (ValueError, MemoryError) as error:
        # Never return parser exception text: malformed files may contain sensitive content.
        known = {"SOURCE_SIZE_LIMIT", "INVALID_UTF8", "BINARY_TEXT_UNSUPPORTED", "MALFORMED_PDF",
                 "ENCRYPTED_PDF_UNSUPPORTED", "SOURCE_PAGE_LIMIT", "PDF_STREAM_LIMIT",
                 "SOURCE_TEXT_LIMIT", "UNSUPPORTED_SOURCE_TYPE", "NO_EXTRACTABLE_TEXT"}
        result = {"error": str(error) if str(error) in known else "PARSER_RESOURCE_LIMIT"}
    sys.stdout.buffer.write(json.dumps(result, ensure_ascii=True).encode())
