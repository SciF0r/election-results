#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
# vim: autoindent expandtab tabstop=4 sw=4 sts=4 filetype=python

"""Parse the national elections results website of the Canton of Bern"""

import bs4
import csv
import io
import jinja2
import urllib.request as req
import urllib.error   as url_error
import re

URL = {
    'base'     : 'http://www.wahlarchiv.sites.be.ch/wahlen2011/target/',
    'overview' : 'GemeindenUebersichtAction.do@method=read&sprache=d.html',
    'csv'      : 'pdfs/waehleranteileGemeinde{}.csv',
}
COMMUNE_PATTERN = re.compile(r'.*gem=(\d{3}).html')

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
    'all_votes'        : 'Total',
    'list'             : 'Liste',
}

vote_results = {
    'all_votes': 0,
}
list_results = {}
candidate_results = {}
lists = {}


class List(object):
    """Holds the results for a list"""

    def __init__(self, number, name):
        self.name = name
        self.number = number
        self.direct_votes     = 0
        self.additional_votes = 0
        self.list_votes       = 0
        self.candidates       = []


class Commune(object):
    """Holds the results for a commune"""

    def __init__(self, name, path):
        self.name          = name
        self.path          = path
        self.entitled      = 0
        self.voted         = 0
        self.empty         = 0
        self.invalid       = 0
        self.valid         = 0
        self.all_votes     = 0
        self.turnout       = 0.0
        self.lists         = {}
        self._in_header    = True
        self._current_list = None

    def get_votes_relative(self, list_number):
        return round(
            100 * self.lists[list_number].list_votes / self.all_votes,
            2
        )

    def read_header_row(self, row):
        """Handles a row in header context"""
        if row[0] == STR['entitled']:
            self.entitled = get_csv_int(row[1])
        elif row[0] == STR['voted']:
            self.voted = get_csv_int(row[1])
        elif row[0] == STR['empty']:
            self.empty = get_csv_int(row[1])
        elif row[0] == STR['invalid']:
            self.invalid = get_csv_int(row[1])
        elif row[0] == STR['valid']:
            self.valid = get_csv_int(row[1])
        elif row[0] == STR['all_votes']:
            self.all_votes = get_csv_int(row[2])
            global vote_results
            vote_results['all_votes'] += self.all_votes
        elif row[0] == STR['turnout']:
            self.turnout = get_csv_float(row[1])
            self._in_header = False

    def read_party_row(self, row):
        """Handles a row in party context"""
        if row[0] == STR['list']:
            list_number = get_csv_int(row[1])
            list_name   = row[2]
            self._current_list = List(list_number, list_name)
            self.lists[list_number] = self._current_list
        elif row[0] == STR['direct_votes']:
            self._current_list.direct_votes = get_csv_int(row[1])
        elif row[0] == STR['additional_votes']:
            self._current_list.additional_votes = get_csv_int(row[1])
        elif row[0] == STR['list_votes']:
            list_votes = get_csv_int(row[1])
            self._current_list.list_votes = list_votes
            global list_results
            list_number = self._current_list.number
            if list_number not in list_results.keys():
                list_results[list_number] = 0
                lists[list_number] = self._current_list.name
            list_results[list_number] += list_votes
        elif len(row) == 9 and row[1] != 'Name' and row[1] != 'Nom':
            try:
                first_name = row[1]
                last_name  = row[2]
                votes      = get_csv_int(row[6])
                self._add_candidate(first_name, last_name, votes)
            except ValueError:
                pass

    def get_list(self, number):
        try:
            return self.lists[number]
        except KeyError:
            print('Could not get list {} for commune {}'.format(
                number,
                self.name
            ))

    def _add_candidate(self, first_name, last_name, votes):
        global candidate_results
        self._current_list.candidates.append({
            'first_name': first_name,
            'last_name': last_name,
            'votes': votes,
        })
        full_name = '{} {}'.format(first_name, last_name)
        list_number = self._current_list.number
        if list_number not in candidate_results:
            candidate_results[list_number] = {}
        if full_name not in candidate_results[list_number]:
            candidate_results[list_number][full_name] = 0
        candidate_results[list_number][full_name] += votes

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

        try:
            csv_data = req.urlopen(csv_link).read().decode('latin1', 'ignore')
        except url_error.HTTPError as e:
            raise RuntimeError(
                'Could not open CSV file for {}: {}'.format(self.name, e)
            )
        csv_reader = csv.reader(io.StringIO(csv_data), delimiter=';')
        for row in csv_reader:
            if self._in_header:
                self.read_header_row(row)
            else:
                self.read_party_row(row)


class Election(object):
    """Collect election results"""

    def __init__(self):
        self.communes = []

    def collect(self):
        """Collect all the temporary results"""
        print('Collecting...')
        html = get_html('{}{}'.format(URL['base'], URL['overview']))
        commune_list = html.findAll('a', {'href': COMMUNE_PATTERN})
        commune_results = []
        for commune in commune_list:
            commune_object = Commune(
                commune.get_text().strip(),
                commune.attrs['href'].strip(),
            )
            print('.', end='', flush=True)
            try:
                commune_object.fill()
                self.communes.append(commune_object)
            except RuntimeError as e:
                print(e)
            return

    def candidates_sorted(self, list_number):
        list_ = candidate_results[list_number]
        return sorted(
            list_.items(),
            key=lambda x: x[1],
            reverse=True
        )

    def list_results(self, list_number):
        list_votes = list_results[list_number]
        return {
            'absolute': list_votes,
            'relative': round(100 * list_votes / vote_results['all_votes'], 2)
        }


def get_html(url):
    """Returns a BeautifulSoup object of the given url"""
    page = req.urlopen(url)
    return bs4.BeautifulSoup(page, 'html5lib')


def write_results_html(election):
    """Write the results into an html file"""
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader('templates')
    )
    template = env.get_template('results.html')
    for list_number in list_results.keys():
        template.stream(
            communes=election.communes,
            candidates=election.candidates_sorted(list_number),
            list_results=election.list_results(list_number),
            vote_results=vote_results,
            list_number=list_number,
            lists=lists,
            ordered_lists=sorted(
                lists.items(),
                key=lambda x: x[0]
            )
        ).dump('output/{}.html'.format(list_number))


def get_csv_int(str_):
    """Return the int representation from a csv string"""
    return int(str_.strip().replace('\'', ''))


def get_csv_float(str_):
    """Return the float representation from a csv string"""
    return float(str_.strip().replace('\'', '').replace('%', ''))


election = Election()
election.collect()
write_results_html(election)
