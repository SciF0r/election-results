#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# vim: autoindent expandtab tabstop=4 sw=4 sts=4 filetype=python

"""Parse the national elections results website of the Canton of Bern"""

import urllib.request as req
import bs4
import re

base_url = 'http://www.wahlarchiv.sites.be.ch/wahlen2011/target/'
overview_path = 'GemeindenUebersichtAction.do@method=read&sprache=d.html'
commune_pattern = re.compile(r'.*gem=\d{3}.html')


def get_html(url):
    """Returns a BeautifulSoup object of the given url"""
    page = req.urlopen(url)
    return bs4.BeautifulSoup(page, 'html5lib')


def get_results():
    """Returns all the (temporary) results as an object"""
    html = get_html('{}{}'.format(base_url, overview_path))
    commune_list = html.findAll('a', {'href': commune_pattern})
    for commune in commune_list:
        print('Parsing {}...\n'.format(commune.get_text()))
        parse_commune(commune.attrs['href'])


def parse_commune(path):
    """Returns the results for a given (commune) path"""
    html = get_html('{}{}'.format(base_url, overview_path))


get_results()
