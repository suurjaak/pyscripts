# -*- coding: utf-8 -*-
"""
Simple network relay program - allows any number of clients to make a network
connection, relays sent data between all clients. Can log traffic to local db.

Command-line parameters:
--port PORT    port to run on (default 9000)
--db [PATH]    SQLite database path to log to, if any.
               Empty path defaults to 'relaylog.db' in program directory.
--verbose      print verbose activity messages
--test         do a test run with two clients

------------------------------------------------------------------------------
Released under the Creative Commons CC0 1.0 Universal Public Domain Dedication.

@author      Erki Suurjaak
@created     22.01.2014
@modified    24.09.2015
"""
from __future__ import print_function
import argparse
import datetime
import errno
import os
import select
import socket
import sqlite3
import threading
import time
import traceback


"""Log database default filename and table structure."""
ROOTPATH = os.path.dirname(os.path.abspath(__file__))
DB_DEFAULTPATH = os.path.join(ROOTPATH, "relaylog.db")
DB_INITSQL = ("CREATE TABLE IF NOT EXISTS relaylog "
              "(id INTEGER PRIMARY KEY, dt TIMESTAMP, ip TEXT, data BLOB)")
ARGUMENTS = {
    "description": "A simple network relay server to exchange data between clients.",
    "arguments": [
        {"args": ["-p", "--port"], "help": "TCP port to use, 9000 by default",
         "type": int, "default": 9000},
        {"args": ["--db"], "help": ("SQLite database to log traffic to, if any."
         " If DB not given, defaults to 'relaylog.db' in program directory."),
         "nargs": "?", "const": DB_DEFAULTPATH},
        {"args": ["--verbose"], "help": "print verbose activity messages",
         "action": "store_true"},
        {"args": ["-t", "--test"], "help": "do a test run with dummy clients",
         "action": "store_true"},
    ],
}

class RelayServer(threading.Thread):
    """Simple server for accepting socket connections and relaying data."""

    def __init__(self, port, log=(lambda x: x), dbpath=None, db_initsql=None):
        threading.Thread.__init__(self)
        self.setDaemon(False)  # Daemon threads do not keep application running
        self.is_running = False
        self.clients = []  # List of connected client sockets
        self.log = log
        self.db = None
        if dbpath:
            self.db = sqlite3.connect(dbpath, isolation_level=None,
                                      check_same_thread=False)
            self.db.execute(db_initsql)
        ip = "0.0.0.0"
        self.log("Creating relay server on socket %s:%s." % (ip, port))
        self.serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.serversocket.bind((ip, port))


    def run(self):
        self.is_running = True
        relayer = threading.Thread(target=self.client_relayer)
        relayer.setDaemon(True) # Daemon threads do not keep application running
        relayer.start()
        self.serversocket.listen(20)  # 20 - unaccepted connection queue size
        while self.is_running:
            try:
                clientsocket, address = self.serversocket.accept()
                self.log("New connection %s." % (clientsocket.getpeername(), ))
                self.clients.append(clientsocket)
            except socket.error:
                if self.is_running:
                    traceback.print_exc()
        if self.serversocket:
            self.serversocket.close()


    def client_relayer(self):
        """
        Listens on client sockets and forwards data received from any client to
        the others.
        """
        while self.is_running:
            if len(self.clients) < 1:
                time.sleep(1)
                continue  # continue while self.is_running
            readables, _, errors = select.select(self.clients, [], self.clients, 1)
            for sock in errors:
                self.close_socket(sock)
            for sock in (x for x in readables if x in self.clients):
                data = self.read_socket(sock)
                if not data:
                    self.close_socket(sock)
                    continue  # continue for sock
                self.log("Received from client %s data %r." %
                         (sock.getpeername(), data))
                for sock2 in (x for x in self.clients if x != sock):
                    self.write_socket(sock2, data)
                if self.db: self.log_data(data, sock)


    def close_socket(self, sock):
        self.log("Dropping connection %s." % (sock.getpeername(), ))
        if sock in self.clients: self.clients.remove(sock)
        try:
            sock.close()
        except socket.error:
            traceback.print_exc()


    def write_socket(self, sock, data):
        """Sends data to the specified socket."""
        self.log("Sending to client %s data %r." % (sock.getpeername(), data))
        try:
            sock.sendall(data)
        except socket.error:
            traceback.print_exc()


    def read_socket(self, sock, timeout=0.1, max_size=1048576):
        """
        Reads from non-blocking socket until no more data coming.

        @param   timeout   seconds to keep expecting data from the socket
        @param   max_size  byte limit to stop at, if not timed out
        """
        total_data, data, begin = "", "", time.time()
        while self.is_running:
            if (max_size > 0 and len(total_data) >= max_size
            or total_data and time.time() - begin > timeout
            or time.time() - begin > timeout * 2):
                break  # while self.is_running
            try:
                data = sock.recv(8192)
                if data:
                    total_data += data
                else:
                    time.sleep(0.05)
            except socket.error as e:
                if (self.is_running 
                and e.args[0] not in [errno.EAGAIN, errno.EWOULDBLOCK]):
                    traceback.print_exc()
                break  # while self.is_running
        return total_data


    def stop(self):
        """Closes the socket and stops the thread."""
        self.is_running = False
        try:
            self.serversocket.close()
        except socket.error:
            traceback.print_exc()
        self.serversocket = None


    def log_data(self, data, sock):
        """Logs the data received from socket to database."""
        try:
            sql = "INSERT INTO relaylog (dt, data, ip) VALUES (?, ?, ?)"
            self.db.execute(sql, (datetime.datetime.now(),
                                  data, sock.getpeername()[0]))
        except sqlite3.Error:
            traceback.print_exc()



if "__main__" == __name__:
    parser = argparse.ArgumentParser(description=ARGUMENTS["description"])
    for a in ARGUMENTS["arguments"]: parser.add_argument(*a.pop("args"), **a)
    args = parser.parse_args()

    logger = print if args.verbose or args.test else lambda *x, **y: None
    relay_server = RelayServer(args.port, logger, args.db, DB_INITSQL)
    relay_server.start()

    if args.test:  # Run a simple dummy server and client exchanging data
        import random
        logger("Doing test run with 2 clients.")
        clients = []
        for i in range(2):
            logger("Starting up test client #%s." % i)
            clients.append(socket.socket(socket.AF_INET, socket.SOCK_STREAM))
            clients[-1].connect(("localhost", args.port))
        count = 0
        while True:
            for i, sock in enumerate(clients):
                msg = "%d. test message from #%s." % (count, i)
                logger("Client #%s, sending %s" % (i, msg))
                sock.sendall(msg)
                time.sleep(1 + random.random())
                count += 1
        [sock.close() for sock in clients]
        relay_server.stop()
