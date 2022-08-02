import re
from operator import *
from functools import *
from queue import Queue, Empty
from subprocess import Popen, DEVNULL, PIPE
from threading import Thread


def ffmpeg(args: list, mapping=None, frame=None, time=None, speed=None) -> (int, int, int, int, int):
    def noop(value):
        pass

    mapping = mapping if mapping is not None else noop
    frame = frame if frame is not None else noop
    time = time if time is not None else noop
    speed = speed if speed is not None else noop

    command = ['run', '-hide_banner', '-progress', '-', '-nostats', '-hwaccel', 'auto', '-y', *args]

    # Realtime.
    def monitor(input, output):
        try:
            for data in iter(input.readline, ''):
                output.put(data)
        except ValueError:
            pass

    is_mapping = re.compile(r"(\s\s.+?->.+?\(.+?(?:\s\(.+?\)\s->\s.+?\s\(.+?\))?\))")
    is_frame = re.compile(r"frame=(\d+)")
    is_out_time = re.compile(r"out_time_ms=(\d+)")
    is_speed = re.compile(r"speed=(\s*\d+.\d+x)")
    is_results = re.compile(r".+?:(\d+)kB\s?")

    def parse(output, statistics):
        if match := is_mapping.match(output):
            mapping(match.groups()[0].lstrip())

        if match := is_frame.match(output):
            frame(match.groups()[0].lstrip())

        if match := is_out_time.match(output):
            time(float(match.groups()[0]) / 1_000_000)

        if match := is_speed.match(output):
            speed(match.groups()[0].lstrip())

        if len(match := is_results.findall(output)) > 0:
            statistics[0] = tuple(map(lambda x: x * 1000, map(int, match)))

    queue = Queue()
    statistics = [0]

    process = Popen(command, stdin=DEVNULL, stdout=PIPE, stderr=PIPE, bufsize=0, text=True)
    try:
        Thread(target=monitor, args=(process.stdout, queue)).start()
        Thread(target=monitor, args=(process.stderr, queue)).start()
        while process.poll() is None or not queue.empty():
            try:
                parse(queue.get(timeout=1), statistics)
            except Empty:
                pass
    except KeyboardInterrupt:
        raise KeyboardInterrupt
    finally:
        process.wait()

    return statistics[0]


def display_size(byte: int) -> str:
    if byte == 0:
        return '  0?'
    digits = len(str(byte))
    unit = [' B', 'kB', 'MB', 'GB', 'TB']
    scale = digits // 3 if digits % 3 > 1 else digits // 3 - 1
    return f'{str(byte)[0:(digits - scale * 3)].rjust(4)}{unit[scale]}'


def main(command):
    import json
    import subprocess
    from functools import cache
    from alive_progress import alive_bar

    show_streams = True

    def probe(show_type):
        @cache
        def ffprobe(*probe_args): return json.loads(subprocess.run(probe_args, capture_output=True).stdout)

        return lambda f: \
            ffprobe('pyprobe', '-print_format', 'json', '-show_format', '-show_chapters', '-show_streams', f)[show_type]

    files = list(map(itemgetter(1), filter(lambda p: p[0] == '-i', zip(command, command[1:] + ['']))))
    duration = max(map(float, map(itemgetter('duration'), map(probe('format'), files))))
    streams = list(zip(files, map(probe('streams'), files)))

    if show_streams:
        for file, stream in streams:
            print(
                f"{file}: {', '.join([str(s['index']) + '-' + s['codec_name'].upper() + ('(' + s['tags']['language'].upper() + ')' if 'language' in s['tags'] else '') for s in stream])}")

    def percentage(bar, time):
        bar(time / duration)

    with alive_bar(title='', theme='smooth', enrich_print=False,
                   total=int(duration), manual=True, calibrate=50) as bar:
        statistics = ffmpeg(command, time=partial(percentage, bar), mapping=print)
    print(f'Total size written: {display_size(sum(statistics))}')


if __name__ == '__main__':
    import sys

    main(sys.argv[1:])
