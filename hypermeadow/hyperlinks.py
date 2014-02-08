#!/usr/bin/env python3
"""
Jeff Quast <contact@jeffquast.com>
Completed Fri Sep 13
"""
import argparse
import io
import json
import logging
import queue
import sys
import threading
import time
import urllib.parse

import requests  # requests: HTTP for humans
                 # http://docs.python-requests.org/en/latest/
import bs4  # beautifulsoup: provide[s] idiomatic ways of navigating,
            # searching, and modifying the [html] parse tree
            # http://www.crummy.com/software/BeautifulSoup/

_DEF_URL = 'http://rivermeadow.com'
_LOG_FMT = ('%(relativeCreated)7.3f %(levelname)-6s %(threadName)-10s '
            '%(filename)11s:%(lineno)-3s - %(message)s')

ARGS = argparse.ArgumentParser(
        description='Recursively traverse HTTP URL, '
                    'building graph of hyperlink references.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
ARGS.add_argument(
            '--url', action='store', dest='url',
                default=_DEF_URL,
                help='Target URL.')
ARGS.add_argument(
            '--limit', '-l', action='store', dest='limit',
                default=1000, type=int,
                help='Maximum URLs to traverse.')
ARGS.add_argument(
            '--out', '-o', action='store', dest='out',
                help='File for output.')
ARGS.add_argument(
            '--loglevel', action='store', dest='loglevel',
                default='warn', type=str,
                help='Loging level.')
ARGS.add_argument(
            '--queue', '-q', action='store', dest='queue',
                default='fifo', type=str,
                help="Queue fetching order. fifo: first in, first out, " \
                        "lifo: last in, first out.")
ARGS.add_argument(
            '--threads', '-t', action='store', dest='nthreads',
                default=3, type=int,
                help='Number of threads.')
ARGS.add_argument(
            '--delay', '-d', action='store', dest='delay',
                default=0.33, type=float,
                help='timed delay between requests, per thread.')


class LifoQueue_Limited(queue.LifoQueue):
    """ This modified queue.LifoQueue tracks number
        of inserts to public attribute ``num_inserts``,
        which is evaluated against maximum URL fetches.
    """
    def _init(self, maxsize):
        queue.LifoQueue._init(self, maxsize)
        self.num_inserts = 0

    def _put(self, item):
        self.queue.append(item)
        self.num_inserts += 1


class FifoQueue_Limited(queue.Queue):
    """ This modified queue.Queue tracks number of inserts
        to public attribute ``num_inserts``, which is
        evaluated against maximum URL fetches.
    """
    def _init(self, maxsize):
        queue.Queue._init(self, maxsize)
        self.num_inserts = 0

    def _put(self, item):
        self.queue.append(item)
        self.num_inserts += 1


class JSONSetEncoder(json.JSONEncoder):
    """ this JSONEncoder converts instances of ``set``
        to ``list`` during serialization, as set() is
        not JSON serializable.
    """
    def default(self, obj):
        if isinstance(obj, set):
            return list(obj)
        return json.JSONEncoder.default(self, obj)


def open_filepath(fname):
    """ Returns file object for line-buffered writing of text
        to filepath specified by argument ``fname``.  If the file
        exists, it is truncated.
    """
    import os
    filepath = os.path.abspath(fname)
    if os.path.exists(filepath):
        # path already exists, verify that it is an existing file, and not
        # some other filesystem type, such as a symlink, folder, mountpoint.
        assert os.path.isfile(filepath), (
                '{} is not a file.'.format(filepath))
        assert os.access(filepath, os.W_OK), (
                'no write access to {}.'.format(filepath))
    else:
        # path does not exist, ensure the folder does. If so, may we write
        # a new file to this folder?
        dirname = os.path.dirname(filepath)
        assert os.path.exists(dirname), (
                'directory {} does not exist.'.format(dirname))
        assert os.access(dirname, os.W_OK), (
                'directory {} is not writable, '
                'and file {} does not exist.'.format(dirname,
                    os.path.basename(filepath)))
    # open file for writing (truncate existing), in line-buffering mode (1)
    return io.open(filepath, mode='w', buffering=1)


def set_loglevel(level_name):
    """ Sets global logging level level specified
        by string ``level_name``, such as 'debug',
        or 'warn'.
    """
    assert type(level_name) == str, level_name
    level_name = level_name.upper()
    levels_avail = [level
            for level in dir(logging)
            if isinstance(getattr(logging, level), int)]
    assert level_name in levels_avail, (
            "{} not a valid loglevel, chose one of: {}".format(
                level_name, ', '.join(levels_avail)))
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, level_name))


