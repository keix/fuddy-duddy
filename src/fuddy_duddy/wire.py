"""Reference parser for the collector wire protocol (SPEC.md).

This module is part of the harness: it is the trusted reader used to verify
the C tracer's output, so it stays human-maintained.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class WireEnter:
    pid: int
    ts: int
    nr: int
    args: tuple[int, int, int, int, int, int]
    strings: dict[int, str]


@dataclass(frozen=True)
class WireExit:
    pid: int
    ts: int
    ret: int
    err: bool


@dataclass(frozen=True)
class WireExited:
    pid: int
    ts: int
    code: int


@dataclass(frozen=True)
class WireSignaled:
    pid: int
    ts: int
    sig: int


WireEvent = WireEnter | WireExit | WireExited | WireSignaled


def unescape(token: str) -> str:
    """Decode %xx escapes back into bytes, then into str."""
    out = bytearray()
    i = 0
    while i < len(token):
        char = token[i]
        if char == "%":
            if i + 2 >= len(token):
                raise ValueError(f"truncated escape in {token!r}")
            out.append(int(token[i + 1 : i + 3], 16))
            i += 3
        else:
            out.append(ord(char))
            i += 1
    return out.decode("utf-8", "surrogateescape")


def _fields(tokens: list[str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for token in tokens:
        key, sep, value = token.partition("=")
        if not sep:
            raise ValueError(f"malformed field {token!r}")
        fields[key] = value
    return fields


def parse_line(line: str) -> WireEvent:
    tokens = line.split()
    if not tokens:
        raise ValueError("empty line")
    kind, fields = tokens[0], _fields(tokens[1:])
    try:
        if kind == "ENTER":
            args = tuple(int(a, 16) for a in fields["args"].split(","))
            if len(args) != 6:
                raise ValueError(f"expected 6 args, got {len(args)}")
            strings = {
                int(key[3:]): unescape(value)
                for key, value in fields.items()
                if key.startswith("str")
            }
            return WireEnter(
                pid=int(fields["pid"]),
                ts=int(fields["ts"]),
                nr=int(fields["nr"]),
                args=(args[0], args[1], args[2], args[3], args[4], args[5]),
                strings=strings,
            )
        if kind == "EXIT":
            return WireExit(
                pid=int(fields["pid"]),
                ts=int(fields["ts"]),
                ret=int(fields["ret"]),
                err=fields["err"] == "1",
            )
        if kind == "EXITED":
            return WireExited(pid=int(fields["pid"]), ts=int(fields["ts"]), code=int(fields["code"]))
        if kind == "SIGNALED":
            return WireSignaled(pid=int(fields["pid"]), ts=int(fields["ts"]), sig=int(fields["sig"]))
    except KeyError as missing:
        raise ValueError(f"missing field {missing} in {line!r}") from None
    raise ValueError(f"unknown event kind {kind!r}")
