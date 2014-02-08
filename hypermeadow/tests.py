#!/usr/bin/env python3
"""
Jeff Quast <contact@jeffquast.com>
Competed Fri Sep 13
"""
from hyperlinks import LifoQueue_Limited, FifoQueue_Limited, JSONSetEncoder
from hyperlinks import open_filepath, set_loglevel, Fetch
from nose.tools import eq_

def test_LifoQueue_Limited():
    """ Test LifoQueue increments num_inserts correctly. """
    queue = LifoQueue_Limited()
    for n in range(100):
        queue.put(n)
    for n in range(100):
        queue.get()
    eq_(queue.num_inserts, 100)

def test_FifoQueue_Limited():
    """ Test FifoQueue increments num_inserts correctly. """
    queue = FifoQueue_Limited()
    for n in range(100):
        queue.put(n)
    for n in range(100):
        queue.get()
    eq_(queue.num_inserts, 100)

def test_json_encode_set():
    """ Test JSONSetEncoder encodes all items of set() instance. """
    import json
    alphabet = 'abcdefghijklmnopqrstuvwxyz'
    output = json.dumps(set(alphabet), cls=JSONSetEncoder, sort_keys=True)
    for alpha in alphabet:
        assert '"{}"'.format(alpha) in output, output

def test_fail_open_nonexistant_dir():
    """ Test that program refuses to write to non-existant directory. """
    try:
        open_filepath('ab/cd/ef/gh/ij/kl')
        assert False, "should have raised assertion"
    except AssertionError as err:
        assert err.args[0].startswith('directory'), err.args[0]
        assert err.args[0].endswith('does not exist.'), err.args[0]

def test_fail_cannot_write_to_folder():
    """ Test that program refuses to write to directory without write access. """
    try:
        open_filepath('/test.write')
        assert False, "should have raised assertion"
    except AssertionError as err:
        assert err.args[0].startswith('directory'), err.args[0]
        assert 'is not writable' in err.args[0], err.args[0]
        assert err.args[0].endswith('does not exist.'), err.args[0]

def test_fail_cannot_write_to_file():
    """ Test that program refuses to write to file without write access. """
    import os
    assert not os.path.exists('/tmp/test-minus-r')
    fp = open('/tmp/test-minus-r', 'w')
    fp.write('')
    fp.close()
    os.chmod('/tmp/test-minus-r', 0)
    assert os.path.isfile('/tmp/test-minus-r')
    try:
        open_filepath('/tmp/test-minus-r')
        assert False, "should have raised assertion"
    except AssertionError as err:
        assert err.args[0].startswith('no write access to'), err.args[0]
        assert err.args[0].endswith('/tmp/test-minus-r.'), err.args[0]
    os.unlink('/tmp/test-minus-r')

def test_fail_cannot_write_to_special_dev():
    """ Test that program refuses to write to special device. """
    # not necessarily something to prevent from a power user ... but
    # something to prevent from automated programs: such as
    # following a maliciously plotted symlink.
    try:
        open_filepath('/dev/stdout')
        assert False, "should have raised assertion"
    except AssertionError as err:
        assert err.args[0].startswith('/dev/stdout'), err.args[0]
        assert err.args[0].endswith('is not a file.'), err.args[0]

def test_set_loglevel_correctly():
    """ Test that --loglevel string->const procedure behaves correctly. """
    import logging
    logger = logging.getLogger()
    set_loglevel('debug')
    eq_(logger.isEnabledFor(logging.DEBUG), True)
    set_loglevel('info')
    eq_(logger.isEnabledFor(logging.INFO), True)
    eq_(logger.isEnabledFor(logging.DEBUG), False)
    set_loglevel('warn')
    eq_(logger.isEnabledFor(logging.WARN), True)
    eq_(logger.isEnabledFor(logging.DEBUG), False)
    eq_(logger.isEnabledFor(logging.INFO), False)
    set_loglevel('error')
    eq_(logger.isEnabledFor(logging.ERROR), True)
    eq_(logger.isEnabledFor(logging.WARN), False)
    eq_(logger.isEnabledFor(logging.DEBUG), False)
    eq_(logger.isEnabledFor(logging.INFO), False)
    set_loglevel('debug')

def test_set_loglevel_incorrectly():
    """ Test that --loglevel string->const procedure misbehaves correctly. """
    try:
        set_loglevel('invalid')
        assert False, "should have raised assertion"
    except AssertionError as err:
        assert 'not a valid loglevel' in err.args[0], err.args
    try:
        set_loglevel('')
        assert False, "should have raised assertion"
    except AssertionError as err:
        assert 'not a valid loglevel' in err.args[0], err.args
    try:
        set_loglevel(None)
        assert False, "should have raised assertion"
    except AssertionError as err:
        assert err.args[0] is None, err.args[0]

