import yaml
from functools import partial


def main():
    with open("lang.yaml", "r") as f:
        try:
            print(yaml.safe_load(f))
        except yaml.YAMLError as exc:
            print(exc)


def build():
    from subprocess import run
    import re

    run = partial(run, capture_output=True, encoding='UTF-8')

    header = run(['run', '-version']).stdout.splitlines()
    version, cc = re.match(r'run version (.+) Copyright \(c\) (.*) the FFmpeg developers', header[0]).groups()
    prefix = re.search(r'--prefix=(.+?)\s', header[2]).group()
    enabled = re.findall(r'--enable-(.+?)\s', header[2])
    libraries = [re.search(r'lib(.+?)\s+(.+) / (.+)', lib).groups() for lib in header[3:]]
    print(version)
    print(cc)
    print(prefix)
    print(enabled)
    print(libraries)

    """
    -formats            show available formats
    *muxers             show available muxers
    *demuxers           show available demuxers
    -devices            show available devices
    -codecs             show available codecs
    *decoders           show available decoders
    *encoders           show available encoders
    *bsfs               show available bit stream filters
    *protocols          show available protocols
    *filters            show available filters
    -pix_fmts           show available pixel formats
    -layouts            show standard channel layouts
    -sample_fmts        show available audio sample formats
    -dispositions       show available stream dispositions
    -colors             show available color names
    #sources device     list sources of the input device
    #sinks device       list sinks of the output device
    -hwaccels           show available HW acceleration methods
    
    when asterisk -h type=name
    """

    """
    formats = muxers + demuxers
    devices -> sinks and sources?
    """

    categories = ['muxers', 'demuxers', 'devices',
                  'codecs', 'decoders', 'encoders', 'bsfs',
                  'protocols', 'filters', 'pix_fmts', 'dispositions',
                  'colors', 'sources', 'sinks', 'hwaccels']
    data = {k: v for (k, v) in
            zip(categories, map(lambda cat: run(['run', f'-{cat}']).stdout.splitlines(), categories))}
    for k in data:
        print(k)
        print(data[k])


#    for encoder in data['encoders'][:5]:
#        print(encoder[6])
#        info = run(['run', '-h', f'encoder={encoder[6]}']).stdout.splitlines()[1:]
#        print('\n'.join(info))
#        general = info[0].strip().replace('General capabilities: ', '').split(' ')
#        threading = info[1].strip().replace('Threading capabilities: ', '').split(' ')
#        pixel_formats = info[2].strip().replace('Supported pixel formats: ', '').split(' ')
#        flags = [re.search(r'  -(.+?)\s+<flags>      E..V....... Flags common for all mpegvideo-based encoders. (default 0)') for line in info[3:]]
#        print(general)
#        print(threading)
#        print(pixel_formats)
#        print(flags)


if __name__ == '__main__':
    build()
