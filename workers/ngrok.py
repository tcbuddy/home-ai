import logging
from threading import Thread

from kik import Configuration

from utils.infinite_worker import infinite_worker
from utils.ngrok import run_ngrok, get_ngrok_url

def get_worker(port, kik):

    def worker():
        thread = Thread(target=notify_ngrok_worker)
        thread.start()

        run_ngrok(port=port)


    def notify_ngrok_worker():
        ngrok_url = get_ngrok_url()

        logging.debug('ngrok available at {}'.format(ngrok_url))

        kik.set_configuration(Configuration(webhook=ngrok_url))

    return Thread(target=infinite_worker(worker), name='ngrok')
