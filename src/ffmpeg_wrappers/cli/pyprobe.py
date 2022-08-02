from operator import itemgetter
from pathlib import Path

from rich import print
from rich.console import Console
from rich.tree import Tree
from typer import run

from ffmpeg_wrappers.core.avfile import AvFile, VideoStream, AudioStream, SubtitleStream, AttachmentStream


def display_time(seconds):
    minutes, seconds = divmod(int(seconds), 60)  # intentionally discard sub seconds length
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f'{hours:02}:{minutes:02}:{seconds:02}'
    else:
        return f'{minutes:02}:{seconds:02}'


def display_size(byte: int) -> str:
    if byte == 0:
        return ''
    digits = len(str(byte))
    unit = [' B', 'kB', 'MB', 'GB', 'TB']
    scale = digits // 3 if digits % 3 > 1 else digits // 3 - 1
    return f'{str(byte)[0:(digits - scale * 3)]}{unit[scale]}'


def chapter_timeline(self):
    width = Console().width

    lengths = []
    for i, c in enumerate(self.chapters):
        duration = c.end_time - c.start_time
        percentage = duration / self.duration
        available_length = int(percentage * width)

        title_length = len(c.tags['title'])
        timestamp = display_time(c.start_time)
        timestamp_length = len(timestamp)
        required_length = max(title_length, timestamp_length)
        diff = available_length - required_length
        lengths.append([available_length, required_length, diff, i, timestamp, c.tags['title']])

    solvable = sum(map(itemgetter(2), lengths)) > (len(lengths) - 1) * 2
    assert solvable

    lengths = sorted(lengths, key=itemgetter(2))
    for i in range(len(lengths) - 1):
        extra = 3 if lengths[i][3] != len(lengths) - 1 else 0

        if lengths[i][2] < extra:
            target = -1
            while lengths[target][2] < lengths[target - 1][2]:
                target -= 1

            lengths[target][0] += lengths[i][2] - extra
            lengths[i][0] -= lengths[i][2] - extra

            lengths[target][2] = lengths[target][0] - lengths[target][1]
            lengths[i][2] = lengths[i][0] - lengths[i][1]

    lengths = sorted(lengths, key=itemgetter(3))

    timeline_timestamps = ''
    timeline_graph = ''
    timeline_titles = ''
    for c in lengths:
        timeline_timestamps += c[4].ljust(c[0])
        timeline_graph += '├' + '─' * (c[0] - 1)
        timeline_titles += c[5].ljust(c[0])

    timeline_graph += '─' * (width - len(timeline_graph) - 1) + '┤'

    print('[bright_red]' + timeline_timestamps)
    print('[bold]' + timeline_graph)
    print('[bright_red]' + timeline_titles)


def streams_tree(avfile):
    streams = Tree('Streams', style='bold')
    video = streams.add('Video', style='orange1')
    audio = streams.add('Audio', style='cyan1')
    subtitle = streams.add('Subtitles', style='green1')
    attachment = streams.add('Attachments', style='magenta1')

    codecs = {}

    for s in avfile.streams:
        codec = s.codec_name[0].upper()
        match s:
            case VideoStream():
                if codec not in codecs:
                    codecs[codec] = video.add(codec)

                codecs[codec].add(
                    f'{s.width}x{s.height} {float(s.avg_frame_rate):.2f}fps ({s.index:02})',
                    style='orange3'
                )

            case AudioStream():
                if codec not in codecs:
                    codecs[codec] = audio.add(codec, style='cyan2')

                codecs[codec].add(
                    f'{s.sample_rate}Hz {s.channels}ch ({s.index:02})',
                    style='cyan3'
                )

            case SubtitleStream():
                if codec not in codecs:
                    codecs[codec] = subtitle.add(codec).add('', style='green3')

                codecs[codec].label += ', ' if codecs[codec].label != '' else ''
                codecs[codec].label += f'{langs()[s.tags["language"]]["english"]} "{s.tags["title"]}" ({s.index:02})'

            case AttachmentStream():
                if codec not in codecs:
                    codecs[codec] = attachment.add(codec, style='magenta2').add('', style='magenta3')

                codecs[codec].label += ', ' if codecs[codec].label != '' else ''
                codecs[codec].label += f'({s.index:02})'

    for category in streams.children:
        if len(category.children) == 1:
            ...

    print(streams)


def pyprobe(avfile: Path):
    avfile = AvFile.from_path(avfile)
    print(f'[bold]{avfile.path.name}[/bold], [bright_red]{display_time(avfile.duration)}[/bright_red] long, [bright_cyan]{display_size(avfile.size)}[/bright_cyan]')
    print()
    if len(avfile.chapters) > 0:
        chapter_timeline(avfile)
        print()
    streams_tree(avfile)


def main():
    run(pyprobe)


if __name__ == '__main__':
    main()
