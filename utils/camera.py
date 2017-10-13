import subprocess

def take_picture(destination, skip=1, resolution=(1280, 720)):
    subprocess.check_output([
        'fswebcam',
        '-r', '{}x{}'.format(resolution[0], resolution[1]),
        '--skip', '1',
        '--frames', '1',
        '--no-banner',
        '--quiet',
        destination
    ])