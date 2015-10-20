Various small Python utility scripts
====================================



### [countbits.py](countbits.py)

A command-line tool written just for lark: 
in communications theory the assumption is that a 0-bit is as likely as 1, 
but how is the situation in filesystems?

```
usage: countbits.py [-h] [-d DIR [DIR ...]] [-nr] [-s] [--db DBPATH]
                    [WILDCARD [WILDCARD ...]]

Count the bits (0/1 ratio) in file system files.

positional arguments:
  WILDCARD              one or more filename patterns to match

optional arguments:
  -h, --help            show this help message and exit
  -d DIR [DIR ...], --directory DIR [DIR ...]
                        directories to process, filesystem root by default
  -nr, --nonrecursive   skip subdirectories
  -s, --statsonly       show accumulated statistics and exit
  --db DBPATH           cache-database path, by default in program directory.
                        Use :memory: or empty string for no caching.
```


My result:
```
TOTAL ZERO/ONE    58% vs  42%   99,950,872,411 bytes   699,763 files
-------------------------------------------------------------------------------
          .dll    63% vs  37%   15,686,096,949 bytes    25,414 (16% size)
          .avi    51% vs  49%   12,809,622,256 bytes       180 (13% size)
          .bin    61% vs  39%    8,762,136,890 bytes       314 (9% size)
          .exe    55% vs  45%    7,777,679,103 bytes     6,413 (8% size)
           .db    62% vs  38%    6,963,647,404 bytes       384 (7% size)
<NO EXTENSION>    54% vs  46%    3,935,827,090 bytes    36,492 (4% size)
          .jpg    51% vs  49%    2,709,945,949 bytes    15,781 (3% size)
          .txt    62% vs  38%    2,652,266,242 bytes    16,982 (3% size)
          .pdf    50% vs  50%    2,598,121,519 bytes     1,475 (3% size)
          .msi    51% vs  49%    2,353,022,146 bytes       241 (2% size)
          .dat    51% vs  49%    1,724,590,136 bytes     3,105 (2% size)
         .html    56% vs  44%    1,523,280,768 bytes    41,992 (2% size)
          .jar    58% vs  42%    1,384,024,774 bytes     2,817 (1% size)
          .xml    61% vs  39%    1,117,032,485 bytes     7,034 (1% size)
            .o    69% vs  31%    1,016,419,994 bytes    13,390 (1% size)
..
```
It depends heavily on file types, but in general 0 is slightly more represented.


### [db.py](db.py)

Simple convenience wrapper class for SQLite.

Example usage:

```python
db.init(":memory:", "CREATE TABLE test (id INTEGER PRIMARY KEY, val TEXT)")
db.insert("test", val=None)
for i in range(5): db.insert("test", {"val": i})
db.fetch("test", id=1)
db.fetchall("test", order="val", limit=3)
db.update("test", {"val": "new"}, val=None)
db.fetchall("test", val=("IN", range(3)))
db.delete("test", id=5)
db.execute("DROP TABLE test")
```


### [duplicates.py](duplicates.py)

Command-line tool for detecting duplicate files.

```
usage: duplicates.py [-h] [-d DIR [DIR ...]] [-t  [...]] [-r] [-s]
                     [WILDCARD [WILDCARD ...]]

List files having the same content.

positional arguments:
  WILDCARD              one or more filename patterns to match

optional arguments:
  -h, --help            show this help message and exit
  -d DIR [DIR ...], --directory DIR [DIR ...]
                        directories to process, defaults to working directory
  -t  [ ...], --type  [ ...]
                        file types to match (image, audio, video)
  -r, --recursive       process subdirectories
  -s, --sizeonly        match by file size only
```


### [relayserver.py](relayserver.py)

Simple network relay program - allows any number of clients to make a network
connection, relays sent data between all clients. Can log data to local db.

```
usage: relayserver.py [-h] [-p PORT] [--db [DB]] [--verbose] [-t]

A simple network relay server to exchange data between clients.

optional arguments:
  -h, --help            show this help message and exit
  -p PORT, --port PORT  TCP port to use, 9000 by default
  --db [DB]             SQLite database to log traffic to, if any. If DB not
                        given, defaults to 'relaylog.db' in program directory.
  --verbose             print activity messages
  -t, --test            do a test run with dummy clients
```


### [serialclient.py](serialclient.py)

Simple serial port reader-writer class using background threads.
Needs pyserial.

Example usage:
```python
import serialclient

def callback(data):
    print("Incoming serial data: %r." % data)

client = serialclient.SerialClient("/dev/ttyAMA0", 115200, callback)
client.start()
client.send("outgoing data is queued and written in the background")
```


### [shift_subtitles.py](shift_subtitles.py)

Command-line tool for advancing/delaying movie subtitle timestamps.

```
usage: shift_subtitles.py SUBTITLEFILE SECONDS

Shifts subtitle timestamps in an SRT file by a given amount.
```


### [thumbnails_mpc.py](thumbnails_mpc.py)

Command-line tool for making video thumbnails by invoking Media Player Classic.
Windows-only.

```
usage: thumbnails_mpc.py [WILDCARD [WILDCARD ...]]

Creates thumbnails for videos in current directory, using Media Player Classic.
```


### [util.py](util.py)

All sorts of handy little utility functions accumulated over the years.


License
-------

Published in 2015 by Erki Suurjaak.
Released as free open source software under the 
[Creative Commons CC0 1.0 Universal Public Domain Dedication](https://creativecommons.org/publicdomain/zero/1.0/). ![CC0](http://i.creativecommons.org/p/zero/1.0/88x31.png)
