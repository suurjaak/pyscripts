# -*- coding: utf-8 -*-
"""
Simple serial port reader-writer class using background threads.
Needs pyserial.

------------------------------------------------------------------------------
Released under the Creative Commons CC0 1.0 Universal Public Domain Dedication.

@author      Erki Suurjaak
@created     28.01.2015
@modified    24.09.2015
"""
import logging
import Queue
import threading
import time
import serial


class SerialClient(threading.Thread):
    """Reads bytes from a serial port, posts to callback function."""

    CONNECT_INTERVAL = 10  # Interval to wait between reopen attempts

    def __init__(self, port, baudrate, callback, *args, **kwargs):
        """
        Creates and starts a new reader, with data posted to callback.
        Additional positional and keyword arguments are given to serial.Serial.
        """
        threading.Thread.__init__(self)
        self.setDaemon(True)  # Daemon threads do not keep application running
        self._port = None
        self._args, self._kwargs = [port, baudrate] + list(args), kwargs
        self._callback = callback
        self._serial = None
        self._outqueue = Queue.Queue()
        self._running = False


    def run(self):
        """Read loop, waits for incoming data and invokes callback."""
        self._running = True
        writeloop = threading.Thread(target=self._writeloop)
        writeloop.setDaemon(True), writeloop.start()
        self._open(flush=True)
        while self._running:
            if not self._serial and not self._open():
                time.sleep(self.CONNECT_INTERVAL)
                continue  # while self._running
            try:
                data = self._serial.read(1)
                if data and self._running:
                    data += self._serial.read(self._serial.inWaiting())
                    self._callback(data)
            except IOError:
                if not self._running: continue
                logging.exception("Error reading serial %s. "
                                  "Will close and try to reopen.", self._port)
                self._serial = self._serial.close()
                time.sleep(self.CONNECT_INTERVAL)
        self.stop()


    def send(self, data):
        """Queues byte data to be written to serial port in the background."""
        self._outqueue.put(data)


    def stop(self):
        """Closes the serial port and stops the thread."""
        self._running = False
        self._outqueue.put(None)  # Wake up writeloop
        try: self._serial and self._serial.close()
        except IOError: pass
        self._serial = None


    def _open(self, flush=False):
        """Tries to open serial port, returns True on success."""
        logging.info("Opening serial %s at %sbps.", self._port, self._args[1])
        try:
            self._serial = serial.Serial(*self._args, **self._kwargs)
            if flush: self._serial.flushInput()
            return True
        except IOError:
            logging.exception("Error opening serial %s at %sbps. "
                              "Will try to reopen in %s.", self._port,
                              self._args[1], self.CONNECT_INTERVAL)


    def _writeloop(self):
        """Write loop, sends queued data to serial."""
        while self._running:
            data = self._outqueue.get()
            try:
                if data and self._serial: self._serial.write(data)
            except IOError:
                logging.exception("Error writing to serial %s.", self._port)
