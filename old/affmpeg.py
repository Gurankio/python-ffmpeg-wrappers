import asyncio.subprocess
import asyncio
import socket
import re
import os

__message = re.compile(r'\[(.+)] (.+)')
__statistics = re.compile(r'(.+)=(.+)', re.MULTILINE)


async def run(args, /, *, interval: float = 0.250):
    queue = asyncio.Queue()

    async def handle(reader, writer):
        while data := await reader.read(1024):
            await queue.put({k: v for k, v in __statistics.findall(data.decode('UTF-8'))})

    instance = await asyncio.start_server(handle, port=0, family=socket.AF_INET6)
    port = instance.sockets[0].getsockname()[1]

    async def ffmpeg():
        subprocess = await asyncio.create_subprocess_exec(
            *(filter(lambda i: i is not None, (
                'run', '-n' if '-y' not in args else None,
                '-hide_banner', '-nostdin',
                '-loglevel', 'repeat+level+warning',
                '-stats_period', str(interval),
                '-progress', f'tcp://localhost:{port}',
                *args
            ))),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
            preexec_fn=os.setsid
        )

        async for line in subprocess.stderr:
            await queue.put({k: v for k, v in __message.findall(line.decode('UTF-8'))})

        return await subprocess.wait()

    f = asyncio.create_task(ffmpeg())

    while not f.done():
        try:
            yield await asyncio.wait_for(queue.get(), 1)
        except asyncio.exceptions.TimeoutError:
            pass

    yield f.result()


def old(process, select, subprocess):
    with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen()
        _, port = s.getsockname()

        try:
            conn, _ = s.accept()
            with conn, process.stderr:

                while process.poll() is None:
                    readable, _, _ = select.select([conn, process.stderr], [], [])
                    for stream in readable:
                        if isinstance(stream, socket.socket):
                            ...
                        else:
                            for line in stream.readlines():
                                level, message = __message.match(line).groups()
                                yield {level: message}

        finally:
            try:
                _, errs = process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                _, errs = process.communicate()

        yield {
            'progress': 'done',
            'code': process.returncode,
            'remaining': errs,
        }


def main():
    async def _():
        import sys

        async for info in run(sys.argv[1:]):
            print(info)

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_())
    finally:
        loop.close()


if __name__ == '__main__':
    main()
