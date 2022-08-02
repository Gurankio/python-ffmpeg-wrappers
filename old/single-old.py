import os
import sys
import json
import subprocess
import uuid
from functools import reduce
from operator import itemgetter
from os import path
import shutil

FFMPEG = ['run', '-hide_banner', '-loglevel', '0', '-progress', '-', '-nostats', '-y']


def parallel(pool_size, descriptions, commands, durations):
    if len(commands) == 0:
        return

    import re
    import warnings
    from tqdm.auto import tqdm
    from subprocess import PIPE, Popen
    from concurrent.futures import ThreadPoolExecutor

    warnings.filterwarnings('ignore')
    frame = re.compile(r"frame=(\d+)")
    out_time = re.compile(r"out_time_ms=(\d+)")
    speed = re.compile(r"speed=(\s*\d+.\d+x)")

    def run_command(desc, command, duration):
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

    with ThreadPoolExecutor(max_workers=min(len(commands), pool_size)) as executor:
        for desc, command, duration in zip(descriptions, commands, durations):
            executor.submit(run_command, desc, command, duration)


def probe_file(file, show_type):
    return json.loads(
        subprocess.run(['pyprobe', '-print_format', 'json', f'-show_{show_type}', file], capture_output=True).stdout)[
        show_type]


def should_skip(chapter):
    return chapter['tags']['title'] not in [
        'OP',
        'ED',
        'Next'
    ]


def get_times(chapter):
    return [float(chapter['start_time']), float(chapter['end_time'])]


def concat(a, b):
    if len(a) > 0 and a[-1][1] == b[0]:
        a[-1][1] = b[1]
    else:
        a.append(b)
    return a


def process_vas_soft(codec, data):
    if path.exists('temp'):
        print("temp folder exists. exiting.")
        quit(-1)
    else:
        os.makedirs('temp')
        os.makedirs('temp/attach')

    video = []
    concat_video = []
    audio = []
    concat_audio = []
    subtitles = []
    concat_subtitles = []
    attachments = []

    for file, chapters, streams in data:
        for stream in filter(lambda s: s['codec_type'] == 'video', streams):
            filter_complex = [f'[0:{stream["index"]}]trim=start={start}:end={end},setpts=PTS-STARTPTS[{index}v];' for
                              index, (start, end) in enumerate(chapters)]
            filter_complex.append(
                f'{"".join([f"[{i}v]" for i in range(len(chapters))])}concat=n={len(chapters)}:v=1[outv]')
            video.append((
                f'V{stream["index"]}',
                [*FFMPEG, '-i', file, *codec, '-filter_complex', ''.join(filter_complex), '-map', '[outv]',
                 path.join('temp', out := str(uuid.uuid4()) + '.mkv')],
                chapters[-1][-1] - chapters[0][0]
            ))
            concat_video.append(f"file '{out}'\n")

        for stream in filter(lambda s: s['codec_type'] == 'audio', streams):
            filter_complex = [f'[0:{stream["index"]}]atrim=start={start}:end={end},asetpts=PTS-STARTPTS[{index}a];' for
                              index, (start, end) in enumerate(chapters)]
            filter_complex.append(
                f'{"".join([f"[{i}a]" for i in range(len(chapters))])}concat=n={len(chapters)}:v=0:a=1[outa]')
            audio.append((
                f'A{stream["index"]}',
                [*FFMPEG, '-i', file, *codec, '-filter_complex', ''.join(filter_complex), '-map', '[outa]',
                 path.join('temp', out := str(uuid.uuid4()) + '.mkv')],
                chapters[-1][-1] - chapters[0][0]
            ))
            concat_audio.append(f"file '{out}'\n")

        for stream in filter(lambda s: s['codec_type'] == 'subtitle', streams):
            for index, (start, end) in enumerate(chapters):
                subtitles.append((
                    f'S{stream["index"]}C{index}',
                    [*FFMPEG, '-ss', str(start), '-i', file, '-t', str(end - start), '-map', f'0:{stream["index"]}',
                     path.join('temp', out := str(uuid.uuid4()) + '.ass')],
                    end - start
                ))
                concat_subtitles.append(f"file '{out}'\nduration {end - start}\n")

        for stream in filter(lambda s: s['codec_type'] == 'attachment', streams):
            attachments.append(
                [*FFMPEG, f'-dump_attachment:{stream["index"]}', f'temp/attach/{stream["tags"]["filename"]}', '-i', file])

    with open(v_list := path.join('temp', 'V.txt'), 'w') as f:
        f.writelines(concat_video)
    with open(a_list := path.join('temp', 'A.txt'), 'w') as f:
        f.writelines(concat_audio)
    with open(s_list := path.join('temp', 'S.txt'), 'w') as f:
        f.writelines(concat_subtitles)

    parallel(8, ["ATTACH"] * len(attachments), attachments, [0] * len(attachments))
    parallel(2, list(map(itemgetter(0), video)), list(map(itemgetter(1), video)), list(map(itemgetter(2), video)))
    parallel(8, list(map(itemgetter(0), audio)), list(map(itemgetter(1), audio)), list(map(itemgetter(2), audio)))
    parallel(8, list(map(itemgetter(0), subtitles)), list(map(itemgetter(1), subtitles)), list(map(itemgetter(2), subtitles)))
    parallel(3,
             ["CV", "CA", "CS"],
             [[*FFMPEG, '-f', 'concat', '-safe', '0', '-i', v_list, '-c', 'copy', path.join('temp', 'V.mkv')],
              [*FFMPEG, '-f', 'concat', '-safe', '0', '-i', a_list, '-c', 'copy', path.join('temp', 'A.mkv')],
              [*FFMPEG, '-f', 'concat', '-safe', '0', '-i', s_list, '-c', 'copy', path.join('temp', 'S.mkv')]
              ],
             [sum(map(itemgetter(2), video)), sum(map(itemgetter(2), audio)), sum(map(itemgetter(2), subtitles))]
             )

    attach = []
    for f in os.listdir('temp/attach'):
        attach.append('--attach-file')
        attach.append('temp/attach/' + f)
    subprocess.run(['mkvmerge', *attach, '-o', 'CUT.mkv', 'temp/V.mkv', 'temp/A.mkv', 'temp/S.mkv'])

    shutil.rmtree('temp', True)


def main():
    codec = ['-c:a', 'aac_at', '-c:v', 'h264_videotoolbox', '-b:v', '3000k', '-allow_sw', '1']
    probed = [(file, list(reduce(concat, map(get_times, filter(should_skip, probe_file(file, 'chapters'))), [])), probe_file(file, 'streams')) for file in sys.argv[1:]]
    process_vas_soft(codec, probed)


if __name__ == '__main__':
    main()
