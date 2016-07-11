import json
import subprocess
import unittest

from unified_test_reporter.providers.jenkins_client import Build
from unified_test_reporter.providers.proboscis_provider import ProbockisTestCaseProvider
from unified_test_reporter.providers.providers import DocStringProvider
from unified_test_reporter.providers.pytest_provider import PyTestTestCaseProvider
from unified_test_reporter.providers.testrail_client import TestRailProject
from unified_test_reporter.settings import TestRailSettings
from unified_test_reporter.pylib.pylib import get_yaml_to_attr
from unified_test_reporter.providers.registers import TestReporterModule
from unified_test_reporter.providers.registers import Register


class TestReporter(unittest.TestCase):

    def setUp(self):
        command_list = [
            'cd /home/krozin/@Git/MIRANTIS/unified_test_reporter',
            'CUR_DIR=\$\(pwd\)',
            'FUELQA_DIR=/home/krozin/\@Git/MIRANTIS/fuel-qa',
            'export PYTHONPATH="\${PYTHONPATH}:\$CUR_DIR:\$FUELQA_DIR"',
            'export JENKINS_URL=https://product-ci.infra.mirantis.net',
            'export TESTRAIL_URL=https://mirantis.testrail.com',
            'export TESTRAIL_PROJECT="Mirantis OpenStack"',
            'export TESTRAIL_USER=all@mirantis.com',
            'export TESTRAIL_PASSWORD=mirantis1C@@L',
            'export TESTS_RUNNER=9.0.swarm.runner',
            'export TEST_RUNNER_JOB_NAME=9.0.swarm.runner',
            'export TESTRAIL_TEST_SUITE=\'[9.0] Swarm\'',
            'export TESTRAIL_MILESTONE=9.0',
            'export LAUNCHPAD_MILESTONE=9.0',
            'export USE_UBUNTU = \'true\'']
        for i in command_list:
            subprocess.call(i, shell=True)

    def test_testrail_client(self):
        RUN_ID = 15286
        PLAN_ID = 15282

        testRailPlan = TestRailProject(url=TestRailSettings.url,
                                       user=TestRailSettings.user,
                                       password=TestRailSettings.password,
                                       project=TestRailSettings.project)
        self.assertNotEqual(testRailPlan.project, None)

        results = testRailPlan.get_results_for_run(RUN_ID)
        bugs = testRailPlan.get_bugs(RUN_ID)
        urls = testRailPlan.get_testrail_test_urls(RUN_ID, 'setup_master_multiracks_2')
        tests = testRailPlan.get_tests(run_id=RUN_ID)

        json.dump(tests, open('/home/krozin/Documents/{}_tests.json'.format(RUN_ID), 'w'))
        json.dump(results, open('/home/krozin/Documents/{}_result.json'.format(RUN_ID), 'w'))
        json.dump(bugs, open('/home/krozin/Documents/{}_bugs.json'.format(RUN_ID), 'w'))
        json.dump(urls, open('/home/krozin/Documents/{}_urls.json'.format(RUN_ID), 'w'))

        self.assertNotEqual(tests, None)
        self.assertNotEqual(results, None)
        self.assertNotEqual(bugs, None)
        self.assertNotEqual(urls, None)

    def test_jenkins_client(self):
        name = '9.0.swarm.runner'
        number = 160
        build = Build(name, number)
        self.assertNotEqual(build.build_data, None)

    @unittest.skip("skipping getversion")
    def test_getversion(self):
        magnetlink='magnet:?xt=urn:btih:23c025868f7f17ed2002b70857b0cdd726' \
                   '11114a&dn=fuel-10.0-mitaka-39-2016-07-01%5F10-00-00.is' \
                   'o&tr=http%3A%2F%2Ftracker01-bud.infra.mirantis.net%3A80' \
                   '80%2Fannounce&tr=http%3A%2F%2Ftracker01-scc.infra.miran' \
                   'tis.net%3A8080%2Fannounce&tr=http%3A%2F%2Ftracker01-msk' \
                   '.infra.mirantis.net%3A8080%2Fannounce&ws=http%3A%2F%2Fs' \
                   'rv52-bud.infra.mirantis.net%2Ffuelweb-iso%2Ffuel-10.0-m' \
                   'itaka-39-2016-07-01%5F10-00-00.iso'
        print Build.get_version_from_iso_name(magnetlink)

    def test_get_runid(self):
        name = '9.0.swarm.runner'
        number = 160
        build = Build(name, number)
        self.assertNotEqual(build.build_data, None)
        planname = build.generate_test_plan_name()
        runname = build.generate_test_run_name()

        testRailPlan = TestRailProject(url=TestRailSettings.url,
                                       user=TestRailSettings.user,
                                       password=TestRailSettings.password,
                                       project=TestRailSettings.project)
        self.assertNotEqual(testRailPlan.project, None)

        plan = testRailPlan.get_plan_by_name(planname)
        runid = testRailPlan.get_runid_by_planid(plan.get('id'), runname)
        self.assertNotEqual(plan, None)
        self.assertNotEqual(runid, None)

    def test_get_groups(self):
        name = '9.0.swarm.runner'
        number = 160

        testRailPlan = TestRailProject(
            url=TestRailSettings.url,
            user=TestRailSettings.user,
            password=TestRailSettings.password,
            project=TestRailSettings.project
        )

        distros = testRailPlan.get_distros()
        running_build = Build(name, number)
        tests_groups = running_build.get_groups(distros) if name else []

        self.assertNotEqual(tests_groups, [])

    def test_proboskis_provider(self):
        probockis_provider = ProbockisTestCaseProvider()
        groups = json.load(open('unified_test_reporter/pantry/groups.json'))
        plan = probockis_provider.get_plan(groups)
        all_plan_tests = plan.tests[:]
        self.assertNotEqual(plan.tests[:], [])

    def test_pytest_provider(self):
        pytest_provider = PyTestTestCaseProvider()
        groups = json.load(open('unified_test_reporter/pantry/groups.json'))
        for jenkins_suffix in groups:
            group = groups[jenkins_suffix]
            if pytest_provider.group_in(group):
                cases = pytest_provider.get_cases(group)
                print cases
                self.assertNotEqual(cases, None)

    def test_get_plan_proboscis(self):
        probockis_provider = ProbockisTestCaseProvider()
        groups = json.load(open('unified_test_reporter/pantry/groups.json'))
        plan = probockis_provider.get_plan(groups)
        print len(plan.tests)
        print ((plan.tests[100].entry.parent))
        print ((plan.tests[100].entry.parent.home.__name__))
        print ((plan.tests[100].entry.parent.home.__doc__))
        self.assertNotEqual(plan, None)

    def test_proboskis_getting_docstring(self):
        probockis_provider = ProbockisTestCaseProvider()
        groups = json.load(open('unified_test_reporter/pantry/groups.json'))
        plan = probockis_provider.get_plan(groups)
        docstring_provider = DocStringProvider()
        tests = []
        for jenkins_suffix in groups:
            group = groups[jenkins_suffix]
            plan.filter(group_names=[group])
            for case in plan.tests:
                case_name = probockis_provider.get_test_case_name(case)
                self.assertNotEqual(case_name, None)
                docstring = probockis_provider.get_docstring(parent_home=case.entry.parent.home,
                                                             case_state=case.state,
                                                             home=case.entry.home)
                title, steps, duration = docstring_provider.parse_docstring(docstring, case)
                self.assertNotEqual(title, None)
                self.assertNotEqual(steps, None)
                self.assertNotEqual(duration, None)
                test = {'title': title,
                        'custom_test_group':case_name,
                        'custom_test_case_description': docstring,
                        'custom_test_case_steps': steps,
                        'duration': duration}
                tests.append(test)
        print len(tests)
        self.assertNotEqual(tests, [])

    def test_proboskis_gettests_for_groups(self):
        probockis_provider = ProbockisTestCaseProvider()
        groups = json.load(open('unified_test_reporter/pantry/groups.json'))
        tests = probockis_provider.get_tests_for_groups(groups)
        print len(tests)

    def test_proboskis_gettests_by_group(self):
        probockis_provider = ProbockisTestCaseProvider()
        group = {"services_ha.ceilometer": "services_ha.ceilometer"}
        group = {"test_ibp": "test_ibp"}
        tests = probockis_provider.get_tests_for_group(group)
        print len(tests)
        self.assertNotEqual(tests, [])

    def test_pytest_getting_docstring(self):
        pass

    def test_registering_modules(self):
        class App(object):
            def __init__(self, configfile):
                self.configfile = configfile
                self.config = get_yaml_to_attr(self.configfile)
                self.register = Register(config=self.config)

                self.testcases = self.register.create_module('dummy_testcase_module')
                self.register.append(self.testcases)

                self.testresults = self.register.create_module('dummy_testresult_module')
                self.register.append(self.testresults)

        class DummyTestCases(TestReporterModule):
            def module_init(self):
                super(DummyTestCases, self).module_init()

        class DummyTestresults(TestReporterModule):
            def module_init(self):
                super(DummyTestCases, self).module_init()

if __name__ == '__main__':
    unittest.main()


