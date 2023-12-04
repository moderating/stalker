import logging

COLOR = "\x1b[38;5;68m"
RESET = "\x1b[0m"

loggingfmts: dict = {
    logging.DEBUG: " [⌚ \x1b[38;5;242m%(asctime)s\x1b[0m]  <{0}%(name)s{1}> [%(levelname)s] %(funcName)s(): %(message)s ".format(
        COLOR, RESET
    ),
    logging.INFO: " [⌚ \x1b[38;5;242m%(asctime)s\x1b[0m]  <{0}%(name)s{1}> [{2}<%(levelname)s>{3}] %(funcName)s(): %(message)s ".format(
        COLOR, RESET, "\x1b[38;5;69m", RESET
    ),
    logging.WARNING: " [⌚ \x1b[38;5;242m%(asctime)s\x1b[0m]  <{0}%(name)s{1}> [{2}<%(levelname)s>{3}] %(funcName)s(): %(message)s ".format(
        COLOR, RESET, "\x1b[38;5;228m", RESET
    ),
    logging.ERROR: " [⌚ \x1b[38;5;242m%(asctime)s\x1b[0m]  <{0}%(name)s{1}> [{2}<%(levelname)s>{3}] %(funcName)s(): %(message)s ".format(
        COLOR, RESET, "\x1b[38;5;160m", RESET
    ),
    logging.CRITICAL: " [⌚ \x1b[38;5;242m%(asctime)s\x1b[0m]  <{0}%(name)s{1}> [{2}<%(levelname)s>{3}] %(funcName)s(): %(message)s ".format(
        COLOR, RESET, "\x1b[38;5;88m", RESET
    ),
}


class miamiloggr(logging.Formatter):
    def format(self, record: logging.LogRecord):
        fmt = loggingfmts[record.levelno]
        return logging.Formatter(fmt, datefmt="%m-%d-%Y %I:%M:%S").format(record=record)
