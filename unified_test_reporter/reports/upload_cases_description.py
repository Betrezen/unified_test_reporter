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

from logging import DEBUG
from optparse import OptionParser

from unified_test_reporter.providers.jenkins_client import Build
from unified_test_reporter.providers.proboscis_provider import ProbockisTestCaseProvider
from unified_test_reporter.providers.providers import DocStringProvider
from unified_test_reporter.providers.providers import GROUP_FIELD
from unified_test_reporter.providers.providers import TestCaseProvider
from unified_test_reporter.providers.pytest_provider import PyTestTestCaseProvider
from unified_test_reporter.providers.testrail_client import TestRailProject
from unified_test_reporter.pylib.pylib import duration_to_testrail_estimate
from unified_test_reporter.settings import GROUPS_TO_EXPAND
from unified_test_reporter.settings import TestRailSettings
from unified_test_reporter.settings import logger


def get_tests_descriptions(milestone_id,
                           tests_include, tests_exclude,
                           groups,
                           default_test_priority):
    probockis_provider = ProbockisTestCaseProvider()
    pytest_provider = PyTestTestCaseProvider()
    docstring_provider = DocStringProvider()
    plan = probockis_provider.get_plan(groups)
    all_plan_tests = plan.tests[:]

    tests = []

    for jenkins_suffix in groups:
        group = groups[jenkins_suffix]
        if pytest_provider.group_in(group):
            for case in pytest_provider.get_cases(group):
                docstring = case.obj.__doc__ or ''

                title, steps, duration = docstring_provider.parse_docstring(docstring, case)

                test_group = case.obj.__name__

                test_case = {
                    "title": title,
                    "type_id": 1,
                    "milestone_id": milestone_id,
                    "priority_id": default_test_priority,
                    "estimate": duration,
                    "refs": "",
                    "custom_test_group": test_group,
                    "custom_test_case_description": docstring or " ",
                    "custom_test_case_steps": steps
                }
                tests.append(test_case)
        else:
            plan.filter(group_names=[group])
            for case in plan.tests:
                if not probockis_provider.is_case_processable(case=case, tests=tests):
                    continue

                case_name = test_group = probockis_provider.get_test_case_name(case)

                if not TestCaseProvider.is_included(case_name, tests_include) or \
                        TestCaseProvider.is_excluded(case_name, tests_exclude):
                    continue

                docstring = probockis_provider.get_docstring(parent_home=case.entry.parent.home,
                                           case_state=case.state,
                                           home=case.entry.home)

                title, steps, duration = docstring_provider.parse_docstring(docstring, case)

                if case.entry.home.func_name in GROUPS_TO_EXPAND:
                    """Expand specified test names with the group names that are
                       used in jenkins jobs where this test is started.
                    """
                    title = ' - '.join([title, jenkins_suffix])
                    test_group = '_'.join([case.entry.home.func_name,
                                           jenkins_suffix])

                test_case = {
                    "title": title,
                    "type_id": 1,
                    "milestone_id": milestone_id,
                    "priority_id": default_test_priority,
                    "estimate": duration,
                    "refs": "",
                    "custom_test_group": test_group,
                    "custom_test_case_description": docstring or " ",
                    "custom_test_case_steps": steps
                }

                if not any([x[GROUP_FIELD] == test_group for x in tests]):
                    tests.append(test_case)
                else:
                    logger.warning("Testcase '{0}' run in multiple "
                                   "Jenkins jobs!".format(test_group))

            plan.tests = all_plan_tests[:]

    return tests


def upload_tests_descriptions(testrail_project, section_id,
                              tests, check_all_sections):
    tests_suite = testrail_project.get_suite_by_name(
        TestRailSettings.tests_suite)
    check_section = None if check_all_sections else section_id
    cases = testrail_project.get_cases(suite_id=tests_suite['id'],
                                       section_id=check_section)
    existing_cases = [case[GROUP_FIELD] for case in cases]
    custom_cases_fields = _get_custom_cases_fields(
        case_fields=testrail_project.get_case_fields(),
        project_id=testrail_project.project['id'])

    for test_case in tests:
        if test_case[GROUP_FIELD] in existing_cases:
            testrail_case = testrail_project.get_case_by_group(tests_suite['id'], test_case)
            fields_to_update = _get_fields_to_update(test_case, testrail_case)

            if fields_to_update:
                logger.debug('Updating test "{0}" in TestRail project "{1}", '
                             'suite "{2}", section "{3}". Updated fields: {4}'
                             .format(
                                 test_case[GROUP_FIELD],
                                 TestRailSettings.project,
                                 TestRailSettings.tests_suite,
                                 TestRailSettings.tests_section,
                                 ', '.join(fields_to_update.keys())))
                testrail_project.update_case(case_id=testrail_case['id'],
                                             fields=fields_to_update)
            else:
                logger.debug('Skipping "{0}" test case uploading because '
                             'it is up-to-date in "{1}" suite'
                             .format(test_case[GROUP_FIELD],
                                     TestRailSettings.tests_suite))

        else:
            for case_field, default_value in custom_cases_fields.items():
                if case_field not in test_case:
                    test_case[case_field] = default_value

            logger.debug('Uploading test "{0}" to TestRail project "{1}", '
                         'suite "{2}", section "{3}"'.format(
                             test_case[GROUP_FIELD],
                             TestRailSettings.project,
                             TestRailSettings.tests_suite,
                             TestRailSettings.tests_section))
            testrail_project.add_case(section_id=section_id, case=test_case)


