import json
import os
import subprocess
import sys
import re
import warnings
from operator import itemgetter
from subprocess import PIPE, Popen
from threading import Lock
from tqdm.auto import tqdm
from concurrent.futures import ThreadPoolExecutor

global_bar_values = []
global_bar = None
global_bar_lock = Lock()

pause = []
pause_lock = Lock()


def parallel(pool_size, descriptions, commands, durations):
    if len(commands) == 0:
        return

    warnings.filterwarnings('ignore')
    frame = re.compile(r"frame=(\d+)")
    out_time = re.compile(r"out_time_ms=(\d+)")
    speed = re.compile(r"speed=(\s*\d+.\d+x)")

    def run_command(desc, command, duration):
        jid = None
        bar = tqdm(total=1, leave=False, nrows=2, dynamic_ncols=True,
                   desc=desc, bar_format="{l_bar}{bar} [{elapsed}<{remaining}{postfix}]")
        process = Popen(command, stdout=PIPE, bufsize=1)

        while process.poll() is None:
            output = process.stdout.readline().decode('ascii').strip()
            if match := frame.match(output):
                pass

            if match := out_time.match(output):
                bar.n = int(match.groups()[0]) / 1_000_000 / duration
                bar.refresh()

                with global_bar_lock:
                    global global_bar, global_bar_values
                    if jid is None:
                        jid = len(global_bar_values)
                        global_bar_values.append(0)
                    global_bar_values[jid] = bar.n
                    global_bar.n = sum(global_bar_values)
                    global_bar.refresh()

            if match := speed.match(output):
                bar.set_postfix_str(match.groups()[0], refresh=True)

        bar.n = 1
        bar.refresh()
        bar.close()

    with ThreadPoolExecutor(max_workers=min(len(commands), pool_size)) as executor:
        for desc, command, duration in zip(descriptions, commands, durations):
            executor.submit(run_command, desc, command, duration)


def parse(jobs, ignored, codecs):
    for file in sys.argv[1:]:
        if not os.path.exists(file):
            continue
        data = json.loads(
            subprocess.run(['pyprobe', file, '-hide_banner', '-print_format', 'json', '-show_format', '-show_streams'],
                           capture_output=True).stdout)
        duration = float(data['format']['duration'])
        ignored[file] = []
        for stream in data['streams']:
            outfile = file.replace('.mkv', f' - {stream["codec_type"]}{stream["index"]}.mkv')
            if (t := stream['codec_type']) == 'video':
                jobs[t].append((file, duration,
                                ['run', '-hide_banner', '-loglevel', '0', '-progress', '-', '-nostats', '-i', file,
                                 '-map', f'0:{stream["index"]}', *codecs, '-y', outfile], outfile))
            elif (t := stream['codec_type']) == 'audio':
                jobs[t].append((file, duration,
                                ['run', '-hide_banner', '-loglevel', '0', '-progress', '-', '-nostats', '-i', file,
                                 '-map', f'0:{stream["index"]}', *codecs, '-y', outfile], outfile))
            elif (t := stream['codec_type']) == 'subtitle':
                jobs[t].append((file, duration,
                                ['run', '-hide_banner', '-loglevel', '0', '-progress', '-', '-nostats', '-i', file,
                                 '-map', f'0:{stream["index"]}', *codecs, '-y', outfile], outfile))
            else:
                ignored[file] += [stream['index']]


def encode(jobs):
    parallel(4, [f"Video: {f}" for f in list(map(itemgetter(0), jobs['video']))],
             list(map(itemgetter(2), jobs['video'])),
             list(map(itemgetter(1), jobs['video'])))
    parallel(4, [f"Audio: {f}" for f in list(map(itemgetter(0), jobs['audio']))],
             list(map(itemgetter(2), jobs['audio'])),
             list(map(itemgetter(1), jobs['audio'])))
    parallel(16, [f"Subtitle: {f}" for f in list(map(itemgetter(0), jobs['subtitle']))],
             list(map(itemgetter(2), jobs['subtitle'])),
             list(map(itemgetter(1), jobs['subtitle'])))


def concat(jobs, ignored):
    names = []
    commands = []
    durations = []
    for file in sys.argv[1:]:
        if not os.path.exists(file):
            continue
        resources = list(map(itemgetter(3), list(filter(lambda x: x[0] == file, jobs['video'])) + list(
            filter(lambda x: x[0] == file, jobs['audio'])) + list(filter(lambda x: x[0] == file, jobs['subtitle']))))
        names.append(f"Concat: {file}")
        commands.append(['run', '-hide_banner', '-loglevel', '0', '-progress', '-', '-nostats',
                         '-i', file,
                         *[x for y in [('-i', r) for i, r in enumerate(resources)] for x in y],
                         *[x for y in [('-map', f'0:{i}') for i in ignored[file]] for x in y],
                         *[x for y in [('-map', f'{i + 1}:0') for i, r in enumerate(resources)] for x in y],
                         '-map_metadata', '0', '-c', 'copy', '-y', file.replace('.mkv', ' - ENCODED.mkv')
                         ])
        durations.append(jobs['video'][0][1])

    parallel(4, names, commands, durations)


def remove(jobs):
    for file, duration, command, outfile in jobs['video']:
        os.remove(outfile)

    for file, duration, command, outfile in jobs['audio']:
        os.remove(outfile)

    for file, duration, command, outfile in jobs['subtitle']:
        os.remove(outfile)


def stats():
    def format_bytes(size):
        # 2**10 = 1024
        power = 2 ** 10
        n = 0
        power_labels = {0: '', 1: 'k', 2: 'M', 3: 'G', 4: 'T'}
        while size > power:
            size /= power
            n += 1
        return size, power_labels[n] + 'B'

    total = 0
    for file in sys.argv[1:]:
        gain, unit = format_bytes(raw := os.path.getsize(file) - os.path.getsize(file.replace('.mkv', ' - ENCODED.mkv')))
        total += raw
        print(f"{gain:.2f}{unit} gained for {file}")
    total, unit = format_bytes(total)
    print(f"{total:.2f}{unit} gained.")


def main():
    # codecs = '-c:a aac_at -aq 10 -c:s copy -c:v libx265 -profile:v main10 -crf 24 -x265-params limit-sao=1:psy-rd=1:aq-mode=3:limit-tu=4:tu-intra-depth=4:tu-inter-depth=4:tskip=1:tskip-fast=1:constrained-intra=1'.split(' ')
    codecs = '-c:s copy -c:a aac_at -aq 10 -c:v copy'.split(' ')

    jobs = {
        'video': [],
        'audio': [],
        'subtitle': [],
    }

    ignored = {}

    parse(jobs, ignored, codecs)

    with global_bar_lock:
        global global_bar
        global_bar = tqdm(leave=False, nrows=1, dynamic_ncols=True,
                          desc="Total Progress", bar_format="{l_bar}{bar}| {n:.0f}/{total_fmt}",
                          total=len(jobs['video']) + len(jobs['audio']) + len(jobs['subtitle']) + len(sys.argv[1:]))

    encode(jobs)
    concat(jobs, ignored)

    with global_bar_lock:
        global_bar.n = global_bar.total
        global_bar.refresh()

    remove(jobs)
    stats()


if __name__ == '__main__':
    main()
