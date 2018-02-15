import logging
from threading import Thread
from time import sleep

def infinite_worker(worker):

    def _worker(*args):
        while True:
            try:
                worker(*args)
            except KeyboardInterrupt:
                return
            except Exception as e:
                logging.exception(e)
                sleep(1)
            finally:
                pass

    return _worker