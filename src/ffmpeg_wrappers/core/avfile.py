import json
import subprocess

from pathlib import Path
from fractions import Fraction

from enum import Flag, auto
from attrs import frozen, field
from attrs.converters import optional


def none_on_exception(f, *exceptions):
    def internal(value):
        try:
            return f(value)
        except exceptions:
            return None

    return internal


def keyword_only(cls, fields):
    results = []

    for field in fields:
        if not field.kw_only:
            results.append(field.evolve(kw_only=True))
        else:
            results.append(field)

    return results


def auto_converter(cls, fields):
    results = []

    for field in fields:
        if field.converter is None:
            if isinstance(field.type, tuple):
                def make_converter(types):
                    return lambda values: tuple(target(value) for value, target in zip(values, types))

                results.append(field.evolve(converter=make_converter(field.type)))
            else:
                results.append(field.evolve(converter=field.type))
        else:
            results.append(field)

    return results


def compose_hooks(*hooks):
    def internal(cls, fields):
        for hook in hooks:
            fields = hook(cls, fields)
        return fields

    return internal


class StreamDisposition(Flag):
    NONE = 0
    DEFAULT = auto()
    DUB = auto()
    ORIGINAL = auto()
    COMMENT = auto()
    LYRICS = auto()
    KARAOKE = auto()
    FORCED = auto()
    HEARING_IMPAIRED = auto()
    VISUAL_IMPAIRED = auto()
    CLEAN_EFFECTS = auto()
    ATTACHED_PIC = auto()
    TIMED_THUMBNAIL = auto()
    CAPTIONS = auto()
    DESCRIPTIONS = auto()
    METADATA = auto()
    DEPENDENT = auto()
    STILL_IMAGE = auto()

    @staticmethod
    def from_dict(data):
        from_name = {flag.name: flag for flag in StreamDisposition}

        out = StreamDisposition.NONE
        for key in data.keys():
            if data[key]:
                out |= from_name[key.upper()]

        return out


@frozen(field_transformer=compose_hooks(keyword_only, auto_converter))
class Stream:
    index: int
    codec_name: (str, str)
    codec_tag: (int, str)

    time_base: Fraction
    start_pts: int
    start_time: float

    r_frame_rate: Fraction = field(converter=optional(none_on_exception(Fraction, ZeroDivisionError)))
    avg_frame_rate: Fraction = field(converter=optional(none_on_exception(Fraction, ZeroDivisionError)))

    extra_data_size: int

    disposition: StreamDisposition
    tags: dict[str, str]

    @staticmethod
    def from_dict(data):
        match data:
            case {
                'index': index,
                'codec_type': 'video',
                'codec_tag': codec_tag,
                'codec_tag_string': codec_tag_string,
                'codec_name': codec_name,
                'codec_long_name': codec_long_name,
                'time_base': time_base,
                'start_pts': start_pts,
                'start_time': start_time,
                'r_frame_rate': r_frame_rate,
                'avg_frame_rate': avg_frame_rate,
                'extradata_size': extra_data_size,
                'disposition': disposition,
                'tags': tags,
                'width': width,
                'height': height,
                'pix_fmt': pix_fmt,
                **other
            }:
                return VideoStream(
                    index=index,
                    codec_name=(codec_name, codec_long_name),
                    codec_tag=(int(codec_tag, 16), codec_tag_string),
                    time_base=time_base,
                    start_pts=start_pts,
                    start_time=start_time,
                    r_frame_rate=r_frame_rate,
                    avg_frame_rate=avg_frame_rate,
                    extra_data_size=extra_data_size,
                    disposition=StreamDisposition.from_dict(disposition),
                    tags=tags,
                    width=width,
                    height=height,
                    pix_fmt=pix_fmt,
                    codec_specific=other
                )

            case {
                'index': index,
                'codec_type': 'audio',
                'codec_tag': codec_tag,
                'codec_tag_string': codec_tag_string,
                'codec_name': codec_name,
                'codec_long_name': codec_long_name,
                'time_base': time_base,
                'start_pts': start_pts,
                'start_time': start_time,
                'r_frame_rate': r_frame_rate,
                'avg_frame_rate': avg_frame_rate,
                'extradata_size': extra_data_size,
                'disposition': disposition,
                'tags': tags,
                'sample_fmt': sample_fmt,
                'sample_rate': sample_rate,
                'channels': channels,
                'channel_layout': channel_layout,
                **other
            }:
                return AudioStream(
                    index=index,
                    codec_name=(codec_name, codec_long_name),
                    codec_tag=(int(codec_tag, 16), codec_tag_string),
                    time_base=time_base,
                    start_pts=start_pts,
                    start_time=start_time,
                    r_frame_rate=r_frame_rate,
                    avg_frame_rate=avg_frame_rate,
                    extra_data_size=extra_data_size,
                    disposition=StreamDisposition.from_dict(disposition),
                    tags=tags,
                    sample_fmt=sample_fmt,
                    sample_rate=sample_rate,
                    channels=channels,
                    channel_layout=channel_layout,
                    codec_specific=other
                )

            case {
                'index': index,
                'codec_type': 'subtitle',
                'codec_tag': codec_tag,
                'codec_tag_string': codec_tag_string,
                'codec_name': codec_name,
                'codec_long_name': codec_long_name,
                'time_base': time_base,
                'start_pts': start_pts,
                'start_time': start_time,
                'r_frame_rate': r_frame_rate,
                'avg_frame_rate': avg_frame_rate,
                'extradata_size': extra_data_size,
                'disposition': disposition,
                'tags': tags,
                'duration': duration,
                'duration_ts': duration_ts,
                **other
            }:
                if len(other) > 0:
                    print(other)  # TODO: proper handling.

                return SubtitleStream(
                    index=index,
                    codec_name=(codec_name, codec_long_name),
                    codec_tag=(int(codec_tag, 16), codec_tag_string),
                    time_base=time_base,
                    start_pts=start_pts,
                    start_time=start_time,
                    r_frame_rate=r_frame_rate,
                    avg_frame_rate=avg_frame_rate,
                    extra_data_size=extra_data_size,
                    disposition=StreamDisposition.from_dict(disposition),
                    tags=tags,
                    duration=duration,
                    duration_ts=duration_ts
                )

            case {
                'index': index,
                'codec_type': 'attachment',
                'codec_tag': codec_tag,
                'codec_tag_string': codec_tag_string,
                'codec_name': codec_name,
                'codec_long_name': codec_long_name,
                'time_base': time_base,
                'start_pts': start_pts,
                'start_time': start_time,
                'r_frame_rate': r_frame_rate,
                'avg_frame_rate': avg_frame_rate,
                'extradata_size': extra_data_size,
                'disposition': disposition,
                'tags': tags,
                'duration': duration,
                'duration_ts': duration_ts,
                **other
            }:
                if len(other) > 0:
                    print(other)  # TODO: proper handling.

                return AttachmentStream(
                    index=index,
                    codec_name=(codec_name, codec_long_name),
                    codec_tag=(int(codec_tag, 16), codec_tag_string),
                    time_base=time_base,
                    start_pts=start_pts,
                    start_time=start_time,
                    r_frame_rate=r_frame_rate,
                    avg_frame_rate=avg_frame_rate,
                    extra_data_size=extra_data_size,
                    disposition=StreamDisposition.from_dict(disposition),
                    tags=tags,
                    duration=duration,
                    duration_ts=duration_ts
                )

            case _:
                print(data)
                return Stream(
                    index=data['index'],
                    codec_name=(data['codec_name'], data['codec_long_name']),
                    codec_tag=(int(data['codec_tag'], 16), data['codec_tag_string']),
                    time_base=data['time_base'],
                    start_pts=data['start_pts'],
                    start_time=data['start_time'],
                    r_frame_rate=data['r_frame_rate'],
                    avg_frame_rate=data['avg_frame_rate'],
                    extra_data_size=data['extradata_size'],
                    disposition=StreamDisposition.from_dict(data['disposition']),
                    tags=data['tags'],
                )


