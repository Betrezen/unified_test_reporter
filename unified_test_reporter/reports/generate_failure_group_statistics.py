#!/usr/bin/env python
#
#    Copyright 2016 Mirantis, Inc.
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


from __future__ import division

import argparse
import json
import re
import sys
from logging import CRITICAL
from logging import DEBUG

import tablib

from unified_test_reporter.providers.jenkins_client import Build
from unified_test_reporter.providers.launchpad_client import LaunchpadBug
from unified_test_reporter.providers.testrail_client import TestRailProject
from unified_test_reporter.pylib.pylib import distance
from unified_test_reporter.settings import FAILURE_GROUPING
from unified_test_reporter.settings import JENKINS
from unified_test_reporter.settings import TestRailSettings
from unified_test_reporter.settings import logger


def get_bugs(subbuilds, testraildata, testrailproject):
    """Get bugs of failed tests

    :param sub_builds: list of dict per each subbuild
    :param testraildata: list test results for testrail run
    :return: bugs: dict - bugs extracted from testrail
                          and they are belong to those failed tests
    """

    if not testraildata.get('tests'):
        return {}
    total_bugs = ({str(j.get('test')): []
                  for i in subbuilds
                  for j in i.get('failure_reasons', [])})
    tests = [(i, j.get('id')) for i in total_bugs.keys()
             for j in testraildata.get('tests')
             if i == j.get('custom_test_group')]
    bugs = [(t, iid,
             rid.get('custom_launchpad_bug'),
             rid.get('status_id'))
            for (t, iid) in tests
            for rid in testraildata.get('results')
            if iid == rid.get('test_id')]
    for i in bugs:
        if i[2] and i[2].find('bugs.launchpad.net') > 0:
            iid = int(re.search(r'.*bugs?/(\d+)/?', i[2]).group(1))
            bug = LaunchpadBug(iid)
            title = bug.title or str(iid)
            label = testrailproject.get_label(i[3],
                                              testrailproject.get_statuses())
            color = testrailproject.get_color(i[3],
                                              testrailproject.get_statuses())
            item = {'id': iid,
                    'url': i[2],
                    'title': title,
                    'label': label,
                    'color': color}
            total_bugs[i[0]].append(item)
    return total_bugs


def get_global_failure_group_list(
        sub_builds, threshold=FAILURE_GROUPING.get('threshold')):
    """ Filter out and grouping of all failure reasons across all tests

    :param sub_builds: list of dict per each subbuild
    :param threshold: float -threshold
    :return: (failure_group_dict, failure_reasons): tuple or () otherwise
              where:
              failure_group_dict(all failure groups and
              associated failed test info per each failure group) - dict
              failure_reasons(all failures across all subbuild) - list
    """
    # let's find all failures in all builds
    failure_reasons = []
    failure_group_dict = {}
    failure_group_list = []
    for build in sub_builds:
        if build.get('failure_reasons'):
            for failure in build.get('failure_reasons'):
                failure_reasons.append(failure)
                failure_group_list.append(failure.get('failure'))
    # let's truncate list
    failure_group_list = list(set(failure_group_list))
    # let's update failure_group_dict
    for failure in failure_reasons:
        if failure.get('failure') in failure_group_list:
            key = failure.get('failure')
            if not failure_group_dict.get(key):
                failure_group_dict[key] = []
            failure_group_dict[key].append(failure)
    # let's find Levenshtein distance and update failure_group_dict
    for num1, key1 in enumerate(failure_group_dict.keys()):
        for key2 in failure_group_dict.keys()[num1 + 1:]:
            # let's skip grouping if len are different more 10%
            if key1 == key2 or abs(float(len(key1) / len(key2))) >\
                    FAILURE_GROUPING.get('max_len_diff'):
                continue
            # let's find other failures which can be grouped
            # if normalized Levenshtein distance less threshold
            llen = distance(key1, key2)
            cal_threshold = float(llen) / max(len(key1), len(key2))
            if cal_threshold < threshold:
                # seems we shall combine those groups to one
                failure_group_dict[key1].extend(failure_group_dict[key2])
                logger.info("Those groups are going to be combined"
                            " due to Levenshtein distance\n"
                            " {}\n{}".format(key1, key2))
                del failure_group_dict[key2]
    return failure_group_dict, failure_reasons


