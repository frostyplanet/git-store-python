#!/usr/bin/env python
#
# @file log.py
# @author an.ning@aliyun-inc.com
# @version $Id: log.py,v 1.3 2010/04/26 03:41:21 anning Exp $
# @brief
#
import os
import os.path
import logging
import sys
import traceback
from logging.handlers import RotatingFileHandler


class Log (logging.Logger):

    __file_handler = None
    log_level_map = {'DEBUG': logging.DEBUG,
                    'INFO':logging.INFO,
                    'WARNING':logging.WARNING,
                    'ERROR':logging.ERROR,
                    'CRITICAL':logging.CRITICAL,
                    }
    
    def __init__ (self, filename = None, level = None, config = None, base_path = None):
            
        __log_path = ""
        __rotate_size = 0
        __backup_count = 0 # if 0, will only truncate but no backup
        __log_level = logging.INFO

        #init path according to config
        if "base_path" in dir(config):
            __log_path = config.base_path
        elif base_path:
            __log_path = base_path

        if "log_dir" in dir(config):
            __log_path = os.path.join (__log_path, config.log_dir)

        if "log_rotate_size" in dir(config):
            __rotate_size = config.log_rotate_size * 1000

        if "log_backup_count" in dir(config):
            __backup_count = config.log_backup_count
        try:
            if level:
                __log_level = level
            elif "log_level" in dir(config):
                __log_level = self.log_level_map[config.log_level]
            if __log_level and isinstance (__log_level, str):
                __log_level = self.log_level_map[__log_level]
        except Exception, e:
            print "log_level", str(e)
        
        if not filename:
            filename = "main"
        file_path = os.path.join (__log_path, filename + ".log")
        file_dir = os.path.dirname (file_path)
        if file_dir:
            if os.path.exists (file_dir):
                if not os.path.isdir (file_dir):
                    raise Exception, "logging path '%s' is not a directory"
            else:
                os.mkdir (file_dir)

        self.__file_handler = RotatingFileHandler (file_path, 'a', __rotate_size, __backup_count)
        formatter = logging.Formatter ("%(asctime)s [%(levelname)s] %(message)s")
        self.__file_handler.setFormatter (formatter)
        logging.Logger.__init__ (self, filename)
        self.addHandler (self.__file_handler)
        if __log_level:
            self.setLevel (__log_level)

    def __del__ (self):
        self.removeHandler (self.__file_handler)
        try:
            self.__file_handler.close ()
        except Exception, e:
            print str(e)
            pass
    
    def format_frame (f):
        file, line, func, code = f
        return "in %s() ('%s':%d)" % (func, file, line)
    format_frame = staticmethod (format_frame)

    def format_frame_ex (f):
        file, line, func, code = f
        return "in %s() ('%s':%d) '%s'" % (func, file, line, code)
    format_frame_ex = staticmethod (format_frame_ex)
            
    def get_exc_frames ():
        '''concate exception frames inside and outside try statement'''
        exc_type, exc_value, exc_traceback = sys.exc_info()
        l_in = traceback.extract_tb (exc_traceback)
        l_out = traceback.extract_stack ()
        l = l_out[0: -3]
        for x in l_in:
            l.append (x)
        return l
    get_exc_frames = staticmethod (get_exc_frames)
            
    def exception (self, msg, bt_level = 0):
        assert (bt_level >= 0)
        fs = self.get_exc_frames ()
        prefix = "[%s] " % (self.format_frame (fs[-1 -bt_level]))
        logging.Logger.log (self, logging.ERROR, prefix + str (msg))
    
    def exception_ex (self, msg, bt_level = 0):
        assert (bt_level >= 0)
        fs = self.get_exc_frames ()
        prefix = "[ exception backtrace:"
        for l in fs:
            prefix = prefix + "\n" + self.format_frame_ex (l)
        prefix += "] "
        logging.Logger.log (self, logging.ERROR, prefix + str (msg))
            
    def log (self, level, msg, bt_level = 0):
        assert (bt_level >= 0)
        fs = traceback.extract_stack ()
        bt_level +=1 
        prefix = "[%s] " % (self.format_frame (fs[-1 -bt_level]))
        logging.Logger.log (self, level, prefix + str (msg))

    def debug (self, msg, bt_level = 0):
        self.log (logging.DEBUG, msg, bt_level + 1)
    
    def info (self, msg, bt_level = 0):
        self.log (logging.INFO, msg, bt_level + 1)
    
    def warning (self, msg, bt_level = 0):
        self.log (logging.WARNING, msg, bt_level + 1)

    def error (self, msg, bt_level = 0):
        self.log (logging.ERROR, msg, bt_level + 1)    

    def critical (self, msg, bt_level = 0):
        self.log (logging.CRITICAL, msg, bt_level + 1)    
    

# vim: set sw=4 ts=4 et :
