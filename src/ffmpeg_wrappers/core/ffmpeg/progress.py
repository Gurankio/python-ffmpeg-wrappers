import re

from rich import print
from rich.progress import Progress

from ffmpeg_wrappers.core.ffmpeg import run

__input = re.compile(r'^Input #\d+')
__duration = re.compile(r'^\s\sDuration: (\d\d):(\d\d):(\d\d)\.(\d\d)')
__mapping = re.compile(r"(\s\s.+?->.+?\(.+?(?:\s\(.+?\)\s->\s.+?\s\(.+?\))?\))")


def __format_size(byte: int) -> str:
    if byte == 0:
        return '0B'
    digits = len(str(byte))
    unit = [' B', 'kB', 'MB', 'GB', 'TB']
    scale = digits // 3 if digits % 3 > 1 else digits // 3 - 1
    return f'{str(byte)[0:(digits - scale * 3)]}{unit[scale]}'


def progress(args: list[str], /, title: str = '', total: int = 100):
    inputs = 0
    total_size = 0
    speed_sum = 0
    speed_samples = 0

    with Progress() as p:
        t = p.add_task(title, total=total)

        for info in run(args, loglevel='info', interval=0.25):
            match info:
                case {'out_time_ms': ms, 'total_size': new_size, 'speed': speed}:
                    if t in p.task_ids:
                        p.update(t, completed=ms)
                        total_size = max(total_size, new_size)
                        if speed is not None:
                            speed_sum += speed
                            speed_samples += 1

                case {'info': message} | {'unknown': message}:
                    if __input.match(message):
                        inputs += 1

                        if inputs > 1:
                            p.remove_task(t)
                            print(f'[red]More than one input detected. Disabling progress bar.')

                    if match := __duration.match(message):
                        hours, minutes, seconds, milliseconds = match.groups()
                        p.update(t, total=int(milliseconds) +
                                          int(seconds) * 1000 +
                                          int(minutes) * 60 * 1000 +
                                          int(hours) * 60 * 60 * 1000)

                    if match := __mapping.match(message):
                        print(f'[light blue]{match.groups()[0].lstrip()}')

                case {'warning': message}:
                    print(f'[yellow]{message}')

                case {'error': message}:
                    print(f'[red]{message}')

                case {'fatal': message}:
                    print(f'[bold white on red]{message}')

                case {'code': code}:
                    if code != 0:
                        print(f'[bold white on red]Someting went wrong. ({code})')

                    p.stop()
                    if speed_samples > 0:
                        print(f'[green]{__format_size(total_size)}[/green] at [green]{speed_sum / speed_samples:.2f}x[/green] speed. ')

                    return code
