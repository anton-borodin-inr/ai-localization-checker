"""Sequential D-038 requests with a fresh logcat barrier and a deadline."""

import base64
import json
import queue
import re
import subprocess
import threading
import time
import uuid

from l10n_checker.capture import ACTIVITY, CaptureError, Device
from l10n_checker.text_dump import canonical_bytes

EVENT = re.compile(
    r"\bL10N_SCREEN_(PANES|READY|ERROR|DUMP) ([A-Za-z0-9._-]+) "
    r"request=([A-Za-z0-9._-]+)(?: (.*))?$"
)


class HookFailure(CaptureError):
    def __init__(self, reason: str, *, terminal: bool, events: list[str]):
        super().__init__(reason)
        self.terminal = terminal
        self.events = events


class Logcat:
    """Read the buffer, then establish a unique barrier before sending a request.

    This avoids the process-start race of `logcat -T 1`: even if logcat attaches
    late, the marker remains in the buffer. Nothing before the observed marker
    can acknowledge the new request. The marker changes Android logs only.
    """

    def __init__(self, device: Device):
        self.device = device
        self.lines = queue.Queue()

    def __enter__(self):
        command = [str(self.device.adb)]
        if self.device.serial:
            command += ["-s", self.device.serial]
        try:
            self.process = subprocess.Popen(
                [*command, "logcat", "-v", "raw"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except OSError as exc:
            raise CaptureError("Could not start SDK adb logcat") from exc
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()
        try:
            marker = "L10N_CAPTURE_BARRIER_" + uuid.uuid4().hex
            self.device.shell("log", "-p", "i", "-t", "L10nCapture", marker)
            deadline = time.monotonic() + 15
            while self.next_line(deadline) != marker:
                pass
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self

    def _read(self):
        try:
            for line in self.process.stdout:
                line = line.rstrip("\r\n")
                if "L10N_SCREEN_" in line or line.startswith("L10N_CAPTURE_BARRIER_"):
                    self.lines.put(line)
        finally:
            self.lines.put(None)

    def next_line(self, deadline: float) -> str:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError
        try:
            line = self.lines.get(timeout=remaining)
        except queue.Empty as exc:
            raise TimeoutError from exc
        if line is None:
            raise CaptureError("SDK adb logcat ended before the terminal event")
        return line

    def __exit__(self, *_):
        if self.process.poll() is None:
            self.process.terminate()
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=3)
        self.reader.join(timeout=3)
        self.process.stdout.close()


def wait_terminal(
    log,
    screen: str,
    request: str,
    panes: set[str],
    deadline: float,
    protocol_version: int = 1,
):
    events = []
    actual = None
    dump = None
    dump_error = None
    while True:
        try:
            line = log.next_line(deadline)
        except TimeoutError as exc:
            raise HookFailure("client_timeout", terminal=False, events=events) from exc
        except CaptureError as exc:
            raise HookFailure(str(exc), terminal=False, events=events) from exc
        event = EVENT.search(line)
        if not event or event[2] != screen or event[3] != request:
            continue
        events.append(line)
        kind, details = event[1], event[4] or ""
        if kind == "PANES":
            match = re.fullmatch(r"panes=(.*)", details)
            actual = match[1].split(",") if match and match[1] else []
        elif kind == "DUMP":
            if protocol_version == 1:
                continue
            match = re.fullmatch(r"file=(\S+) sha256=([a-f0-9]{64})", details)
            if (
                dump is not None
                or not match
                or match[1] != f"files/l10n-hook/{request}.json"
            ):
                dump_error = "invalid_or_duplicate_dump_event"
            else:
                dump = {"file": match[1], "sha256": match[2]}
        elif kind == "ERROR":
            raise HookFailure(details, terminal=True, events=events)
        elif kind == "READY":
            # Wait for the terminal event even when PANES disagrees: never
            # supersede a request while manifest discovery is still pending.
            if actual is None or set(actual) != panes or len(actual) != len(panes):
                raise HookFailure(
                    f"pane_set_mismatch expected={sorted(panes)} actual={actual}",
                    terminal=True,
                    events=events,
                )
            frames = re.fullmatch(r"frames=(\d+)", details)
            if frames is None or int(frames[1]) < 2:
                raise HookFailure("invalid_ready_frames", terminal=True, events=events)
            result = {"events": events, "panes": actual, "frames": int(frames[1])}
            if protocol_version == 2:
                if dump_error or dump is None:
                    raise HookFailure(
                        dump_error or "missing_dump_event", terminal=True, events=events
                    )
                result["dump"] = dump
            return result


def request_screen(
    device: Device,
    screen: str,
    request: str,
    state: dict,
    timeout_s: float,
    log_factory=Logcat,
    *,
    protocol_version: int = 1,
):
    if re.fullmatch(r"[A-Za-z0-9._-]{1,64}", request) is None:
        raise CaptureError("Invalid D-038 request id")
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", screen) is None:
        raise CaptureError("Invalid D-038 screen id")
    if type(protocol_version) is not int or protocol_version not in (1, 2):
        raise CaptureError("Unsupported hook protocol version")
    payload = (
        canonical_bytes(state)
        if protocol_version == 2
        else json.dumps(
            state, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        ).encode()
    )
    encoded = base64.b64encode(payload).decode("ascii")
    panes = set(state["scroll"]) | set(state["scroll_to"])
    # All three extras contain shell-safe tokens; no raw JSON or source names
    # are interpolated into adb's remote shell command.
    try:
        with log_factory(device) as log:
            deadline = time.monotonic() + timeout_s
            arguments = [
                "am",
                "start",
                "-W",
                "-n",
                ACTIVITY,
                "--es",
                "l10n_screen",
                screen,
                "--es",
                "l10n_request",
                request,
                "--es",
                "l10n_state_b64",
                encoded,
            ]
            if protocol_version == 2:
                arguments += ["--es", "l10n_protocol", "2"]
            started = device.shell(*arguments)
            if "Status: ok" not in started:
                raise HookFailure("am_start_failed", terminal=False, events=[started])
            result = wait_terminal(
                log, screen, request, panes, deadline, protocol_version
            )
            result["am_start"] = started
            return result
    except HookFailure:
        raise
    except (CaptureError, TimeoutError) as exc:
        raise HookFailure(
            f"logcat_or_launch_failed: {exc}", terminal=False, events=[]
        ) from exc
