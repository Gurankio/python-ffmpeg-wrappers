import subprocess
import socket
import select
import re
import os
from typing import Generator, Any

__progress = re.compile(r'(.+)=(.+)', re.MULTILINE)
__log = re.compile(r'(?:\[(.+ @ .+)] )?\[(.+)] (.+)')


def __recv_progress(stream):
    return stream.recv(1024).decode('UTF-8')


def __handle_progress(line: str):
    if line:
        packet = {k: v for k, v in __progress.findall(line)}
        match packet:
            case {
                'frame': frame,
                'fps': fps,
                'bitrate': bitrate,
                'total_size': size,
                'out_time_us': us,
                'out_time_ms': ms,
                'out_time': _,
                'dup_frames': duplicated,
                'drop_frames': dropped,
                'speed': speed,
                'progress': progress,
                **streams_qualities
            }:
                return {
                    'frame': int(frame),
                    'fps': float(fps),
                    'bitrate': int(float(bitrate[:-7]) * 1000) if bitrate != 'N/A' else None,
                    'total_size': int(size) if size != 'N/A' else None,
                    'out_time_us': int(us),
                    'out_time_ms': int(ms) // 1000,
                    'dup_frames': int(duplicated),
                    'drop_frames': int(dropped),
                    'speed': float(speed[:-1]) if speed != 'N/A' else None,
                    'progress': progress,  # TODO: enum
                    **{stream: float(quality) for stream, quality in streams_qualities.items()}
                }

            case _:
                return {'error': f'Unknown progress info.', 'packet': packet}


def __recv_logs(stream):
    return stream.readline().strip()


def __handle_logs(line):
    if match := __log.match(line):
        sender, level, message = match.groups()
        if sender is None:
            return {'level': level, 'message': message}
        else:
            return {'level': level, 'message': message, 'sender': sender}
    else:
        return {'level': 'unknown', 'message': line}


def run(args: list[str], /, *, loglevel: str, interval: float) -> Generator[dict[str, Any], None, None]:
    with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as server:
        server.bind(('', 0))
        server.listen()
        server.settimeout(2)
        port = server.getsockname()[1]

        process = subprocess.Popen(
            tuple(filter(lambda i: i is not None, (
                'run', '-n' if '-y' not in args else None,
                '-hide_banner', '-nostdin', '-nostats',
                '-loglevel', f'repeat+level+{loglevel}',
                '-stats_period', str(interval),
                '-progress', f'tcp://localhost:{port}',
                *args
            ))),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding='UTF-8',
            universal_newlines=True,
            bufsize=1,
            preexec_fn=os.setsid
        )

        try:
            connection, _ = server.accept()

            handlers = {
                connection: lambda stream: __handle_progress(__recv_progress(stream)),
                process.stdout: lambda stream: __handle_logs(__recv_logs(stream)),
                process.stderr: lambda stream: __handle_logs(__recv_logs(stream)),
            }

            while process.poll() is None:
                readable, _, _ = select.select(handlers.keys(), [], [])
                yield from filter(lambda i: i is not None, (handlers[stream](stream) for stream in readable))

        except TimeoutError:
            process.kill()

        finally:
            connection.close()

            try:
                code = process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                code = process.wait()

        outs, errs = process.communicate()
        yield from (__handle_logs(line) for line in outs.splitlines() + errs.splitlines())
        yield {'code': code}
