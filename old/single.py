from functools import *
# noinspection PyUnresolvedReferences
from itertools import *
# noinspection PyUnresolvedReferences
from operator import *
import os
import uuid
import tempfile
from os import path
from subprocess import run
from ffprobe import probe
from alive_progress import alive_bar


def star(f):
    def flatten(container):
        return chain(*((tuple(i) if not isinstance(tuple, list) else i for i in container)))

    def inner(*args):
        return f(*flatten(args))

    return inner


def part(f):
    def inner(*args):
        return partial(f, args)

    return inner


@part
@star
def valid_chapter(length: int, position: int, chapter: dict) -> bool:
    start_names = [
        'Prologue',
        'Prologue A',
        'Prologue B',
        'Opening',
        'OP',
        'Intro',
        'Series Intro',
        'Episode Intro',
        'Title',
    ]
    end_names = [
        'Epilogue',
        'Ending',
        'ED',
        'Preview',
    ]
    title = chapter['tags']['title'].strip()
    if position == 0:
        return title not in end_names
    elif position == length - 1:
        return title not in start_names
    else:
        return title not in start_names and title not in end_names


@star
def make_attachments(file, streams) -> [([str], str, str)]:
    return [
        (['run', '-y', f'-dump_attachment:{stream["index"]}', out := f'{stream["tags"]["filename"]}', '-i', file],
         out, stream['tags']['mimetype'])
        for stream in filter(lambda x: x['codec_type'] == 'attachment', streams)]


@part
@star
def make_command(codec, file, chapter) -> [([str], str, float)]:
    return (
        ['run', '-hwaccel', 'auto', '-y', '-ss', str(max(0.0, float(chapter['start_time']) - 30)), '-i', file, '-ss',
         chapter['start_time'], '-to', chapter['end_time'],
         '-map', 'V', '-map', 'a', '-map', 's', *codec, out := f'{str(uuid.uuid4())}.mkv'],
        out, float(chapter['end_time']) - float(chapter['start_time'])
    )


def make_concat(chapters, attachments) -> [str]:
    return ['mkvmerge', '-o', path.abspath('./single.mkv'),
            *chain(*map(lambda file_mime: ('--attach-file', file_mime[0]), attachments)),
            *tuple(chain(*zip(chapters, ['+'] * len(chapters))))[:-1]
            ]


# TODO: explicit stream checking.
# TODO: explicit sort.
def single(files: [str], codec: [str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        files = tuple(map(path.abspath, files))
        chapters = tuple(map(probe('chapters'), files))
        chapters = tuple(map(lambda x: (files[x[0]], x[1]), filter(valid_chapter(len(chapters)), chain(*map(lambda i: [(i[0], x) for x in i[1]], enumerate(chapters))))))
        attachments = tuple(chain(*map(make_attachments, zip(files, map(probe('streams'), files)))))
        commands = tuple(map(make_command(codec), chapters))
        concat = make_concat(tuple(map(itemgetter(1), commands)), set(zip(map(itemgetter(1), attachments), map(itemgetter(2), attachments))))
        os.chdir(tmp)

        with alive_bar(title='', theme='smooth', enrich_print=False, total=len(commands) + 1) as bar:
            for (command, out, mime) in attachments:
                run(command, capture_output=True)
                bar()
            for (command, out, duration) in commands:
                run(command)
                bar()
            run(concat)
            bar()


if __name__ == '__main__':
    import sys
    # never copy streams.
    single(sys.argv[1:], ['-c:V', 'h264_videotoolbox', '-b:V', '3000k', '-c:a', 'aac_at', '-aq', '10', '-c:s', 'ass'])
