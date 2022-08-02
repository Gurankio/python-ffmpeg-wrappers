from pathlib import Path

from ffmpeg_wrappers.core.avfile import AvFile, VideoStream, AudioStream


def __convert(options: dict):
    for parameter, value in options.items():
        yield f'-{parameter}', f'{value}'


def generate(input: AvFile, mapper, output: Path, *, extra=None) -> [str]:
    if extra is None:
        extra = tuple()

    mappings = []
    counter = 0

    for stream in input.streams:
        mapping = mapper(stream)

        if mapping is None:
            continue

        if isinstance(mapping, tuple):
            codec, options = mapping
            options = tuple(*__convert(options))

        else:
            codec, options = mapping, tuple()

        mappings += ['-map', f'0:{stream.index}', f'-c:{counter}', codec, *options]
        counter += 1

    return '-i', str(input.path), *mappings, *extra, str(output)


if __name__ == '__main__':
    avfile = AvFile.from_path(
        Path('/Volumes/Storage/Anime/Sword Art Online/Sword Art Online - S01E01 - The World Of Swords.mkv')
    )
    from rich import print


    def encode_crf28(s):
        match s:
            case VideoStream():
                return 'libx265', {'crf': '28'}

            case AudioStream():
                return 'aac_at', {'aq': '0'}

            case _:
                return 'copy'


    print(generate(avfile, encode_crf28, Path('testing.mkv')))
