#    Copyright 2015 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from __future__ import unicode_literals

import re
import time

import requests
import xmltodict
from cached_property import cached_property
from requests.packages.urllib3 import disable_warnings

from unified_test_reporter.providers.providers import TestResultProvider
from unified_test_reporter.settings import JENKINS
from unified_test_reporter.settings import TestRailSettings
from unified_test_reporter.settings import logger
from unified_test_reporter.pylib.pylib import make_cleanup

disable_warnings()


class Build(TestResultProvider):

    def __init__(self, name, number='latest'):
        """Get build info via Jenkins API, get test info via direct HTTP
        request.

        If number is 'latest', get latest completed build.
        """

        self.name = name
        self.requested_number = number
        self.job_info = self.get_job_info(depth=0)
        self.latest_number = self.job_info["lastCompletedBuild"]["number"]
        self.latest_started = self.job_info["lastBuild"]["number"]
        if number == 'latest':
            self.number = int(self.latest_number)
        elif number == 'latest_started':
            self.number = int(self.latest_started)
        elif number is None:
            self.number = int(self.latest_number)
        else:
            self.number = int(number)
        self.build_data = self.get_build_data(depth=0)
        self.url = self.build_data["url"]
        self.results = self.get_results()
        self.failures = self.get_build_failure_reasons()

    def module_init(self):
        super(Build, self).module_init()

    def get_job_info(self, depth=1):
        job_url = "/".join([JENKINS["url"], 'job',
                            self.name,
                            'api/json?depth={depth}'.format(depth=depth)])
        logger.debug("Request job info from {}".format(job_url))
        return requests.get(job_url).json()

    def get_build_data(self, depth=1):
        build_url = "/".join([JENKINS["url"], 'job',
                              self.name,
                              str(self.number),
                              'api/json?depth={depth}'.format(depth=depth)])
        logger.debug("Request build data from {}".format(build_url))
        return requests.get(build_url).json()

    def get_job_console(self):
        job_url = "/".join([JENKINS["url"], 'job', self.name,
                            str(self.number), 'consoleText'])
        logger.debug("Request job console from {}".format(job_url))
        return requests.get(job_url).text.split('\n')

    def get_environment_variables(self):
        build_url = "/".join([JENKINS["url"], 'job',
                              self.name,
                              str(self.number),
                              'injectedEnvVars',
                              'api/json'])
        logger.debug("Request Environment variables from {}".format(build_url))
        return requests.get(build_url).json()

    @staticmethod
    def get_build_artifact(url, artifact):
        """Return content of job build artifact
        """
        url = "/".join([url, 'artifact', artifact])
        logger.debug("Request artifact content from {}".format(url))
        return requests.get(url).text

    @staticmethod
    def get_downstream_builds_from_html(url):
        """Return list of downstream jobs builds from specified job
        """
        url = "/".join([url, 'downstreambuildview/'])
        logger.debug("Request downstream builds data from {}".format(url))
        response = requests.get(url).text
        jobs = []
        raw_downstream_builds = re.findall(
            '.*downstream-buildview.*href="(/job/\S+/[0-9]+/).*', response)
        for raw_build in raw_downstream_builds:
            sub_job_name = raw_build.split('/')[2]
            sub_job_build = raw_build.split('/')[3]
            build = Build(name=sub_job_name, number=sub_job_build)
            jobs.append(
                {
                    'name': build.name,
                    'number': build.number,
                    'result': build.build_data['result']
                }
            )
        return jobs

    @staticmethod
    def get_jobs_for_view(view):
        """Return list of jobs from specified view
        """
        view_url = "/".join([JENKINS["url"], 'view', view, 'api/json'])
        logger.debug("Request view data from {}".format(view_url))
        view_data = requests.get(view_url).json()
        jobs = [job["name"] for job in view_data["jobs"]]
        return jobs

    @staticmethod
    def get_test_data(url, result_path=None):
        """ Get build test data from Jenkins from testReport api

        :param: None
        :return: test_data: dict - test result info or None otherwise
        """
        if result_path:
            test_url = "/".join(
                [url.rstrip("/"), 'testReport'] + result_path + ['api/json'])
        else:
            test_url = "/".join([url.rstrip("/"), 'testReport', 'api/json'])

        logger.debug("Request test data from {}".format(test_url))
        return requests.get(test_url).json()

    def get_groups(self, distros):
        """ Get build test groups from Jenkins

        :param: distros - list of os which shall be included
        :return: groups: dict - group info or None otherwise
        """
        res = {}

        def _get_suffix(distros, job_name):
            for distro in distros:
                if distro in job_name:
                    sep = '.' + distro + '.'
                    job_suffix = job_name.split(sep)[-1]
                    break
            else:
                job_suffix = job_name.split('.')[-1]
            return job_suffix

        if not self.build_data['subBuilds']:
            test_group = self.get_environment_variables.get('TEST_GROUP')
            job_suffix = _get_suffix(distros, self.name)
            res[job_suffix] = test_group
        else:
            for b in self.build_data['subBuilds']:
                if b['result'] is None:
                    logger.debug("Skipping '{0}' job (build #{1}) because it's still "
                                 "running...".format(b['jobName'], b['buildNumber'], ))
                    continue
                # Get the test group from the Environment variables
                sub_build = Build(b['jobName'], b['buildNumber'])
                test_group = sub_build.get_environment_variables()['envMap'].\
                    get('TEST_GROUP')
                # Get the job suffix
                job_suffix = _get_suffix(distros, b['jobName'])
                res[job_suffix] = test_group
        return res

    def get_results(self):
        """ Get build test data from Jenkins from nosetests.xml

        :param: None
        :return: test_data: dict - build info or None otherwise
        """

        test_data = None
        logger.info('Request results from {} {}'.format(self.name,
                                                          self.number))
        if not self.build_data:
            logger.error('Getting subbuilds info is failed. '
                         'Job={} Build={}'.format(self.name, self.number))
            return test_data
        try:
            artifact_paths = [v for i in self.build_data.get('artifacts')
                              for k, v in i.items() if k == 'relativePath' and
                              v == JENKINS.get('xml_testresult_file_name')][0]
            artifact_url = "/".join([JENKINS['url'], 'job', self.name,
                                     str(self.number)])
            xunit_data = self.get_build_artifact(artifact_url, artifact_paths)
            test_data = xmltodict.parse(xunit_data, xml_attribs=True)
            test_data.update({'build_number': self.number,
                              'job_name': self.name,
                              'job_url': self.build_data.get('url'),
                              'job_description':
                                  self.build_data.get('description'),
                              'job_status': self.build_data.get('result')})
        except:
            test_data = None
        return test_data

    def test_data(self, result_path=None):
        try:
            data = self.get_test_data(self.url, result_path)
        except Exception as e:
            logger.warning("No test data for {0}: {1}".format(
                self.url,
                e,
            ))
            # If we failed to get any tests for the build, return
            # meta test case 'jenkins' with status 'failed'.
            data = {
                "suites": [
                    {
                        "cases": [
                            {
                                "name": "jenkins",
                                "className": "jenkins",
                                "status": "failed",
                                "duration": 0
                            }
                        ]
                    }
                ]
            }

        return data

    def get_downstream_builds(self, status=None):
        if 'subBuilds' not in self.build_data.keys():
            return self.get_downstream_builds_from_html(self.build_data['url'])
        return [{'name': b['jobName'], 'number': b['buildNumber'],
                 'result': b['result']} for b in self.build_data['subBuilds']]

    def generate_test_plan_name(self):
        """ Generate name of TestPlan basing on iso image name
            taken from Jenkins job build parameters"""
        milestone, iso_number, prefix = self.get_version()
        return ' '.join(filter(lambda x: bool(x),
                               (milestone, prefix, 'iso', '#' + str(iso_number))))

    def generate_test_run_name(self):
        """ Generate name of TestRun basing on iso image name
            taken from Jenkins job build parameters"""
        milestone = self.get_version()[0]
        return ''.join(filter(lambda x: bool(x),
                              ('[', milestone, ']', ' Swarm')))

    def get_job_parameter(self, parameter):
        parameters = [a['parameters'] for a in self.build_data['actions']
                      if 'parameters' in a.keys()][0]
        target_params = [p['value'] for p in parameters
                         if p['name'].lower() == str(parameter).lower()]
        if len(target_params) > 0:
            return target_params[0]

    def get_version(self):
        version = self.get_version_from_parameters()
        if not version:
            version = self.get_version_from_artifacts()
        if not version:
            version = self.get_version_from_upstream_job()
        if not version:
            raise Exception('Failed to get iso version from Jenkins jobs '
                            'parameters/artifacts!')
        return version

    @staticmethod
    def get_version_from_iso_name(iso_link):
        match = re.search(r'.*\bfuel-(?P<prefix1>[a-zA-Z]*)-?(?P<version>\d+'
                          r'(?P<version2>\.\d+)+)-(?P<prefix2>[a-zA-Z]*)-?'
                          r'(?P<buildnum>\d+)-.*', iso_link)
        if match:
            return (match.group('version'),
                    int(match.group('buildnum')),
                    match.group('prefix1') or match.group('prefix2'))

    def get_version_from_parameters(self):
        custom_version = self.get_job_parameter('CUSTOM_VERSION')
        if custom_version:
            swarm_timestamp = self.build_data['timestamp'] // 1000 \
                if 'timestamp' in self.build_data else None
            return (TestRailSettings.milestone,
                    time.strftime("%D %H:%M", time.localtime(swarm_timestamp)),
                    custom_version)
        iso_link = self.get_job_parameter('magnet_link')
        if iso_link:
            return self.get_version_from_iso_name(iso_link)

    def get_version_from_upstream_job(self):
        upstream_job = self.get_job_parameter('UPSTREAM_JOB_URL')
        if not upstream_job:
            return
        causes = [a['causes'] for a in self.build_data['actions']
                  if 'causes' in a.keys()][0]
        if len(causes) > 0:
            upstream_job_name = causes[0]['upstreamProject']
            upstream_build_number = causes[0]['upstreamBuild']
            upstream_build = Build(upstream_job_name, upstream_build_number)
            return (upstream_build.get_version_from_artifacts() or
                    upstream_build.get_version_from_parameters())

    def get_version_from_artifacts(self):
        if not any([artifact for artifact in self.build_data['artifacts']
                    if artifact['fileName'] == JENKINS['magnet_link_artifact']]):
            return
        iso_link = (self.get_build_artifact(
            url=self.build_data['url'],
            artifact=JENKINS['magnet_link_artifact']))
        if iso_link:
            return self.get_version_from_iso_name(iso_link)

    def get_test_build(self, check_rebuild=False):
        """Get test data from Jenkins job build
        :param build_name: string
        :param build_number: string
        :param check_rebuild: bool, if True then look for newer job rebuild(s)
        :return: dict
        """
        if self.test_data()['suites'][0]['cases'].pop()['name'] == 'jenkins':
            if not check_rebuild:
                return self
            iso_magnet = self.get_job_parameter(self.build_data, 'MAGNET_LINK')
            if not iso_magnet:
                return self
            latest_build_number = self.build_data('latest').number
            for n in range(self.number, latest_build_number):
                test_rebuild = Build(self.name, n + 1)
                if test_rebuild.get_job_parameter('MAGNET_LINK') \
                        == iso_magnet:
                    logger.debug("Found test job rebuild: "
                                 "{0}".format(test_rebuild.url))
                    return test_rebuild
        return self

    def get_sub_builds(self):
        """ Gather all sub build info into subbuild list

        :param build_number: int - Jenkins build number
        :param job_name: str - Jenkins job_name
        :param jenkins_url: str - Jenkins http url
        :return: sub_builds: list of dicts or None otherwise
                 {build_info, test_data, failure_reasons}
                 where:
                 build_info(sub build specific info got from Jenkins)-dict
                 test_data(test data per one sub build)-dict
                 failure_reasons(failures per one sub build)-list
        """

        parent_build_info = self.build_data
        sub_builds = None
        if parent_build_info:
            sub_builds = parent_build_info.get('subBuilds')
        if sub_builds:
            for i in sub_builds:
                sub_build = Build(i.get('jobName'), i.get('buildNumber'))
                if sub_build and sub_build.results:
                    i.update({'test_data': sub_build.results})
                    i.update({'description': sub_build.results.get('job_description')})
                    i.update({'failure_reasons':  sub_build.failures})
        return sub_builds

    def get_build_failure_reasons(self):
        """ Gather all failure reasons across all tests

        :param test_data: dict - test data which were extracted from Jenkins
        :return: test_data: list of dicts
                 {failure, test, build_number, job_name, url, test_url}
                 where:
                 failure(type and message were exctracted from nosetests.xml)-str
                 test(@classname was exctracted from nosetests.xml)-str
                 build_number(number which exctracted from build_info early)-int
                 job_name(Jenkins job name extracted from build_info early)-str
                 url(Jenkins job name full URL) - str
                 test_url(Jenkins test result URL) - str
                 [] otherwise
        """
        failure_reasons = []
        if not (self.results and self.results.get('testsuite')):
            return failure_reasons
        for test in self.results.get('testsuite').get('testcase'):
            failure_reason = None
            if test.get('error'):
                failure_reason = "___".join(['error',
                                             'type',
                                             test.get('error', {}).get('@type', ''),
                                             'message',
                                             test.get('error', {}).get('@message', '')])
            elif test.get('failure'):
                failure_reason = "___".join(['failure',
                                             'type',
                                             test.get('failure', {}).get('@type', ''),
                                             'message',
                                             test.get('failure', {}).get('@message', '')])
            elif test.get('skipped'):
                failure_reason = "___".join(['skipped',
                                             'type',
                                             test.get('skipped', {}).get('@type', ''),
                                             'message',
                                             test.get('skipped', {}).get('@message', '')])
            if failure_reason:
                failure_reason_cleanup = make_cleanup(failure_reason)
                failure_reasons.append({'failure': failure_reason_cleanup,
                                        'failure_origin': failure_reason,
                                        'test': test.get('@classname'),
                                        'build_number':
                                            self.results.get('build_number'),
                                        'job_name': self.results.get('job_name'),
                                        'job_url': self.results.get('job_url'),
                                        'job_status': self.results.get('job_status'),
                                        'test_fail_url':
                                            "".join([self.results.get('job_url'),
                                                     'testReport/(root)/',
                                                     test.get('@classname'),
                                                     '/', test.get('@name')])
                                        })
        return failure_reasons

    def __str__(self):
        string = "\n".join([
            "{0}: {1}".format(*item) for item in self.build_record()
        ])
        return string

    def build_record(self):
        """Return list of pairs.

        We cannot use dictionary, because columns are ordered.
        """

        data = [
            ('number', str(self.number)),
            ('name', self.name),
            ('requested_number', self.requested_number),
            ('latest_started', self.latest_started),
            ('latest_number', self.latest_number),
            ('id', self.build_data["id"]),
            ('description', self.build_data["description"]),
            ('url', self.build_data["url"]),
        ]

        test_data = self.test_data()
        for suite in test_data['suites']:
            for case in suite['cases']:
                column_id = case['className'].lower().replace("_", "-")
                data.append((column_id, case['status'].lower()))

        return data
