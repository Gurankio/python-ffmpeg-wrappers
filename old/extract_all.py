import argparse
import json
import subprocess
from os import path
import os

parser = argparse.ArgumentParser(description='-')
parser.add_argument('files', metavar='IN', type=str, nargs='+', help='-')
args = parser.parse_args()

for file in args.files:
    file = path.abspath(file)
    filename = path.basename(file).removesuffix('.mkv')
    folder = path.dirname(file)

    command = ["pyprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", file]
    streams = json.loads(subprocess.run(command, capture_output=True, text=True).stdout)['streams']

    attachments = path.join(folder, 'attachments')

    if not path.exists(attachments):
        os.makedirs(attachments)

    for stream in filter(lambda s: s['codec_type'] == 'attachment', streams):
        command = ['run', '-y', f"-dump_attachment:{stream['index']}", path.join(attachments, stream['tags']['filename']), '-i', file]
        subprocess.run(command, stderr=subprocess.DEVNULL)

    for stream in filter(lambda s: s['codec_type'] != 'attachment', streams):
        command = ['run', '-y', '-i', file, '-map', f"0:{stream['index']}", '-c', 'copy', out := f"{path.join(folder, filename + ' - ' + str(stream['index']) + ('+' + str(stream['codec_name']).upper()) + ('+' + str(stream['tags']['language']).upper() if 'language' in stream['tags'] else '') + '.mkv')}"]
        subprocess.run(command, stderr=subprocess.DEVNULL)
