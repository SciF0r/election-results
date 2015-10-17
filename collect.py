#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
# vim: autoindent expandtab tabstop=4 sw=4 sts=4 filetype=python

"""Parse the national elections results website of the Canton of Bern"""

import bs4
import csv
import datetime
import hashlib
import io
import jinja2
import os
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
    'entitled': 0,
    'voted': 0,
    'empty': 0,
    'invalid': 0,
    'valid': 0,
}
list_results = {}
candidate_results = {}
lists = {}
ignore_cache = 'IGNORE_CACHE' in os.environ.keys()


class List(object):
    """Holds the results for a list"""

    def __init__(self, number, name):
        self.name             = name
        self.number           = number
        self.short            = ''
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
        self._commune_id   = 0
        self._in_header    = True
        self._current_list = None

    def get_votes_relative(self, list_number):
        """Returns the percentage of list votes received"""
        return round(
            100 * self.lists[list_number].list_votes / self.all_votes,
            2
        )

    def read_header_row(self, row):
        """Handles a row in header context"""
        if row[0] == STR['entitled']:
            self.entitled = get_csv_int(row[1])
            vote_results['entitled'] += self.entitled
        elif row[0] == STR['voted']:
            self.voted = get_csv_int(row[1])
            vote_results['voted'] += self.voted
        elif row[0] == STR['empty']:
            self.empty = get_csv_int(row[1])
            vote_results['empty'] += self.empty
        elif row[0] == STR['invalid']:
            self.invalid = get_csv_int(row[1])
            vote_results['invalid'] += self.invalid
        elif row[0] == STR['valid']:
            self.valid = get_csv_int(row[1])
            vote_results['valid'] += self.valid
        elif row[0] == STR['all_votes']:
            self.all_votes = get_csv_int(row[2])
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
        elif row[0] == STR['short']:
            self._current_list.short = row[1]
        elif row[0] == STR['direct_votes']:
            self._current_list.direct_votes = get_csv_int(row[1])
        elif row[0] == STR['additional_votes']:
            self._current_list.additional_votes = get_csv_int(row[1])
        elif row[0] == STR['list_votes']:
            list_votes = get_csv_int(row[1])
            self._current_list.list_votes = list_votes
            list_number = self._current_list.number
            if list_number not in list_results.keys():
                list_results[list_number] = 0
                lists[list_number] = {
                    'name': self._current_list.name,
                    'short': self._current_list.short,
                }
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

    def get_invalid_relative(self):
        """Returns the percentage of invalid votes received"""
        return round(100 * self.invalid / self.voted, 2)

    def _add_candidate(self, first_name, last_name, votes):
        """Add a new candidate to the Commune"""
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

    def get_commune_id(self):
        if self._commune_id == 0:
            match = COMMUNE_PATTERN.search(self.path)
            if not match:
                print('No commune id found for {}'.format(self.name))
                return
            self._commune_id = int(match.group(1))
        return self._commune_id

    def get_csv_link(self):
        return '{}{}'.format(
            URL['base'],
            URL['csv'].format(self.get_commune_id())
        )

    def fill(self):
        """Fills Commune object with the results"""
        csv_path = 'cache/{}.csv'.format(self.get_commune_id())
        if ignore_cache or not os.path.exists(csv_path):
            self.download_csv(self.get_commune_id(), csv_path)
        with open(csv_path, 'r') as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=';')
            for row in csv_reader:
                if self._in_header:
                    self.read_header_row(row)
                else:
                    self.read_party_row(row)

    def download_csv(self, commune_id, path):
        """Download the corresponding CSV file to given path"""
        print('d', end='', flush=True)
        try:
            csv_data = req.urlopen(self.get_csv_link()).read()
            with open(path, 'w') as csv_file:
                csv_file.write(csv_data.decode('latin1', 'ignore'))
            with open('{}.meta'.format(path), 'a') as meta_file:
                meta_file.write('{}: {}\n'.format(
                    datetime.datetime.now(),
                    hashlib.sha256(
                        open(path, 'rb').read()
                    ).hexdigest()
                ))
        except url_error.HTTPError as e:
            raise RuntimeError(
                'Could not download CSV file for {}: {}'.format(self.name, e)
            )


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

    def candidates_sorted(self, list_number):
        """Return the candidates of a list, sorted by votes received"""
        list_ = candidate_results[list_number]
        return sorted(
            list_.items(),
            key=lambda x: x[1],
            reverse=True
        )

    def list_results(self, list_number):
        """Returns the absolute and relative votes received in the whole canton"""
        list_votes = list_results[list_number]
        return {
            'absolute': list_votes,
            'relative': round(100 * list_votes / vote_results['all_votes'], 2)
        }

    def lists_ordered(self):
        """Returns the list results ordered by votes"""
        return sorted(
            lists.items(),
            key=lambda x: self.list_results(x[0])['absolute'],
            reverse=True
        )

    def turnout_relative(self):
        """Returns the turnout percentage of these elections"""
        return round(100 * vote_results['voted'] / vote_results['entitled'], 2)

    def invalid_relative(self):
        """Returns the percentage of invalid votes in the whole canton"""
        return round(100 * vote_results['invalid'] / vote_results['voted'], 2)


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
            election=election,
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
