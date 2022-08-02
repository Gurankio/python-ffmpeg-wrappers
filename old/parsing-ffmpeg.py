import json
import re
import subprocess
import sys
from functools import *
from operator import *
from queue import Queue, Empty
from subprocess import Popen, DEVNULL, PIPE
from threading import Thread

from alive_progress import alive_bar


def probe(show_type):
    @cache
    def ffprobe(*probe_args): return json.loads(subprocess.run(probe_args, capture_output=True).stdout)
    return lambda file: ffprobe('pyprobe', '-print_format', 'json', '-show_format', '-show_chapters', '-show_streams', file)[show_type]


def ffmpeg(description=None, show_streams=True, *args):
    def is_input(arg_pair):
        return arg_pair[0] == '-i'

    command = ['run', '-progress', '-', '-nostats', '-y', *args]
    files = list(map(itemgetter(1), filter(is_input, zip(command, command[1:] + [None]))))
    duration = max(map(float, map(itemgetter('duration'), map(probe('format'), files))))
    streams = list(zip(files, map(probe('streams'), files)))

    if show_streams:
        for file, stream in streams:
            print(f"{file}: {', '.join([str(s['index'])+'-'+s['codec_name'].upper()+('('+s['tags']['language'].upper()+')' if 'language' in s['tags'] else '') for s in stream])}")

    queue = Queue()

    def reader(stream, queue):
        while line := stream.readline().decode('UTF-8').rstrip():
            queue.put(line)

    mapping = re.compile(r"(\s\s.+?->.+?\(.+?(?:\s\(.+?\)\s->\s.+?\s\(.+?\))?\))")
    frame = re.compile(r"frame=(\d+)")
    out_time = re.compile(r"out_time_ms=(\d+)")
    speed = re.compile(r"speed=(\s*\d+.\d+x)")

    process = Popen(command, stdin=DEVNULL, stdout=PIPE, stderr=PIPE, bufsize=0)
    try:
        stderr = Thread(target=reader, args=(process.stderr, queue))
        stderr.setDaemon(True)
        stderr.start()

        stdout = Thread(target=reader, args=(process.stdout, queue))
        stdout.setDaemon(True)
        stdout.start()

        with alive_bar(title=description, theme='classic', enrich_print=False,
                       total=int(duration), manual=True, calibrate=50) as bar:
            while process.poll() is None:
                try:
                    output = queue.get(timeout=1)

                    if show_streams and (match := mapping.match(output)):
                        print(match.groups()[0].lstrip())

                    if match := frame.match(output):
                        pass

                    if match := out_time.match(output):
                        bar(int(float(match.groups()[0]) / 1_000_000) / duration)

                    if match := speed.match(output):
                        pass

                except Empty:
                    pass
    finally:
        process.kill()


if __name__ == '__main__':
    ffmpeg("Sasso", False, *sys.argv[1:])
