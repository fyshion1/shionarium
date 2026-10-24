"""Nonblocking process lock; never read a byte held by another Windows process."""
import os


def acquire(file):
    file.seek(0)
    try:
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    # Initialization happens only after locking. Reading first fails on Windows.
    if os.fstat(file.fileno()).st_size == 0:
        file.write(b'0')
        file.flush()
    return True