def update_subbuilds_failuregroup(sub_builds, failure_group_dict,
                                  testrail_testdata, testrail_project, bugs):
    """ update subbuilds by TestRail and Launchpad info

    :param sub_builds: dict of subbuilds
    :param failure_group_dict: dict of failures
    :param testrail_testdata: dict - data extracted from TestRail
    :param bugs: dict - data extracted from launchpad
    :return: None
    """

    failure_reasons_builds = [i for j in sub_builds
                              for i in j.get('failure_reasons', {})]
    if failure_reasons_builds:
        for fail in failure_reasons_builds:
            fail.update(
                testrail_project.get_testrail_test_urls(
                    testrail_testdata.get('run').get('id'),
                    fail.get('test')))
            fail.update({'bugs': bugs.get(fail.get('test'))})
        for fgroup, flist in failure_group_dict.items():
            for fail in failure_reasons_builds:
                for ffail in flist:
                    if not fail.get('failure_group')\
                       and fail.get('failure') == ffail.get('failure'):
                        fail.update({'failure_group': fgroup})
                    if fail.get('test') == ffail.get('test'):
                        ffail.update({'testresult_status':
                                      fail.get('testresult_status'),
                                      'testresult_status_color':
                                      fail.get('testresult_status_color'),
                                      'testcase_url':
                                      fail.get('testcase_url'),
                                      'testresult_url':
                                      fail.get('testresult_url'),
                                      'bugs': fail.get('bugs')})


def get_statistics(failure_group_dict, format_out=None):
    """ Generate statistics for all failure reasons across all tests

    Note: non hml format is going to be flat
    :param failure_group_dict: dict of failures
    :param testrail_tests: list of test cases extracted from TestRail
    :param format_output: html, json, xls, xlsx, csv, yam
    :return:    statistics
    """

    if format_out != 'html':
        return failure_group_dict
    html_statistics = {}
    failure_type_count = 0
    failure_group_count = 0
    ctests = list()
    cbugs = list()
    for failure, tests in failure_group_dict.items():
        # let's through list of tests
        ftype = failure.split('___message___')[0]
        skipped = (ftype.find('skipped___type___') == 0)
        if not skipped:
            if not html_statistics.get(ftype):
                html_statistics[ftype] = {}
                failure_type_count += 1
            if not html_statistics[ftype].get(failure):
                html_statistics[ftype][failure] = []
                failure_group_count += 1
            for test in tests:
                html_statistics[ftype][failure].append(test)
                ctests.append(test.get('test'))
                for bug in test.get('bugs', {}):
                    cbugs.append(bug.get('id'))
    return {'html_statistics': html_statistics,
            'failure_type_count': failure_type_count,
            'failure_group_count': failure_group_count,
            'test_count': len(set(ctests)),
            'bug_count': len(set(cbugs))}