@frozen(field_transformer=compose_hooks(keyword_only, auto_converter))
class VideoStream(Stream):
    width: int
    height: int
    pix_fmt: str

    codec_specific: dict[str, str]


@frozen(field_transformer=compose_hooks(keyword_only, auto_converter))
class AudioStream(Stream):
    sample_fmt: str
    sample_rate: int
    channels: int
    channel_layout: str

    codec_specific: dict[str, str]


@frozen(field_transformer=compose_hooks(keyword_only, auto_converter))
class SubtitleStream(Stream):
    duration: float
    duration_ts: int


@frozen(field_transformer=compose_hooks(keyword_only, auto_converter))
class AttachmentStream(Stream):
    duration: float
    duration_ts: int


@frozen(field_transformer=compose_hooks(keyword_only, auto_converter))
class Chapter:
    id: int
    time_base: Fraction
    start: int
    start_time: float
    end: int
    end_time: float
    tags: dict[str, str]

    @staticmethod
    def from_dict(data):
        return Chapter(**data)


@frozen(field_transformer=compose_hooks(keyword_only, auto_converter))
class AvFile:
    path: Path

    format_name: (str, str)

    start: float
    duration: float
    size: int
    bit_rate: int

    chapters: tuple[Chapter]
    streams: tuple[Stream]

    tags: dict[str, str]

    @staticmethod
    def from_path(path: Path):
        path = path.resolve(strict=True)
        assert path.exists()
        assert path.is_file()

        ffprobe = subprocess.run(
            ('ffprobe', '-print_format', 'json', '-show_format', '-show_chapters', '-show_streams', str(path)),
            check=True,  # TODO: proper handling
            timeout=30,  # TODO: proper handling
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            encoding='UTF-8',
            universal_newlines=True,
            close_fds=True
        )

        data = json.loads(ffprobe.stdout)
        format, chapters, streams = data['format'], data['chapters'], data['streams']

        return AvFile(
            path=path,
            format_name=(format['format_name'], format['format_long_name']),
            start=format['start_time'],
            duration=format['duration'],
            size=format['size'],
            bit_rate=format['bit_rate'],
            chapters=(Chapter.from_dict(chapter) for chapter in chapters),
            streams=(Stream.from_dict(stream) for stream in streams),
            tags=format['tags']
        )
