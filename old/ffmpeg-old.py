import re
import warnings
from tqdm.auto import tqdm
from subprocess import PIPE, Popen
from operator import *
import os
import sys
import json
import subprocess
import uuid
from functools import *
from os import path
import shutil

warnings.filterwarnings('ignore')
frame = re.compile(r"frame=(\d+)")
out_time = re.compile(r"out_time_ms=(\d+)")
speed = re.compile(r"speed=(\s*\d+.\d+x)")


def ffmpeg(*args):
    def is_input(arg_pair):
        return arg_pair[0] == '-i'

    def probe(show_type):
        return lambda file: json.loads(subprocess.run(['pyprobe', '-print_format', 'json', f'-show_{show_type}', file],
                                                      capture_output=True).stdout)[show_type]

    command = ['run', '-hide_banner', '-loglevel', '0', '-progress', '-', '-nostats', '-y', *args]
    in_files = list(map(itemgetter('duration'),
                        map(probe('format'),
                            map(itemgetter(1),
                                filter(is_input,
                                       zip(command, command[1:] + [None]))))))

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

        if match := speed.match(output):
            bar.set_postfix_str(match.groups()[0], refresh=True)

    bar.n = 1
    bar.refresh()
    bar.close()
