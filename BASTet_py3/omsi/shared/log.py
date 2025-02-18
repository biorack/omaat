"""
Module providing functionality for logging based on the python logging module.
The module is intended toease the use of logging while a developer
can still access the standard python logging mechanism if needed.
"""
import logging
import omsi.shared.mpi_helper as mpi_helper


class log_helper(object):
    """
    BASTet helper module to ease the use of logging

    Class Variables:

    :cvar log_levels: Dictionary describing the different available logging levels.
    """
    initialized = False

    log_levels = {'CRITICAL': logging.CRITICAL,
                  'ERROR': logging.ERROR,
                  'WARNING': logging.WARNING,
                  'INFO': logging.INFO,
                  'DEBUG': logging.DEBUG,
                  'NOTSET': logging.NOTSET}

    global_log_level = log_levels['INFO']

    @classmethod
    def setup_logging(cls, level=None):
        """
        Call this function at the beginning of your code to initiate logging.

        :param level: The default log level to be used. One of ``log_helper.log_level``.

        """
        if level is None:
            level = log_helper.global_log_level
        log_helper.global_log_level = level
        logging.basicConfig(level=level, format=cls.get_default_format())

    @classmethod
    def get_default_format(cls):
        """
        Get default formatting string.
        """
        return '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    @classmethod
    def set_log_level(cls, level):
        """
        Set the logging level for all BASTet loggers

        :param level: The logging levels to be used, one of the values specified in log_helper.log_levels.
        """
        log_helper.debug(__name__, "Setting log level to " + str(level))
        if level not in list(log_helper.log_levels.values()):
            try:
                level = log_helper.log_levels[level]
            except KeyError:
                raise KeyError('Invalid log level given')
        log_helper.global_log_level = level
        ld = logging.Logger.manager.loggerDict
        for k in list(ld.keys()):
            if k.startswith('omsi.'):
                cls.get_logger(k).setLevel(level)

    @classmethod
    def get_logger(cls, module_name):
        """
        Get the logger for a particular module. The module_name
        should always be set to the __name__ variable of the calling module.

        :param module_name: __name__ of the calling module or None in case the ROOT logger should be used.

        :returns: Python logging.Logger retrieved via logging.getLogger.

        """
        if module_name is not None:
            logobj = logging.getLogger(module_name)
            # Make sure we set the correct logging level if we have not created the logger before
            logobj.setLevel(log_helper.global_log_level)
            return logobj
        else:
            return logging.getLogger()

    @classmethod
    def log_var(cls, module_name, root=0, comm=None, level=None, **kwargs):
        """
        Log one or more variable values

        :param module_name: __name__ of the calling module or None in case the ROOT logger should be used.
        :param message: The message to be added to the log
        :param root: The root process to be used for output when running in parallel. If None, then all
                     calling ranks will perform logging. Default is 0.
        :param comm: The MPI communicator to be used to determin the MPI rank. None by default, in which case
                      mpi.comm_world is used.
        :param kwargs: Variables+values to be logged

        """
        for var_name, var_value in kwargs.items():
            try:
                message = str(var_name) + " = " + str(var_value)
                log_helper.log(level=level, module_name=module_name, root=root, comm=comm, message=message)
            except:
                message = "Logging of " + var_name + " for " + module_name + " failed"
                log_helper.error(module_name=__name__, root=root, comm=comm, message=message)

    @classmethod
    def log(cls, module_name, message, root=0, comm=None, level=None,  *args, **kwargs):
        """
        Convenience function used to select the log message level using an input parameter
        rathern than by selecting the approbriate function.

        :param module_name: __name__ of the calling module or None in case the ROOT logger should be used.
        :param message: The message to be added to the log
        :param root: The root process to be used for output when running in parallel. If None, then all
                     calling ranks will perform logging. Default is 0.
        :param comm: The MPI communicator to be used to determine the MPI rank. None by default, in which case
                      mpi.comm_world is used.
        :param level: To which logging level should we send the message
        :param args: Additional positional arguments for the python logger.debug function. See the python docs.
        :param kwargs: Additional keyword arguments for the python logger.debug function. See the python docs.
        """
        if level is None:
            level = log_helper.log_levels['INFO']
        if level in list(log_helper.log_levels.keys()):
            level = log_helper.log_levels[level]
        if root is None or root == mpi_helper.get_rank(comm=comm):
            cls.get_logger(module_name).log(level, message, *args, **kwargs)

    @classmethod
    def debug(cls, module_name, message, root=0, comm=None, *args, **kwargs):
        """
        Create a debug log entry. This function is typically called as:

        log_helper.debug(module_name=__name__, message="your message")

        :param module_name: __name__ of the calling module or None in case the ROOT logger should be used.
        :param message: The message to be added to the log
        :param root: The root process to be used for output when running in parallel. If None, then all
                     calling ranks will perform logging. Default is 0.
        :param comm: The MPI communicator to be used to determin the MPI rank. None by default, in which case
                      mpi.comm_world is used.
        :param args: Additional positional arguments for the python logger.debug function. See the python docs.
        :param kwargs: Additional keyword arguments for the python logger.debug function. See the python docs.

        """
        if root is None or root == mpi_helper.get_rank(comm=comm):
            cls.get_logger(module_name).debug(message, *args, **kwargs)

    @classmethod
    def info(cls, module_name, message, root=0, comm=None, *args, **kwargs):
        """
        Create a info log entry. This function is typically called as:

        log_helper.info(module_name=__name__, message="your message")

        :param module_name: __name__ of the calling module or None in case the ROOT logger should be used.
        :param message: The message to be added to the log
        :param root: The root process to be used for output when running in parallel. If None, then all
                     calling ranks will perform logging. Default is 0.
        :param comm: The MPI communicator to be used to determin the MPI rank. None by default, in which case
                      mpi.comm_world is used.
        :param args: Additional positional arguments for the python logger.debug function. See the python docs.
        :param kwargs: Additional keyword arguments for the python logger.debug function. See the python docs.

        """
        if root is None or root == mpi_helper.get_rank(comm=comm):
            cls.get_logger(module_name).info(message, *args, **kwargs)

    @classmethod
    def warning(cls, module_name, message, root=0, comm=None, *args, **kwargs):
        """
        Create a warning log entry. This function is typically called as:

        log_helper.warning(module_name=__name__, message="your message")

        :param module_name: __name__ of the calling module or None in case the ROOT logger should be used.
        :param message: The message to be added to the log
        :param root: The root process to be used for output when running in parallel. If None, then all
                     calling ranks will perform logging. Default is 0.
        :param comm: The MPI communicator to be used to determin the MPI rank. None by default, in which case
                      mpi.comm_world is used.
        :param args: Additional positional arguments for the python logger.debug function. See the python docs.
        :param kwargs: Additional keyword arguments for the python logger.debug function. See the python docs.

        """
        if root is None or root == mpi_helper.get_rank(comm=comm):
            cls.get_logger(module_name).warning(message, *args, **kwargs)

    @classmethod
    def error(cls, module_name, message, root=0, comm=None, *args, **kwargs):
        """
        Create a error log entry. This function is typically called as:

        log_helper.error(module_name=__name__, message="your message")

        :param module_name: __name__ of the calling module or None in case the ROOT logger should be used.
        :param message: The message to be added to the log
        :param root: The root process to be used for output when running in parallel. If None, then all
                     calling ranks will perform logging. Default is 0.
        :param comm: The MPI communicator to be used to determin the MPI rank. None by default, in which case
                      mpi.comm_world is used.
        :param args: Additional positional arguments for the python logger.debug function. See the python docs.
        :param kwargs: Additional keyword arguments for the python logger.debug function. See the python docs.

        """
        if root is None or root == mpi_helper.get_rank(comm=comm):
            cls.get_logger(module_name).error(message, *args, **kwargs)

    @classmethod
    def critical(cls, module_name, message, root=0, comm=None, *args, **kwargs):
        """
        Create a critical log entry. This function is typically called as:

        log_helper.critical(module_name=__name__, message="your message")

        :param module_name: __name__ of the calling module or None in case the ROOT logger should be used.
        :param message: The message to be added to the log
        :param root: The root process to be used for output when running in parallel. If None, then all
                     calling ranks will perform logging. Default is 0.
        :param comm: The MPI communicator to be used to determin the MPI rank. None by default, in which case
                      mpi.comm_world is used.
        :param args: Additional positional arguments for the python logger.debug function. See the python docs.
        :param kwargs: Additional keyword arguments for the python logger.debug function. See the python docs.

        """
        if root is None or root == mpi_helper.get_rank(comm=comm):
            cls.get_logger(module_name).critical(message, *args, **kwargs)

    @classmethod
    def exception(cls, module_name, message, root=0, comm=None, *args, **kwargs):
        """
        Create a exception log entry. This function is typically called as:

        log_helper.exception(module_name=__name__, message="your message")

        :param module_name: __name__ of the calling module or None in case the ROOT logger should be used.
        :param message: The message to be added to the log
        :param root: The root process to be used for output when running in parallel. If None, then all
                     calling ranks will perform logging. Default is 0.
        :param comm: The MPI communicator to be used to determin the MPI rank. None by default, in which case
                      mpi.comm_world is used.
        :param args: Additional positional arguments for the python logger.debug function. See the python docs.
        :param kwargs: Additional keyword arguments for the python logger.debug function. See the python docs.

        """
        if root is None or root == mpi_helper.get_rank(comm=comm):
            cls.get_logger(module_name).exception(message, *args, **kwargs)


# Setup the logging upon the first import of the class
if not log_helper.initialized:
    log_helper.setup_logging()
    log_helper.set_log_level(log_helper.global_log_level)
    log_helper.debug(__name__, 'Initialized logging')
