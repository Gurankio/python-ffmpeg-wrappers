import re
import sys
import json
import subprocess
import multiprocessing
from multiprocessing.pool import ThreadPool
from threading import Lock
from os import path
from functools import *
from operator import *
from math import *
from alive_progress import alive_bar


def probe(show_type):
    @cache
    def ffprobe(*probe_args): return json.loads(subprocess.run(probe_args, capture_output=True).stdout)

    return lambda file: \
        ffprobe('pyprobe', '-print_format', 'json', '-show_format', '-show_chapters', '-show_streams', file)[show_type]


def display_time(seconds: int) -> str:
    if seconds == 0:
        return 'start'
    hours, minutes, seconds = seconds // 3600, (seconds % 3600) // 60, (seconds % 3600) % 60
    return ((f'{hours:02}h ' if hours > 0 else '') +
            (f'{minutes:02}m ' if hours > 0 or minutes > 0 else '') +
            (f'{seconds:02}s ' if hours > 0 or minutes > 0 or seconds > 0 else '')).strip()


def display_size(byte: int) -> str:
    if byte == 0:
        return ''
    digits = len(str(byte))
    unit = [' B', 'kB', 'MB', 'GB', 'TB']
    scale = digits // 3 if digits % 3 > 1 else digits // 3 - 1
    return f'{str(byte)[0:(digits - scale * 3)].rjust(4)}{unit[scale]}'


def display_rate(rate: int) -> str:
    if rate == 0:
        return ''
    digits = len(str(rate))
    unit = [' bps', 'kbps', 'Mbps', 'Gbps', 'Tbps']
    scale = digits // 3 if digits % 3 > 1 else digits // 3 - 1
    return f'{str(rate)[0:(digits - scale * 3)].rjust(4)}{unit[scale]}'


def display_bool(boolean: bool, string: str = '*') -> str:
    return string if boolean else ' '


def display_lang(language: str) -> str:
    try:
        return "lang"  # languages.lookup(language).name
    except LookupError:
        return ''


def display_fps(fps: str) -> str:
    try:
        return f'{float(eval(fps)):.2f}fps'
    except ZeroDivisionError:
        return ''


def display_perc(percentage: float) -> str:
    if percentage == 0:
        return ' 0%'
    return f'{round(percentage * 100):2.0f}%' if percentage > (1 / 100) else f'~0%'


def display_bar(percentage: float, width: int = 30) -> str:
    fill = floor(percentage * width)
    return '|' + (' ' * (width - fill)) + ('#' * fill) + '|'


def get(dictionary: dict, path: str, default='') -> str:
    try:
        for key in path.split('.'):
            dictionary = dictionary[key]
        return dictionary
    except KeyError:
        return default


def compute_size(duration: float, streams: int, bar: [Lock, alive_bar, float], stream) -> int:
    if 'bit_rate' in stream and 'duration' in stream:
        return int(float(stream['duration']) * int(stream['bit_rate']) / 8)

    from ffmpeg import ffmpeg
    last = [0]

    def update(last, time):
        time /= duration
        time /= streams
        with bar[0]:
            bar[2] += time - last[0]
            bar[1](bar[2])
        last[0] = time

    statistics = ffmpeg(['-i', sys.argv[1], '-map', f"0:{str(stream['index'])}", '-c', 'copy', '-f', 'null', '-'],
                        time=partial(update, last))

    with bar[0]:
        bar[2] += (1 / streams) - last[0]
        bar[1](bar[2])

    return sum(statistics) if statistics is not None else 0


def pad(rows):
    columns = len(list(zip(*rows)))
    column_max = list(map(lambda x: max(map(len, x)), zip(*rows)))
    for column in range(columns):
        for row in range(len(rows)):
            rows[row][column] = rows[row][column].ljust(column_max[column])
    return columns, column_max


