import re

from rich import print
from rich import progress

from ffmpeg_wrappers.core.ffmpeg import run

frame = re.compile(r'frame:(\d+) pblack:(\d+).*')


def main(reference, other):
    with progress.Progress() as p:
        for offset in ('240', '480', '720'):
            t = p.add_task(f'Extracting from REFERENCE at {offset}', total=1)
            for packet in run(['-i', reference, '-filter:v', f'select=eq(n\\,{offset})', '-frames:v', '1', '-y',
                               f'REF{offset}.png'], loglevel='fatal', interval=0.125):
                match packet:
                    case {'level': level, 'message': message, 'sender': sender}:
                        print(message)
            p.update(t, advance=1)

            t = p.add_task(f'Searching for {offset} in OTHER', total=120 * 1000)
            other_frames = []
            for packet in run(
                    ['-hwaccel', 'auto', '-i', other, '-loop', '1', '-i', f'REF{offset}.png', '-filter_complex',
                     '[0]scale=iw*2:ih*2[t];[t][1]blend=difference,blackframe=95', '-vn', '-an', '-sn', '-t', '120s',
                     '-f', 'null', '-'], loglevel='verbose', interval=0.125):
                # print(packet)
                match packet:
                    case {'level': 'error', 'message': message} | {'level': 'fatal', 'message': message}:
                        print(message)
                    case {'level': level, 'message': message, 'sender': sender}:
                        if 'blackframe' in sender:
                            if match := frame.search(message.strip()):
                                other_frames.append(match.groups())
                    case {'out_time_ms': ms}:
                        p.update(t, completed=ms)

            t = p.add_task(f'Searching for {offset} in REFERENCE', total=120 * 1000)
            reference_frames = []
            for packet in run(
                    ['-hwaccel', 'auto', '-i', reference, '-loop', '1', '-i', f'REF{offset}.png', '-filter_complex',
                     '[0][1]blend=difference,blackframe=95', '-vn', '-an', '-sn', '-t', '120s', '-f', 'null', '-'],
                    loglevel='verbose', interval=0.125):
                # print(packet)
                match packet:
                    case {'level': 'error', 'message': message} | {'level': 'fatal', 'message': message}:
                        print(message)
                    case {'level': level, 'message': message, 'sender': sender}:
                        if 'blackframe' in sender:
                            if match := frame.search(message.strip()):
                                reference_frames.append(match.groups())
                    case {'out_time_ms': ms}:
                        p.update(t, completed=ms)

            print(offset)
            print(reference_frames)
            print(other_frames)


if __name__ == '__main__':
    import sys

    main(sys.argv[1], sys.argv[2])
