import sys

from rich.console import Console

from ffmpeg_wrappers.core.ffmpeg import run


# TODO: filter and highlight
def pympeg():
    ffmpeg_stream = run(sys.argv[1:], loglevel='info', interval=0.5)
    console = Console(highlight=False)

    def display_time(seconds):
        minutes, seconds = divmod(int(seconds), 60)  # intentionally discard sub seconds length
        hours, minutes = divmod(minutes, 60)
        return f'{hours:02}:{minutes:02}:{seconds:02}'

    def display_size(byte: int) -> str:
        if byte == 0:
            return ''
        digits = len(str(byte))
        unit = ['B ', 'kB', 'MB', 'GB', 'TB']
        scale = digits // 3 if digits % 3 > 1 else digits // 3 - 1
        return f'{str(byte)[0:(digits - scale * 3)].rjust(4)}{unit[scale]}'

    def display_rate(rate: int) -> str:
        if rate == 0:
            return ''
        digits = len(str(rate))
        unit = ['bps ', 'kbps', 'Mbps', 'Gbps', 'Tbps']
        scale = digits // 3 if digits % 3 > 1 else digits // 3 - 1
        return f'{str(rate)[0:(digits - scale * 3)].rjust(4)}{unit[scale]}'

    styles = {
        'unknown': '',
        'info': '',
        'warning': '[yellow1]',
        'error': '[bright_red]',
        'fatal': '[bold white on red]',
    }

    for packet in ffmpeg_stream:
        match packet:
            case {'level': level, 'message': message}:
                console.print(f'{styles[level]}{message}')

            case {'level': level, 'message': message, 'sender': sender}:
                console.print(f'\\[{sender}] {styles[level]}{message}')

            case {
                'frame': frame,
                'fps': fps,
                'bitrate': bitrate,
                'total_size': size,
                'out_time_ms': ms,
                'speed': speed
            }:
                console.print(
                    f'frame={frame:5} '
                    f'fps={fps:6.2f} '
                    f'size={display_size(size)} '
                    f'time={display_time(ms // 1000)} '
                    f'bitrate={display_rate(bitrate)} '
                    f'speed={speed:4.2f}x'
                    '        ',
                    end='\r'
                )


def main():
    pympeg()


if __name__ == '__main__':
    main()