class Fetch(threading.Thread):
    """ A threaded URL fetcher. URLs are discovered from the class attribute
        ``url_queue`` shared Queue instance provided during instantiation, with
        hyperlink relationship information stored in the class attribute
        ``url_store``, also shared by other threads, and locked by ``url_lock``,
        both keyword arguments provided during instantiation.

        Class attributes::

            ``stall``
            Number of seconds for a thread to sleep when the url_queue is empty
            before emitting a warning.

    """
    stall = 5  #: timeout of url_queue get request
    _force_ending = False
    def __init__(self, url_queue, url_store, url_lock, max_urls=1000, delay=1):
        """ Class constructor arguments:
            :arg url_queue: a queue.Queue class instance that contains URLs to
                be fetched.  Any URLs not discovered in ``url_store`` are added
                to this queue.  This queue may be shared by multiple threads.
            :arg url_store: a dict class instance that contains the reporting
                results of hyperlinks traversed and discovered.  This
                dictionary may be shared by multiple threads.
            :arg url_lock: a threading.Lock class instance that is shared by
                multiple threads to ensure that no data is lost when stored
                to the output ``url_store`` storage unit.
            :arg max_urls: the maximum number of URLs allowed to be fetched;
                requires a custom Queue subclass that implements public
                attribute counter, 'num_inserts'.
            :arg delay: timed delay between requests. Important to set an
                articial delay on public servers that you do not own --
                recursively scanning the public internet may trigger a
                denial-of-service alert.
        """
        assert issubclass(type(url_queue), queue.Queue), url_queue
        self.url_queue = url_queue

        assert issubclass(type(url_store), dict), url_store
        self.url_store = url_store

        assert (hasattr(url_lock, 'acquire') and
                hasattr(url_lock, 'release')), url_lock
        self.url_lock = url_lock

        assert (type(max_urls) == int), max_urls
        assert max_urls > 0, max_urls
        self.max_urls = max_urls

        assert (type(delay) in (int, float)), delay
        assert delay >= 0.0, delay
        self.delay = delay

        threading.Thread.__init__(self)

    def stop(self):
        self._force_ending = True

    def run(self):
        """ Fetch execution loop: Retrieve an item from the url_queue,
            fetch it, check it, parse and record hyperlinks, push
            new hyperlinks back into url_queue. """
        logging.debug('begin')
        while not self._force_ending:
            try:
                url = self.url_queue.get(timeout=self.stall)
            except queue.Empty:
                if self.url_queue.num_inserts >= self.max_urls:
                    # we've reached the maximum url's fetched; we won't
                    # find any new urls to retrieve, yet another thread
                    # is still busy with a task.
                    logging.debug('giving up')
                    break

                if not self._force_ending:
                    # when the queue is empty, but _force_ending is not True,
                    # we are in condition of a single thread holding onto
                    # a pending url request that may still yet have additional
                    # urls to place back into the queue. log a warning and
                    # try again.
                    logging.warn('stall')
                continue

            # fetch url, handling and reporting exceptions
            logging.debug('fetch {}'.format(url))
            try:
                req = requests.get(url)
            except Exception as err:
                logging.warn('failed url {}, reason: {}'.format(url, err))
                self.url_queue.task_done()
                continue

            # check status code, only 200 permitted
            if req.status_code != 200:
                logging.warn('status code {} for url {}'.format(
                    req.status_code, req.url))
                self.url_queue.task_done()
                continue

            # assume content-type is text/html unless specified.
            # as only html contains hyperlinks, we skip all others.
            # ('naivety' requirement)
            ctype = req.headers.get('content-type', 'text/html')
            if not ctype.split(';', 1)[0] == 'text/html':
                logging.info('skip; content-type is {}'.format(ctype))
                self.url_queue.task_done()
                continue

            # discover all outgoing links of current hypertext document.
            urls = self.discover_urls(req.url, req.content)
            logging.debug('{} outgoing urls discovered'.format(len(urls)))

            if urls:
                # ensure view of url_store is frozen during evaluation.
                self.url_lock.acquire()
                logging.debug('lock acquired')

                # ``req.url`` becomes the 'incoming' reference for
                # the 'outgoing' links discovered in list ``urls``.
                fetch_urls = self.store_urldata(req.url, urls, store=self.url_store)

                if fetch_urls:
                    # queue newly discoered URLs for later downloading,
                    # unless limit has been reached: report number of discarded
                    # urls as 'info'
                    for count, fetch_url in enumerate(fetch_urls):
                        if self.url_queue.num_inserts >= self.max_urls:
                            logging.info('url limit reached ({}), '
                                      '{} urls discarded.'.format(
                                          self.max_urls, len(fetch_urls) - count))
                            break
                        self.url_queue.put (fetch_url)
                    if count:
                        logging.info('{} urls queued'.format(count))

                # release url_store for evaluation by other threads.
                self.url_lock.release()

            logging.debug('lock released{}{}.'.format(
                          ', {} remain'.format(self.url_queue.qsize())
                              if self.url_queue.qsize() else '',
                          ', sleeping for {}'.format(self.delay)
                            if self.delay else '.'))
            self.url_queue.task_done()

            if self.delay >= 0.0:
                # take a byte out of i/o crime
                time.sleep(self.delay)

        logging.debug('end')

    def discover_urls(self, base_url, body):
        """ Given the current ``base_url`` and request ``body``, return a list
            of absolute urls, duplicates and all. Anchors are removed from page
            links, and relative urls are converted to absolute.  """
        soup = bs4.BeautifulSoup(body)

        # discover a list of urls found on this page (base_url).
        discovered = []
        for a_href in soup('a'):
            href = a_href.get('href')
            if href is None:
                logging.debug('anchor href is None: {!r}'.format(a_href))
                continue
            parsed = urllib.parse.urlparse(href.strip())

            if len(parsed.scheme) and len(parsed.netloc):
                # url already absolute
                url = href.strip()
            else:
                # convert relative ``a_href`` to absolute ``url``
                if 0 == len(href.strip()):
                    logging.debug('empty href skipped')
                    continue
                url = urllib.parse.urljoin(base_url, href)
                re_parsed = urllib.parse.urlparse(url)
                if (0 in (len(re_parsed.scheme), len(re_parsed.netloc))
                        or not url.startswith ('http')):
                    logging.debug('skipping non-http hyperlink {}'.format(url))
                    continue

            discovered.append(url)

        return discovered

    def store_urldata(self, current_url, outgoing_urls, store):
        # list of urls that should be queued for fetching: they are new and
        # have not yet been discovered until evaluated here.
        new_urls = set()

        # track 'incoming' links,
        for o_url in outgoing_urls:
            if not o_url in store:
                store[o_url] = {
                        'incoming': set((current_url,)),
                        'outgoing': set()
                        }
                new_urls.add (o_url)
            else:
                store[o_url]['incoming'].add(current_url)

        # track 'outgoing' links
        if not current_url in store:
            store[current_url] = {
                    'incoming': set(),
                    'outgoing': set(outgoing_urls)
                    }
        else:
            store[current_url]['outgoing'].update(set(outgoing_urls))

        return new_urls