def test_fetch_badargs():
    """ Test that bad arguments to Fetch() raise Assertions and TypeErrors. """
    import queue, threading
    try:
        Fetch()
        assert False, "should have raised assertion"
    except TypeError as err:
        assert err.args[0].startswith(
                '__init__() missing 3 required positional arguments:'
                ), err.args[0]
    try:
        Fetch(url_queue=0, url_store=0, url_lock=0)
        assert False, "should have raised assertion"
    except AssertionError as err:
        assert err.args[0] == 0, err.args
    try:
        Fetch(url_queue=queue.Queue(), url_store=0, url_lock=0)
        assert False, "should have raised assertion"
    except AssertionError as err:
        assert err.args[0] == 0, err.args
    try:
        Fetch(url_queue=queue.Queue(), url_store=dict(), url_lock=0)
        assert False, "should have raised assertion"
    except AssertionError as err:
        assert err.args[0] == 0, err.args
    try:
        Fetch(url_queue=queue.Queue(), url_store=dict(),
                url_lock=threading.Lock(), max_urls=0)
        assert False, "should have raised assertion"
    except AssertionError as err:
        assert err.args[0] == 0, err.args
    try:
        Fetch(url_queue=queue.Queue(), url_store=dict(),
                url_lock=threading.Lock(), max_urls=1,
                delay=-1)
        assert False, "should have raised assertion"
    except AssertionError as err:
        assert err.args[0] == -1, err.args

def test_fetch_goodargs():
    """ Test simple and correct instantiation of Fetch. """
    import queue, threading
    Fetch(url_queue=queue.Queue(), url_store=dict(), url_lock=threading.Lock())

def test_stop_fetch():
    """ Test that Fetch can be started and stopped correctly. """
    import queue, threading
    iq = queue.Queue()
    iq.put('http://nonexistant')
    f = Fetch(url_queue=iq, url_store=dict(), url_lock=threading.Lock())
    eq_(f.isAlive(), False)
    f.start()
    eq_(f.isAlive(), True)
    eq_(f._force_ending, False)
    f.stop()
    eq_(f._force_ending, True)
    f.join()
    eq_(f.isAlive(), False)

def test_discover_urls():
    """ Test that hyperlinks are discovered or ignored correctly. """
    import queue, threading
    f = Fetch(url_queue=queue.Queue(), url_store=dict(), url_lock=threading.Lock())
    body = """
    <html><body>
    <a href='/a' />
    <a href='/b' />
    <a href='./c' />
    <a href='../d' />
    <a href='http://othersite/' />
    <a href='http://othersite/e' />
    <a href='http://othersite/e#foo' />
    <a href='mailto:contact@jeffquast.com' />
    <a not always as it seems! />
    </body></html>
    """
    urls = f.discover_urls('http://nonexistant/x/', body)
    eq_(urls, ['http://nonexistant/a',
               'http://nonexistant/b',
               'http://nonexistant/x/c',
               'http://nonexistant/d',
               'http://othersite/',
               'http://othersite/e',
               'http://othersite/e#foo',
               ])

def test_store_urldata():
    """ Test that hyperlink relationships are modelled correctly. """
    import queue, threading
    f = Fetch(url_queue=queue.Queue(), url_store=dict(), url_lock=threading.Lock())
    test_dict = dict()
    o_urls = ['http://nonexistant/a',
            'http://nonexistant/b',
            'http://nonexistant/x/c',
            'http://nonexistant/d',
            'http://othersite/',
            'http://othersite/e',
            'http://othersite/e#foo',
            ]
    f.store_urldata(current_url='http://nonexistant/x/',
            outgoing_urls=o_urls, store=test_dict)
    eq_(len(test_dict['http://nonexistant/x/']['outgoing']), len(o_urls))
    eq_(len(test_dict['http://nonexistant/x/']['incoming']), 0)
    eq_(len(test_dict['http://nonexistant/d']['incoming']), 1)
    eq_(len(test_dict), len(o_urls) + 1)
    # 'd' points back to 'x', should increment x's "incoming" to 1
    f.store_urldata(current_url='http://nonexistant/d',
            outgoing_urls=['http://nonexistant/x/',], store=test_dict)
    eq_(len(test_dict['http://nonexistant/x/']['outgoing']), len(o_urls))
    eq_(len(test_dict['http://nonexistant/x/']['incoming']), 1)  # *
    eq_(len(test_dict['http://nonexistant/d']['incoming']), 1)
    eq_(len(test_dict), len(o_urls) + 1)
    # exact same entry added again; no change
    f.store_urldata(current_url='http://nonexistant/d',
            outgoing_urls=['http://nonexistant/x/',], store=test_dict)
    eq_(len(test_dict['http://nonexistant/x/']['outgoing']), len(o_urls))
    eq_(len(test_dict['http://nonexistant/x/']['incoming']), 1)  # *
    eq_(len(test_dict['http://nonexistant/d']['incoming']), 1)
    eq_(len(test_dict), len(o_urls) + 1)
