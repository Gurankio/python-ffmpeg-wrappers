import sys
import os
from os import path
sys.path.append(path.abspath(path.dirname(path.abspath(sys.argv[0])) + '/..'))
from generic.MEDO import Medo

format_str = sys.argv[1]
for file in sys.argv[2:]:
    file = path.abspath(file)
    os.rename(file, path.join(path.dirname(file), Medo.parse(path.basename(file)).formatter(format_str)))
