from logging.handlers import RotatingFileHandler
import logging
relative_path="utils/log_file/"
"""
sdsa
"""
Global_Log ={}
"""
https://docs.python.org/2/library/logging.html#logging-levels

log.debug('debug')
log.info('info')
log.warning('warning')
log.error('error')
log.critical('critical')
"""


"""https://docs.python.org/3/library/logging.html#logrecord-attributes
set_Formatter
"""
def setup_logger(filename, maxBytes, backupCount, level=logging.INFO,set_Formatter='%(asctime)s %(levelname)s:%(message)s %(filename)s %(lineno)s  %(funcName)s() %(processName)s %(process)d %(threadName)s %(thread)d'):
    formatter = logging.Formatter(set_Formatter)
    relative_path_filename = relative_path+filename
    handler = RotatingFileHandler(
        filename=relative_path_filename, maxBytes=maxBytes, backupCount=backupCount)
    handler.setFormatter(formatter)

    logger = logging.getLogger("root")
    logger.setLevel(level)
    logger.addHandler(handler)
    global Global_Log
    Global_Log[filename] = logger

"""
log.setup_logger(filename="app.log", maxBytes=0,
                 backupCount=0, level=logging.INFO)
log.Global_Log["app.log"].info("dd")
"""
