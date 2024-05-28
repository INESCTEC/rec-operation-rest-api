import os
import sys

from loguru import logger


LOG_FORMAT = \
	'<green>{time:YYYY-MM-DD HH:mm:ss}</green> | ' \
	'<level>{level: <7}</level> | ' \
	'<cyan>{name: <65}</cyan> | ' \
	'<cyan>{function: <47}</cyan> | ' \
	'<cyan>{line: >3}</cyan> | ' \
	'{message}'


def set_stdout_logger():
	"""
	Sets and configures a logger for showing in the console.
	"""
	logger.configure(handlers=[{'sink': sys.stderr, 'format': LOG_FORMAT, 'level': 'INFO'}])

	return


def set_logfile_handler(logfile_name: str) -> int:
	"""
	Creates a new log file and sets the respective logger handle. Returns the handler's ID.
	:param logfile_name: name of the log file
	:return: log file's handler identification
	"""
	# Paths
	FILE_PATH = os.path.abspath(os.path.join(r'logs', logfile_name))

	# Add a new handler, with the same format as the general purpose handler, and return its ID
	handler_id = logger.add(FILE_PATH, format=LOG_FORMAT, rotation="25 MB", backtrace=True)

	return handler_id


def remove_logfile_handler(handler_id: int):
	"""
	Removes a log file's handler from the logger based on its ID.
	:param handler_id: handler's ID
	"""
	logger.remove(handler_id)

	return