def dump_statistics(statistics, build_number, job_name,
                    format_output=None, file_output=None):
    """ Save statistics info to file according to requested format
    Note: Please, follow tablib python lib supported formats
    http://docs.python-tablib.org/en/latest/

    non hml format is going to be flat
    html format shall use rowspan for tests under one failure group

    :param statistics: list
    :param format_output: html, json, xls, xlsx, csv, yam
    :param file_output: output file path
    :return: None
    """

    filename = None
    html_statistics = statistics.get('html_statistics')
    data = tablib.Dataset()
    html_top = "<html><body>"
    html_total_count = "<table border=1><tr>" \
                       "<th>Build</th>" \
                       "<th>Job</th>" \
                       "<th>FailureTypeCount</th>" \
                       "<th>FailureGroupCount</th>" \
                       "<th>TestCount</th>" \
                       "<th>BugCount</th></tr>"\
                       "<tr><td><font color='#ff0000'>{}</font>" \
                       "</td><td>{}</td>" \
                       "<td>{}</td>" \
                       "<td><font color='#00ff00'>{}</font></td>" \
                       "<td>{}</td>" \
                       "<td><font color='#0000ff'>{}</font></td>" \
                       "</tr></table>".\
        format(build_number,
               job_name,
               statistics.get('failure_type_count'),
               statistics.get('failure_group_count'),
               statistics.get('test_count'),
               statistics.get('bug_count'))

    html_failurestat_header = "<table border=1><tr><th>FailureType</th>" \
                              "<th>FailureGroup</th>" \
                              "<th>Test</th><th>Bug</th></tr>"
    html_buttom = "</table></body></html>"
    html = ""
    if format_output and file_output:
        filename = ".".join([file_output, format_output])
    if format_output != 'html':
        data.json = json.dumps(html_statistics)
    else:
        html_body = ""
        for failure_type in html_statistics.keys():
            rowspan_failure_type = len([j for i in html_statistics.
                                        get(failure_type).keys()
                                        for j in html_statistics.
                                        get(failure_type).get(i)])
            failure_groups = sorted(html_statistics.get(failure_type).keys())
            rowspan_failure_group = len([j for j in html_statistics.
                                         get(failure_type).
                                         get(failure_groups[0])])
            tests = html_statistics.get(failure_type).get(failure_groups[0])
            failure_message = ": ".join(failure_groups[0].
                                        split('___type___')[1].
                                        split('___message___'))
            failure_message = re.sub('\t', '&nbsp;&nbsp;&nbsp;&nbsp;',
                                     failure_message)
            failure_message = '<br>'.join(failure_message.splitlines())

            html_bugs = "<br>". \
                join(['<a href={}>#{}</a>: {}'.
                     format(bug.get('url'),
                            bug.get('id'),
                            bug.get('title'))
                      for bug in tests[0].get('bugs')])
            html_tr = '<tr>' \
                      '<td rowspan="{}">count groups:{} / ' \
                      'count tests:{}<br>{}</td>' \
                      '<td rowspan="{}">count tests: {}<br>{}</td>' \
                      '<td><font color={}>{}</font>' \
                      '<br><a href={}>{}</a>' \
                      '<br><a href={}>[job]</a></td>' \
                      '<td>{}</td>'\
                      '</tr>'.format(rowspan_failure_type,
                                     len(failure_groups),
                                     rowspan_failure_type,
                                     failure_type,
                                     rowspan_failure_group,
                                     rowspan_failure_group,
                                     failure_message,
                                     tests[0].get('testresult_status_color'),
                                     tests[0].get('testresult_status'),
                                     tests[0].get('testresult_url'),
                                     tests[0].get('test'),
                                     tests[0].get('test_fail_url'),
                                     html_bugs)
            html_body += html_tr
            if len(tests) > 1:
                for i in tests[1:]:
                    html_bugs = "<br>".\
                        join(['<a href={}>#{}</a>: {}'.
                             format(bug.get('url'),
                                    bug.get('id'),
                                    bug.get('title'))
                             for bug in i.get('bugs')])
                    html_tr = "".join(["<tr>",
                                       "<td><font color={}>{}</font>"
                                       "<br><a href={}>{}</a>"
                                       "<br><a href={}>[job]</a></td>\
                                       <td>{}</td>".
                                       format(i.get('testresult_status_color'),
                                              i.get('testresult_status'),
                                              i.get('testresult_url'),
                                              i.get('test'),
                                              i.get('test_fail_url'),
                                              html_bugs),
                                       "</tr>"])
                    html_body += html_tr
            for fgroup in failure_groups[1:]:
                tstat = html_statistics.get(failure_type).get(fgroup)
                rowspan_fg = len(tstat)
                failure_message = ": ".join(fgroup.
                                            split('___type___')[1].
                                            split('___message___'))
                failure_message = re.sub('\t', '&nbsp;&nbsp;&nbsp;&nbsp;',
                                         failure_message)
                failure_message = '<br>'.join(failure_message.splitlines())
                html_bugs = "<br>". \
                    join(['<a href={}>#{}</a>: {}'.
                         format(bug.get('url'),
                                bug.get('id'),
                                bug.get('title'))
                          for bug in tstat[0].get('bugs')])
                html_tr = '<tr>' \
                          '<td rowspan="{}">{}<br>{}</td>' \
                          '<td><font color={}>{}</font>' \
                          '<br><a href={}>{}</a>' \
                          '<br><a href={}>[job]</a></td>' \
                          '<td>{}</td>' \
                          '</tr>'.format(rowspan_fg, rowspan_fg,
                                         failure_message,
                                         tstat[0].
                                         get('testresult_status_color'),
                                         tstat[0].get('testresult_status'),
                                         tstat[0].get('testresult_url'),
                                         tstat[0].get('test'),
                                         tstat[0].get('test_fail_url'),
                                         html_bugs)
                html_body += html_tr
                if len(tstat) > 1:
                    for i in tstat[1:]:
                        html_bugs = "<br>". \
                            join(['<a href={}>#{}</a>: {}'.
                                 format(bug.get('url'),
                                        bug.get('id'),
                                        bug.get('title'))
                                  for bug in i.get('bugs')])
                        color = i.get('testresult_status_color')
                        html_tr = "".join(["<tr>",
                                           "<td><font color={}>{}</font>"
                                           "<br><a href={}>{}</a>"
                                           "<br><a href={}>[job]</a></td>\
                                           <td>{}</td>".
                                          format(color,
                                                 i.get('testresult_status'),
                                                 i.get('testresult_url'),
                                                 i.get('test'),
                                                 i.get('test_fail_url'),
                                                 html_bugs),
                                           "</tr>"])
                        html_body += html_tr
        html += html_top
        html += html_total_count
        html += html_failurestat_header
        html += html_body
        html += html_buttom
    if filename:
        with open(filename, 'w') as fileoutput:
            if format_output not in ['html']:
                mdata = getattr(data, format_output)
                fileoutput.write(mdata)
            else:
                fileoutput.write(html)