def _get_custom_cases_fields(case_fields, project_id):
    custom_cases_fields = {}
    for field in case_fields:
        for config in field['configs']:
            if ((project_id in
                    config['context']['project_ids'] or
                    not config['context']['project_ids']) and
                    config['options']['is_required']):
                try:
                    custom_cases_fields[field['system_name']] = \
                        int(config['options']['items'].split(',')[0])
                except:
                    logger.error("Couldn't find default value for required "
                                 "field '{0}', setting '1' (index)!".format(
                                     field['system_name']))
                    custom_cases_fields[field['system_name']] = 1
    return custom_cases_fields


def _get_fields_to_update(test_case, testrail_case):
    """Produces dictionary with fields to be updated
    """
    fields_to_update = {}
    for field in ('title', 'estimate', 'custom_test_case_description',
                  'custom_test_case_steps'):
        if test_case and testrail_case and test_case[field] and \
                test_case[field] != testrail_case[field]:
            if field == 'estimate':
                testcase_estimate_raw = int(test_case[field][:-1])
                testcase_estimate = \
                    duration_to_testrail_estimate(
                        testcase_estimate_raw)
                if testrail_case[field] == testcase_estimate:
                    continue
            elif field == 'custom_test_case_description' and \
                    test_case[field] == testrail_case[field].replace('\r', ''):
                continue
            fields_to_update[field] = test_case[field]
    return fields_to_update


def main():
    parser = OptionParser(
        description="Upload tests cases to TestRail. "
                    "See settings.py for configuration."
    )
    parser.add_option("-v", "--verbose",
                      action="store_true", dest="verbose", default=False,
                      help="Enable debug output")
    parser.add_option('-j', '--job-name', dest='job_name', default=None,
                      help='Jenkins swarm runner job name')
    parser.add_option('-N', '--build-number', dest='build_number',
                      default='latest',
                      help='Jenkins swarm runner build number')
    parser.add_option('-o', '--check_one_section', action="store_true",
                      dest='check_one_section', default=False,
                      help='Look for existing test case only in specified '
                           'section of test suite.')
    parser.add_option("-l", "--live", dest="live_upload", action="store_true",
                      help="Get tests results from running swarm")

    (options, _) = parser.parse_args()

    if options.verbose:
        logger.setLevel(DEBUG)

    if options.live_upload and options.build_number == 'latest':
        options.build_number = 'latest_started'

    project = TestRailProject(
        url=TestRailSettings.url,
        user=TestRailSettings.user,
        password=TestRailSettings.password,
        project=TestRailSettings.project
    )

    testrail_section = project.get_section_by_name(
        suite_id=project.get_suite_by_name(TestRailSettings.tests_suite)['id'],
        section_name=TestRailSettings.tests_section
    )

    testrail_milestone = project.get_milestone_by_name(
        name=TestRailSettings.milestone)

    testrail_default_test_priority = [priority['id'] for priority in
                                      project.get_priorities() if
                                      priority['is_default'] is True][0]

    distros = [config['name'].split()[0].lower()
               for config in project.get_config_by_name(
                   'Operation System')['configs']
               if config['name'] in TestRailSettings.operation_systems]

    running_build = Build(options.job_name, options.build_number)

    tests_groups = running_build.get_groups(distros)\
        if options.job_name else []

    # If Jenkins job build is specified, but it doesn't have downstream builds
    # with tests groups in jobs names, then skip tests cases uploading because
    # ALL existing tests cases will be uploaded
    if options.job_name and not tests_groups:
        return

    tests_descriptions = get_tests_descriptions(
        milestone_id=testrail_milestone['id'],
        tests_include=TestRailSettings.tests_include,
        tests_exclude=TestRailSettings.tests_exclude,
        groups=tests_groups,
        default_test_priority=testrail_default_test_priority
    )

    print tests_descriptions
    return
    upload_tests_descriptions(testrail_project=project,
                              section_id=testrail_section['id'],
                              tests=tests_descriptions,
                              check_all_sections=not options.check_one_section)

if __name__ == '__main__':
    main()
