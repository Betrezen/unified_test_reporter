from __future__ import division

import functools
import hashlib
import re

import yaml


MINUTE = 60
HOUR = MINUTE ** 2
DAY = HOUR * 8
WEEK = DAY * 5


def retry(count=3):
    def wrapped(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            i = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except:
                    i += 1
                    if i >= count:
                        raise
        return wrapper
    return wrapped


def duration_to_testrail_estimate(duration):
    """Converts duration in minutes to testrail estimate format
    """
    seconds = duration * MINUTE
    week = seconds // WEEK
    days = seconds % WEEK // DAY
    hours = seconds % DAY // HOUR
    minutes = seconds % HOUR // MINUTE
    estimate = ''
    for val, char in ((week, 'w'), (days, 'd'), (hours, 'h'), (minutes, 'm')):
        if val:
            estimate = ' '.join([estimate, '{0}{1}'.format(val, char)])
    return estimate.lstrip()


def get_sha(input_string):
    """get sha hash

    :param input_string: str - input string
    :return: sha hash string
    """

    return hashlib.sha256(input_string).hexdigest()


def make_cleanup(input_string):
    """clean up string: remove IP/IP6/Mac/etc... by using regexp

    :param input_string: str - input string
    :return: s after regexp and clean up
    """

    # let's try to find all IP, IP6, MAC
    ip4re = re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b')
    ip6re = re.compile(r'\b(?:[a-fA-F0-9]{4}[:|\-]?){8}\b')
    macre = re.compile(r'\b[a-fA-F0-9]{2}[:][a-fA-F0-9]{2}[:]'
                       r'[a-fA-F0-9]{2}[:][a-fA-F0-9]{2}[:]'
                       r'[a-fA-F0-9]{2}[:][a-fA-F0-9]{2}\b')
    digitre = re.compile(r'\b(?:[0-9]{1,3}){1,50}\b')
    hexre = re.compile(r'\b(?:[0-9a-fA-F]{1,8}){1,50}\b')
    # punctuation = re.compile(r'["\'!,?.:;\(\)\{\}\[\]\/\\\<\>]+')

    def ismatch(match):
        """
        :param match: string
        :return: value or ''
        """

        value = match.group()
        return " " if value else value

    stmp = ip4re.sub(ismatch, input_string)
    stmp = ip6re.sub(ismatch, stmp)
    stmp = macre.sub(ismatch, stmp)
    # stmp = punctuation.sub(ismatch, stmp)
    stmp = digitre.sub('x', stmp)
    listhex = hexre.findall(stmp)
    if listhex:
        for i in listhex:
            stmp = hexre.sub('x' * len(i), stmp)
    return stmp


def distance(astr, bstr):
    """Calculates the Levenshtein distance between a and b

    :param astr: str - input string
    :param bstr: str - input string
    :return: distance: int - distance between astr and bstr
    """

    alen, blen = len(astr), len(bstr)
    if alen > blen:
        astr, bstr = bstr, astr
        alen, blen = blen, alen
    current_row = list(range(alen + 1))  # Keep current and previous row
    for i in range(1, blen + 1):
        previous_row, current_row = current_row, [i] + [0] * alen
        for j in range(1, alen + 1):
            add = previous_row[j] + 1
            delete = current_row[j - 1] + 1
            change = previous_row[j - 1]
            if astr[j - 1] != bstr[i - 1]:
                change += 1
            current_row[j] = min(add, delete, change)
    return current_row[alen]

class attrdict(dict):
    """Dictionary with support for attribute syntax.
    d = attrdict({'foo-bar':42, 'baz':777}); d.foo_bar == d['foo-bar']; d.hello = "hello"; d.hello == d['hello']
    """

    def __getattr__(self, name):
        print name
        try:
            return self[name]
        except KeyError:
            pass
        try:
            return self[name.replace('_', '-')]
        except KeyError:
            pass
        raise (AttributeError, 'no such attribute or key: %s' % name)

    def __setattr__(self, name, value):
        self[name] = value

def copy(x):
    """Makes a deep copy of x, replacing dict with attrdict."""
    if isinstance(x, dict):
        d = attrdict()
        for k, v in x.iteritems():
            d[copy(k)] = copy(v)
        return d
    elif isinstance(x, list):
        return map(copy, x)
    return x

def copyx(x):
    """Makes a deep copy of x, replacing attrdict with dict."""
    if isinstance(x, attrdict):
        d = {}
        for k, v in x.iteritems():
            d[copyx(k)] = copyx(v)
        return d
    elif isinstance(x, list):
        return map(copy, x)
    return x

def get_yaml_to_attr(filename):
    return copy(yaml.load(open(filename)))
