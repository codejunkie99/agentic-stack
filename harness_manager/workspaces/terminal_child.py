"""Set up a controlling PTY in a fresh interpreter, then exec the interactive CLI.

No preexec_fn runs in the threaded control service. This helper is not an RPC.
"""
import fcntl
import os
import sys
import termios


def main():
    os.setsid()
    fcntl.ioctl(0, termios.TIOCSCTTY, 0)
    os.execvpe(sys.argv[1], sys.argv[1:], os.environ)


if __name__ == "__main__":
    main()