def main():
    """ Program entry point, parameters set by program arguments.
    """
    # parse program arguments.
    args = ARGS.parse_args()

    # initialize logger format and level.
    set_loglevel(args.loglevel)
    logging.basicConfig(format=_LOG_FMT)

    # display all command argument values in debug mode.
    if logging.getLogger().isEnabledFor(logging.DEBUG):
        for key, val in args._get_kwargs():
            logging.debug('arg {}: {}'.format(key, val))

    # verify remaining program arguments.
    assert urllib.parse.urlparse(args.url).scheme in ('http', 'https'), (
            "{!r} is not a valid hyptertext url".format(args.url))
    assert args.nthreads > 0, (
            "number of threads must be positive ({}).".format(args.nthreads))
    assert args.limit > 0, (
        "url fetch limit must be positive ({}).".format(args.limit))
    assert args.delay >= 0.0, (
        "timed delay must be non-negative ({}).".format(args.delay))
    assert (args.queue and
            args.queue.lower() in ('fifo', 'lifo')), ("queue '{}' invalid, "
                "must be one of: fifo, lifo.".format(args.queue))

    # initialize output stream.
    if args.out is not None:
        f_out = open_filepath(args.out)
    else:
        f_out = sys.__stdout__

    # initialize input url queue and output data store.
    url_queue = (
            LifoQueue_Limited() if args.queue.lower() == 'lifo'
            else FifoQueue_Limited())
    url_queue.put(args.url)
    url_store = dict()

    # initialize threads.
    url_lock = threading.Lock()
    threads = [Fetch(url_queue, url_store, url_lock, args.limit, args.delay)
            for n in range(args.nthreads)]

    # startup threads.
    [thread.start() for thread in threads]

    # block until url_queue is exhausted.
    url_queue.join()

    # shutdown threads.
    [thread.stop() for thread in threads]

    logging.info('{} URLs discovered, writing report.'.format(len(url_store)))

    [thread.join() for thread in threads]

    # report results.
    json.dump(url_store, f_out, sort_keys=True, cls=JSONSetEncoder,
            indent=4, separators=(',', ':'))

if __name__ == '__main__':
    main()
