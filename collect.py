#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
# vim: autoindent expandtab tabstop=4 sw=4 sts=4 filetype=python

"""Parse the national elections results website of the Canton of Bern"""

import bs4
import csv
import io
import urllib.request as req
import re

URL = {
    'base'     : 'http://www.wahlarchiv.sites.be.ch/wahlen2011/target/',
    'overview' : 'GemeindenUebersichtAction.do@method=read&sprache=d.html',
    'csv'      : 'pdfs/waehleranteileGemeinde{}.csv',
}
COMMUNE_PATTERN = re.compile(r'.*gem=(\d{3}).html')
LIST_NAME = 'PIRATEN / PIRATES'

STR = {
    'entitled'         : 'Wahlberechtigte / Nombre d\'électeurs',
    'voted'            : 'Eingelangte Wahlzettel / Bulletins rentrés',
    'empty'            : 'Leere Wahlzettel / Blancs',
    'invalid'          : 'Ungültige Wahlzettel / Nuls',
    'valid'            : 'Gültige Wahlzettel / Bulletins valables',
    'turnout'          : 'Wahlbeteiligung / Participation électorale',
    'short'            : 'Kürzel / Sigle',
    'direct_votes'     : 'Kandidatenstimmen /Total des suffrages nominatifs',
    'additional_votes' : 'Zusatzstimmen / Suffrages complémentaires',
    'list_votes'       : 'Parteistimmen / Total des suffrages de parti',
}


class Commune(object):
    """Holds the results for a commune"""

    def __init__(self, name, path):
        self.name             = name
        self.path             = path
        self.absolute_votes   = 0
        self.relative_votes   = 0.0
        self.entitled         = 0
        self.voted            = 0
        self.empty            = 0
        self.invalid          = 0
        self.valid            = 0
        self.turnout          = 0.0
        self.direct_votes     = 0
        self.additional_votes = 0
        self.list_votes       = 0
        self.candidates       = []
        self._in_header       = True
        self._in_party        = False

    def read_header_row(self, row):
        """Handles a row in header context"""
        if len(row) == 4 and row[1] == LIST_NAME:
            self.absolute_votes = get_csv_int(row[2])
            self.relative_votes = get_csv_float(row[3])
        if len(row) == 2:
            if row[0] == STR['entitled']:
                self.entitled = get_csv_int(row[1])
            if row[0] == STR['voted']:
                self.voted = get_csv_int(row[1])
            if row[0] == STR['empty']:
                self.empty = get_csv_int(row[1])
            if row[0] == STR['invalid']:
                self.invalid = get_csv_int(row[1])
            if row[0] == STR['valid']:
                self.valid = get_csv_int(row[1])
            if row[0] == STR['turnout']:
                self.turnout = get_csv_float(row[1])
                self._in_header = False

    def read_party_row(self, row):
        """Handles a row in party context"""
        if row[0] == STR['direct_votes']:
            self.direct_votes = get_csv_int(row[1])
        elif row[0] == STR['additional_votes']:
            self.additional_votes = get_csv_int(row[1])
        elif row[0] == STR['list_votes']:
            self.list_votes = get_csv_int(row[1])
        elif len(row) == 9:
            try:
                self.candidates.append({
                    'last_name': row[1].strip(),
                    'first_name': row[2].strip(),
                    'votes': get_csv_int(row[6]),
                })
            except ValueError:
                pass

    def fill(self):
        """Fills Commune object with the results"""
        match = COMMUNE_PATTERN.search(self.path)
        if not match:
            print('No commune id found for {}'.format(self.name))
            return
        csv_link = '{}{}'.format(
            URL['base'],
            URL['csv'].format(match.group(1))
        )
        csv_data = req.urlopen(csv_link).read().decode('latin1', 'ignore')
        csv_reader = csv.reader(io.StringIO(csv_data), delimiter=';')
        for row in csv_reader:
            if self._in_header:
                self.read_header_row(row)
            else:
                if not self._in_party:
                    if row[0] == STR['short'] and row[1] == LIST_NAME:
                        self._in_party = True
                    continue
                self.read_party_row(row)
                if row[0] == 'Liste':
                    break

        print('Votes: {} ({}%)\n{}'.format(
            self.absolute_votes,
            self.relative_votes,
            self.candidates
        ))


def get_html(url):
    """Returns a BeautifulSoup object of the given url"""
    page = req.urlopen(url)
    return bs4.BeautifulSoup(page, 'html5lib')


def get_results():
    """Returns all the (temporary) results as an object"""
    html = get_html('{}{}'.format(URL['base'], URL['overview']))
    commune_list = html.findAll('a', {'href': COMMUNE_PATTERN})
    for commune in commune_list:
        commune_object = Commune(
            commune.get_text().strip(),
            commune.attrs['href'].strip(),
        )
        print('Parsing {}...'.format(commune_object.name))
        commune_object.fill()


def get_csv_int(str_):
    """Return the int representation from a csv string"""
    return int(str_.strip().replace('\'', ''))


def get_csv_float(str_):
    """Return the float representation from a csv string"""
    return float(str_.strip().replace('\'', '').replace('%', ''))




get_results()
