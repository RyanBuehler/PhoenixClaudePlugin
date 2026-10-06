#!/usr/bin/env python3
"""Run one console command in a running Phoenix engine over its console pipe and print the answer.

An engine started with --console-pipe=PATH listens for console lines. A line opened with the reply
header, `--reply -- <command>`, is run on the cycle thread and answered on the connection it came on:
a decimal byte count, a newline, then that many bytes, which read `OK <value>` or `ERR <message>`.
Only commands their author opened to agents run; the rest are refused with an ERR.

Where the answer travels differs by platform, and nothing else does:

  Linux    PATH is the FIFO; the answer comes back over the AF_UNIX socket at PATH.sock.
  Windows  PATH must be a named pipe, \\\\.\\pipe\\NAME, given to the engine verbatim.

  console_pipe.py send --pipe PATH [--wait SECONDS] -- <command...>

Exit status: 0 the engine answered OK, 1 it answered ERR, 2 misuse, 3 no engine answered -- none was
listening on PATH within --wait, or the connection ended before a whole answer arrived.
"""

import argparse
import os
import socket
import sys
import threading
import time

ANSWERED = 0
REFUSED = 1
MISUSED = 2
UNANSWERED = 3

REPLY_HEADER = "--reply --"
WINDOWS_PIPE_PREFIXES = ("\\\\.\\pipe\\", "//./pipe/")
SOCKET_SUFFIX = ".sock"

# The engine answers a command it could not run within 5 s itself, so a reply slower than this means
# the engine is gone or wedged, not busy.
DEFAULT_REPLY_SECONDS = 15.0
CONNECT_RETRY_SECONDS = 0.25
# A count longer than this is not a byte count, and reading on would wait for bytes that never come.
MAX_COUNT_DIGITS = 20


class NoAnswer(Exception):
	"""No engine answered: nothing listened on the pipe, or the connection ended mid-answer."""


def ComposeRequest(command):
	"""The line that asks for an answer. A command spanning lines would run as several, so it is refused."""
	text = command.strip()
	if not text:
		raise ValueError("no command to send")
	if "\n" in text or "\r" in text:
		raise ValueError("a console command is one line")
	return f"{REPLY_HEADER} {text}\n".encode("utf-8")


def ReadAnswer(read):
	"""Read one length-framed answer through read(n), which returns at most n bytes and b"" at the end."""
	digits = b""
	while True:
		byte = read(1)
		if not byte:
			raise NoAnswer("the connection ended before the answer's byte count")
		if byte == b"\n":
			break
		if not byte.isdigit() or len(digits) >= MAX_COUNT_DIGITS:
			raise NoAnswer(f"the answer did not open with a byte count: {digits + byte!r}")
		digits += byte
	if not digits:
		raise NoAnswer("the answer's byte count was empty")
	remaining = int(digits)
	payload = bytearray()
	while remaining > 0:
		chunk = read(remaining)
		if not chunk:
			raise NoAnswer(f"the connection ended {remaining} bytes short of the answer")
		payload += chunk
		remaining -= len(chunk)
	return payload.decode("utf-8", errors="replace")


def ClassifyAnswer(payload):
	"""The exit status an answer earns: OK is answered, anything else is the engine refusing."""
	return ANSWERED if payload == "OK" or payload.startswith("OK ") else REFUSED


def IsWindowsPipeName(path):
	return path.startswith(WINDOWS_PIPE_PREFIXES)


def ConnectPosix(path, deadline):
	socket_path = path + SOCKET_SUFFIX
	while True:
		connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
		try:
			connection.connect(socket_path)
			return connection
		except OSError as error:
			connection.close()
			if time.monotonic() >= deadline:
				raise NoAnswer(f"no engine is listening on the console pipe {path} ({socket_path}: {error.strerror})") from error
		time.sleep(CONNECT_RETRY_SECONDS)


def ConnectWindows(path, deadline):
	while True:
		try:
			return open(path, "r+b", buffering=0)
		except OSError as error:
			# Absent until the engine creates it, and busy while every instance serves another client.
			if time.monotonic() >= deadline:
				raise NoAnswer(f"no engine is listening on the console pipe {path} ({error.strerror or error})") from error
		time.sleep(CONNECT_RETRY_SECONDS)


def ReadWithin(read, seconds):
	"""ReadAnswer, bounded: a named pipe read cannot time out on its own, so the read runs on a thread."""
	outcome = {}

	def Run():
		try:
			outcome["payload"] = ReadAnswer(read)
		except (NoAnswer, OSError) as error:
			outcome["error"] = error

	reader = threading.Thread(target=Run, daemon=True)
	reader.start()
	reader.join(seconds)
	if reader.is_alive():
		raise NoAnswer(f"no answer arrived within {seconds:g} s")
	if "error" in outcome:
		error = outcome["error"]
		raise error if isinstance(error, NoAnswer) else NoAnswer(f"the answer could not be read: {error}")
	return outcome["payload"]


def Send(path, command, wait_seconds, reply_seconds):
	"""Send one command and return the engine's answer text. Raises NoAnswer when no engine answers."""
	request = ComposeRequest(command)
	deadline = time.monotonic() + wait_seconds
	if os.name == "nt":
		if not IsWindowsPipeName(path):
			raise ValueError(f"on Windows the console pipe is a named pipe, \\\\.\\pipe\\NAME, not {path}")
		with ConnectWindows(path, deadline) as pipe:
			pipe.write(request)
			pipe.flush()
			return ReadWithin(pipe.read, reply_seconds)
	connection = ConnectPosix(path, deadline)
	with connection:
		connection.sendall(request)
		connection.settimeout(reply_seconds)
		try:
			return ReadAnswer(lambda count: connection.recv(count))
		except socket.timeout as error:
			raise NoAnswer(f"no answer arrived within {reply_seconds:g} s") from error


def Main(argv):
	parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
	sub = parser.add_subparsers(dest="action", required=True)
	send = sub.add_parser("send", help="run one command and print its answer")
	send.add_argument("--pipe", required=True, help="the path the engine was given as --console-pipe")
	send.add_argument("--wait", type=float, default=0.0,
		help="seconds to keep trying while no engine listens yet, as while one starts (default: try once)")
	send.add_argument("--reply-timeout", type=float, default=DEFAULT_REPLY_SECONDS,
		help="seconds to wait for the answer once connected")
	send.add_argument("command", nargs=argparse.REMAINDER)
	args = parser.parse_args(argv)

	words = args.command[1:] if args.command[:1] == ["--"] else args.command
	try:
		answer = Send(args.pipe, " ".join(words), max(args.wait, 0.0), args.reply_timeout)
	except ValueError as error:
		print(f"console_pipe: {error}", file=sys.stderr)
		return MISUSED
	except NoAnswer as error:
		print(f"console_pipe: {error}", file=sys.stderr)
		return UNANSWERED
	print(answer)
	return ClassifyAnswer(answer)


if __name__ == "__main__":
	sys.exit(Main(sys.argv[1:]))