# TODO: argparse
# TODO: Save size info in mkv metadata.
# TODO: clean code
# TODO: automatic bar size
# TODO: if not parallel print line by line, requires large rewrite.
if __name__ == '__main__':
    FULL = True  # Process all streams
    CHAPTERS = True  # Process chapters
    SORTED = False  # Sort by size
    PARALLEL = True  # Compute size in parallel
    TECHNICAL = False  # Show technical info

    FILE = path.abspath(sys.argv[1])

    # Format
    fmt = probe('format')(FILE)
    duration = float(fmt['duration'])
    total_size = int(fmt['size'])

    # Chapters
    chapters_rows = []
    chapters = probe('chapters')(FILE)
    for chapter in chapters:
        chapters_rows.append([
            get(chapter, 'tags.title'),
            'from',
            display_time(int(float(get(chapter, 'start_time')))),
            'to',
            display_time(int(float(get(chapter, 'end_time'))))
        ])

    chapter_columns, chapter_max = pad(chapters_rows)

    # Streams
    streams = probe('streams')(FILE)
    streams = streams if FULL else list(filter(lambda s: s['codec_type'] != 'attachment', streams))

    # > Pictures
    for stream in streams:
        if bool(int(get(stream, 'disposition.attached_pic'))):
            stream['codec_type'] = 'picture'

    # > Sizes
    with alive_bar(title='Computing sizes', theme='smooth', enrich_print=False,
                   total=len(streams) * 100, manual=True, calibrate=1) as bar:
        pool = ThreadPool(processes=min(multiprocessing.cpu_count(), len(streams)) if PARALLEL else 1)
        sizes = pool.map(partial(compute_size, duration, len(streams), [Lock(), bar, 0]), streams)
        bar(1)

    # > Sorting
    data = zip(streams, sizes)
    if SORTED:
        data = sorted(data, key=itemgetter(1), reverse=True)

    # > Paging
    streams_rows = []
    for stream, size in data:
        bitrate = (size * 8) / duration
        percentage = size / total_size

        match stream['codec_type']:
            case 'video':
                streams_rows.append([
                    display_bool(bool(int(get(stream, 'disposition.default')))),
                    display_lang(get(stream, 'tags.language')),
                    get(stream, 'codec_name').upper(),
                    str(get(stream, 'width')) + 'x' + str(get(stream, 'height')),
                    display_fps(get(stream, 'avg_frame_rate')),
                    'video',
                    'at ' + display_rate(int(bitrate)),
                    display_bar(percentage),
                    display_perc(percentage),
                    display_size(size)
                ])

            case 'picture':
                streams_rows.append([
                    display_bool(bool(int(get(stream, 'disposition.default')))),
                    display_lang(get(stream, 'tags.language')),
                    get(stream, 'codec_name').upper(),
                    str(get(stream, 'width')) + 'x' + str(get(stream, 'height')),
                    '',
                    'picture',
                    '',
                    display_bar(percentage),
                    display_perc(percentage),
                    display_size(size)
                ])

            case 'audio':
                streams_rows.append([
                    display_bool(bool(int(get(stream, 'disposition.default')))),
                    display_lang(get(stream, 'tags.language')),
                    get(stream, 'codec_name').upper(),
                    str(get(stream, 'sample_rate')) + 'Hz',
                    str(get(stream, 'channels')) + 'ch',
                    'audio',
                    'at ' + display_rate(int(bitrate)),
                    display_bar(percentage),
                    display_perc(percentage),
                    display_size(size)
                ])

            case 'subtitle':
                streams_rows.append([
                    display_bool(bool(int(get(stream, 'disposition.default')))),
                    display_lang(get(stream, 'tags.language')),
                    get(stream, 'codec_name').upper(),
                    '',
                    '',
                    'subtitles',
                    '',
                    display_bar(percentage),
                    display_perc(percentage),
                    display_size(size)
                ])

            case 'attachment':
                streams_rows.append([
                    display_bool(bool(int(get(stream, 'disposition.default')))),
                    get(stream, 'tags.filename'),
                    get(stream, 'codec_name').upper(),
                    '',
                    '',
                    'attachment',
                    '',
                    display_bar(percentage),
                    display_perc(percentage),
                    display_size(size)
                ])

        if TECHNICAL:
            extra = [
                format(get(stream, 'index'), '02')
            ]
            extra.extend(streams_rows[-1])
            streams_rows[-1] = extra

    stream_columns, stream_max = pad(streams_rows)

    # Output
    print(path.basename(fmt["filename"]))
    general = f'{fmt["format_long_name"]}, {display_time(int(duration))} long'
    total_size = display_size(total_size)
    padding = sum(stream_max) + stream_columns - 1 - len(general) - len(total_size)
    print(general + ' ' * padding + total_size)
    for row in streams_rows:
        print(' '.join(row))
    if CHAPTERS:
        for row in chapters_rows:
            print(' '.join(row))
