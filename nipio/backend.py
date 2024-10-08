#!/usr/bin/python
# Copyright 2019 Exentrique Solutions Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import ConfigParser
import os
import re
import sys


def _is_debug():
    return False


def _log(msg):
    sys.stderr.write('backend (%s): %s\n' % (os.getpid(), msg))


def _write(*l):
    args = len(l)
    c = 0
    for a in l:
        c += 1
        if _is_debug():
            _log('writing: %s' % a)
        sys.stdout.write(a)
        if c < args:
            if _is_debug():
                _log('writetab')
            sys.stdout.write('\t')
    if _is_debug():
        _log('writenewline')
    sys.stdout.write('\n')
    sys.stdout.flush()


def _get_next():
    if _is_debug():
        _log('reading now')
    line = sys.stdin.readline()
    if _is_debug():
        _log('read line: %s' % line)
    return line.strip().split('\t')


class DynamicBackend:
    def __init__(self):
        self.id = ''
        self.soa = ''
        self.domain = ''
        self.ip_address = ''
        self.ttl = ''
        self.name_servers = {}
        self.static = {}
        self.blacklisted_ips = []
        self.acme_challenge = []

    def configure(self):
        fname = self._get_config_filename()
        if not os.path.exists(fname):
            _log('%s does not exist' % fname)
            sys.exit(1)

        with open(fname) as fp:
            config = ConfigParser.ConfigParser()
            config.readfp(fp)

        self.id = config.get('soa', 'id')
        self.soa = '%s %s %s' % (config.get('soa', 'ns'), config.get('soa', 'hostmaster'), self.id)
        self.domain = config.get('main', 'domain')
        self.ip_address = config.get('main', 'ipaddress')
        self.ttl = config.get('main', 'ttl')
        if config.has_section("acme"):
            for entry in config.items("acme"):
                self.acme_challenge.append(entry[1])

        for entry in config.items('nameservers'):
            self.name_servers[entry[0]] = entry[1]
        if config.has_section("static"):
            for entry in config.items('static'):
                self.static[entry[0]] = entry[1]

        if config.has_section("blacklist"):
            for entry in config.items("blacklist"):
                self.blacklisted_ips.append(entry[1])

        _log('Name servers: %s' % self.name_servers)
        _log('Static resolution: %s' % self.static)
        _log('ID: %s' % self.id)
        _log('TTL %s' % self.ttl)
        _log('SOA: %s' % self.soa)
        _log('IP Address: %s' % self.ip_address)
        _log('DOMAIN: %s' % self.domain)
        _log("Blacklist: %s" % self.blacklisted_ips)
        _log('ACME challenge: %s' % self.acme_challenge)

    def run(self):
        _log('starting up')
        handshake = _get_next()
        if handshake[1] != '1':
            _log('Not version 1: %s' % handshake)
            sys.exit(1)
        _write('OK', 'We are good')
        _log('Done handshake')

        while True:
            cmd = _get_next()
            if _is_debug():
                _log("cmd: %s" % cmd)

            if cmd[0] == "END":
                _log("completing")
                break

            if len(cmd) < 6:
                _log('did not understand: %s' % cmd)
                _write('FAIL')
                continue

            qname = cmd[1].lower()
            qtype = cmd[3]

            if (qtype == 'A' or qtype == 'ANY') and qname.endswith(self.domain):
                if qname in self.static:
                    self.handle_static(qname)
                elif qname == self.domain:
                    self.handle_self(self.domain)
                elif qname in self.name_servers:
                    self.handle_nameservers(qname)
                elif qname == '_acme-challenge.' + self.domain and self.acme_challenge:
                    self.handle_acme(qname)
                else:
                    self.handle_subdomains(qname)
            elif qtype == 'SOA' and qname.endswith(self.domain):
                self.handle_soa(qname)
            elif qtype == 'TXT' and qname == '_acme-challenge.' + self.domain and self.acme_challenge:
                self.handle_acme(qname)
            else:
                self.handle_unknown(qtype, qname)

    def handle_acme(self, name):
        if _is_debug():
            _log("handle acme: %s" % name)
        _write('DATA', name, 'IN', 'A', self.ttl, self.id, self.ip_address)
        for challenge in self.acme_challenge:
            _write('DATA', name, 'IN', 'TXT', self.ttl, self.id, challenge)
        self.write_name_servers(name)
        _write('END')

    def handle_static(self, qname):
        if _is_debug():
            _log("handle static: %s" % qname)
        ip = self.static[qname]
        _write('DATA', qname, 'IN', 'A', self.ttl, self.id, ip)
        self.write_name_servers(qname)
        _write('END')

    def handle_self(self, name):
        if _is_debug():
            _log("handle self: %s" % name)
        _write('DATA', name, 'IN', 'A', self.ttl, self.id, self.ip_address)
        self.write_name_servers(name)
        _write('END')
    def is_valid_ip(self, ip_address_parts):
        for part in ip_address_parts:
            if re.match('^\d{1,3}$', part) is None:
                return False
            part_int = int(part)
            if part_int < 0 or part_int > 255:
                return False
        return True

    def handle_subdomains(self, qname):
        _log('resolve: %s' % qname)
        subdomain = qname[0:qname.find(self.domain) - 1]

        subparts = self._split_subdomain(subdomain)
        if len(subparts) < 4:
            if _is_debug():
                _log('subparts less than 4')
            self.handle_self(qname)
            return

        ip_address_parts = None

        if len(subparts) >= 4 and self.is_valid_ip(subparts[:4]):
            ip_address_parts = subparts[:4]
        elif len(subparts) >= 4 and self.is_valid_ip(subparts[-4:]):
            ip_address_parts = subparts[-4:]
        else:
            if _is_debug():
                _log('No valid IP found in: %s' % subparts)
            self.handle_self(qname)
            return

        if _is_debug():
            _log('ip: %s' % ip_address_parts)

        ip_address = ".".join(ip_address_parts)
        if ip_address in self.blacklisted_ips:
            self.handle_blacklisted(ip_address)
            return

        _write('DATA', qname, 'IN', 'A', self.ttl, self.id, '%s.%s.%s.%s' % (ip_address_parts[0], ip_address_parts[1], ip_address_parts[2], ip_address_parts[3]))
        self.write_name_servers(qname)
        _write('END')

    def handle_nameservers(self, qname):
        if _is_debug():
            _log("handle nameservers: %s" % qname)
        ip = self.name_servers[qname]
        _write('DATA', qname, 'IN', 'A', self.ttl, self.id, ip)
        _write('END')

    def write_name_servers(self, qname):
        for nameServer in self.name_servers:
            _write('DATA', qname, 'IN', 'NS', self.ttl, self.id, nameServer)

    def handle_soa(self, qname):
        if _is_debug():
            _log("handle soa: %s" % qname)
        _write('DATA', qname, 'IN', 'SOA', self.ttl, self.id, self.soa)
        _write('END')

    def handle_unknown(self, qtype, qname):
        _write('LOG', 'Unknown type: %s, domain: %s' % (qtype, qname))
        _write('END')

    def handle_blacklisted(self, ip_address):
        _write('LOG', 'Blacklisted: %s' % ip_address)
        _write('END')

    def _get_config_filename(self):
        return os.path.join(os.path.dirname(os.path.realpath(__file__)), 'backend.conf')

    def _split_subdomain(self, subdomain):
        return re.split("[.-]", subdomain)


if __name__ == '__main__':
    backend = DynamicBackend()
    backend.configure()
    backend.run()
