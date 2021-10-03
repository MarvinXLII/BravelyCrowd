import sys
import hjson
# from gui import pack, unpack

sys.path.append('src')
from ROM import UNPACK, PACK

def main(settings):
    if settings['option'] == 'Pack':
        PACK(settings)
    if settings['option'] == 'Unpack':
        UNPACK(settings)

if __name__=='__main__':
    if len(sys.argv) != 2:
        sys.exit('Usage: python main.py settings.json')
    with open(sys.argv[1], 'r') as file:
        settings = hjson.load(file)
    main(settings)