def publish_statistics(stat, build_number, job_name):
    """ Publish statistics info to TestRail
    Note: Please, follow tablib python lib supported formats

    :param statistics: list.
        Each item contains test specific info and failure reason group
    :return: True/False
    """

    dump_statistics(stat, build_number, job_name,
                    format_output='html',
                    file_output='/tmp/failure_groups_statistics')
    # We've got file and it shall be uploaded to TestRail to custom field
    # but TestRail shall be extended at first. Waiting...
    return True


def main():
    """
    :param argv: command line arguments
    :return: None
    """

    parser = argparse.ArgumentParser(description='Get downstream build info'
                                     ' for Jenkins swarm.runner build.'
                                     ' Generate matrix statisctics:'
                                     ' (failure group -> builds & tests).'
                                     ' Publish matrix to Testrail'
                                     ' if necessary.')
    parser.add_argument('-n', '--build-number', type=int, required=False,
                        dest='build_number', help='Jenkins job build number')
    parser.add_argument('-j', '--job-name', type=str,
                        dest='job_name', default=JENKINS.get('test_runner'),
                        help='Name of Jenkins job which runs tests (runner)')
    parser.add_argument('-f', '--format', type=str, dest='formatfile',
                        default='html',
                        help='format statistics: html,json,table')
    parser.add_argument('-o', '--out', type=str, dest="fileoutput",
                        default='failure_groups_statistics',
                        help='Save statistics to file')
    parser.add_argument('-t', '--track', action="store_true",
                        help='Publish statistics to TestPlan description')
    parser.add_argument('-q', '--quiet', action="store_true",
                        help='Be quiet (disable logging except critical) '
                             'Overrides "--verbose" option.')
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Enable debug logging.")
    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(DEBUG)
    if args.quiet:
        logger.setLevel(CRITICAL)
    if args.formatfile and\
       args.formatfile not in ['json', 'html', 'xls', 'xlsx', 'yaml', 'csv']:
        logger.info('Not supported format output. Exit')
        return 2

    runner_build = Build(args.job_name, args.build_number)
    testrail_project = TestRailProject(url=TestRailSettings.url,
                    user=TestRailSettings.user,
                    password=TestRailSettings.password,
                    project=TestRailSettings.project)
    if not runner_build or not testrail_project:
        logger.error('Necessary build or testrail object were not created.'
                     'Exit')
        return 3

    if not runner_build or not testrail_project:
        logger.error('Necessary build or testrail object were not created.'
                     'Exit')
        return 3
    if not args.build_number:
        logger.info('Latest build number is {}. Job is {}'.
                    format(runner_build.number, args.job_name))
        args.build_number = runner_build.number

    logger.info('Getting subbuilds for {} {}'.format(args.job_name,
                                                     args.build_number))
    subbuilds = runner_build.get_sub_builds()
    json.dump(subbuilds, open('/home/krozin/Documents/subbuilds.json', 'w'))
    if not subbuilds:
        logger.error('Necessary subbuilds info are absent. Exit')
        return 4
    logger.info('{} Subbuilds have been found'.format(len(subbuilds)))

    logger.info('Calculating failure groups')
    failure_gd = get_global_failure_group_list(subbuilds)[0]
    json.dump(failure_gd, open('/home/krozin/Documents/failure_gd.json', 'w'))
    if not failure_gd:
        logger.error('Necessary failure grpoup info are absent. Exit')
        return 5
    logger.info('{} Failure groups have been found'.format(len(failure_gd)))

    logger.info('Getting TestRail data. {} {}'.format(args.job_name, args.build_number))
    testrail_testdata = testrail_project.get_testrail_data_by_jenkinsjob(
        args.job_name, args.build_number)
    json.dump(testrail_testdata, open('/home/krozin/Documents/testrail_testdata.json', 'w'))
    if not testrail_testdata:
        logger.error('Necessary testrail info are absent. Exit')
        return 6
    logger.info('TestRail data have been downloaded')

    logger.info('Getting TestRail bugs')
    testrail_bugs = get_bugs(subbuilds, testrail_testdata, testrail_project)
    json.dump(testrail_bugs, open('/home/krozin/Documents/testrail_bugs.json', 'w'))
    if not testrail_bugs:
        logger.error('Necessary testrail bugs info are absent. Exit')
        return 7
    logger.info('TestRail bugs have been got')

    logger.info('Update subbuilds data')
    update_subbuilds_failuregroup(subbuilds, failure_gd,
                                  testrail_testdata,
                                  testrail_project,
                                  testrail_bugs)
    logger.info('Subbuilds data have been updated')

    logger.info('Generating statistics across all failure groups')
    statistics = get_statistics(failure_gd, format_out=args.formatfile)
    json.dump(statistics, open('/home/krozin/Documents/statistics.json', 'w'))
    if not statistics:
        logger.error('Necessary statistics info are absent. Exit')
        return 8
    logger.info('Statistics have been generated')

    if args.fileoutput and args.formatfile:
        logger.info('Save statistics')
        dump_statistics(statistics, args.build_number, args.job_name,
                        args.formatfile, args.fileoutput)
        logger.info('Statistics have been saved')
    if args.track:
        logger.info('Publish statistics to TestRail')
        if publish_statistics(statistics, args.build_number, args.job_name):
            logger.info('Statistics have been published')
        else:
            logger.info('Statistics have not been published'
                        'due to internal issue')

if __name__ == '__main__':
    sys.exit(main())
