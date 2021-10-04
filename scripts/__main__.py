from log.logger import init_logger
from server.server import run_server
from server.master import run_master

import os
import sys
import glob
import time
import configparser
import colorama, coloredlogs, logging

colorama.init()
logger = init_logger("", True)

def _main():

    logger.info('Starting the basic setup procedure...')
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    '''
    Read the ini config
    for the custom attributes
    '''
    config = configparser.ConfigParser()
    config.read(glob.glob('../config/config.ini'))

    '''
    Intialization process
    '''
    dirname = os.path.dirname(__file__)
    folder = os.path.join(dirname, '../files')

    if not os.path.isdir(folder):
        os.mkdir(folder)

    hostname = config['bottle']['hostname']
    port = config['bottle']['port']
    mode = config['bottle']['mode']

    if len(sys.argv) == 4:
        logger.info("Using CLI variables!")
        hostname = sys.argv[1]
        port = sys.argv[2]
        mode = sys.argv[3]

    '''
    Start the http server
    '''
    if mode == "master":
        logger.info("Starting master server node...")
        run_master(hostname, port, config, logger)
    else:
        logger.info("Starting common server node...")
        run_server(hostname, port, config, logger)

    '''
    Freeze main thread
    '''
    try:
        while True:
            time.sleep(1000)
    except KeyboardInterrupt:
        logger.info("Proccess stopped!")

if __name__ == '__main__':
    _main()