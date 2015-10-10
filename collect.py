#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
# vim: autoindent expandtab tabstop=4 sw=4 sts=4 filetype=python

"""Parse the national elections results website of the Canton of Bern"""

import bs4
import urllib.request as req
import re
import string

base_url = 'http://www.wahlarchiv.sites.be.ch/wahlen2011/target/'
overview_path = 'GemeindenUebersichtAction.do@method=read&sprache=d.html'
commune_pattern = re.compile(r'.*gem=\d{3}.html')


class Commune(object):
    """Holds the results for a commune"""

    def __init__(self, name, path):
        self.name = name
        self.path = path
        self.absolute_votes = 0
        self.relative_votes = 0.0


def get_html(url):
    """Returns a BeautifulSoup object of the given url"""
    page = req.urlopen(url)
    return bs4.BeautifulSoup(page, 'html5lib')


def get_results():
    """Returns all the (temporary) results as an object"""
    html = get_html('{}{}'.format(base_url, overview_path))
    commune_list = html.findAll('a', {'href': commune_pattern})
    for commune in commune_list:
        commune_object = Commune(
            commune.get_text().strip(),
            commune.attrs['href'].strip(),
        )
        print('Parsing {}...'.format(commune_object.name))
        fill_commune(commune_object)


def fill_commune(commune):
    """Fills a given Commune object with the results"""
    html = get_html('{}{}'.format(base_url, commune.path))
    party_td = html.find('td', text='PIRATEN / PIRATES')
    absolute_td = party_td.find_next_sibling('td')
    relative_td = absolute_td.find_next_sibling('td')
    commune.absolute_votes = int(absolute_td.text.strip())
    commune.relative_votes = float(
        relative_td.text.strip('{}{}'.format(string.whitespace, '%'))
    )
    print('Votes: {} ({}%)\n'.format(
        commune.absolute_votes,
        commune.relative_votes
    ))


get_results()
