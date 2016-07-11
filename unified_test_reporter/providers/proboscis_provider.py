from proboscis import TestPlan
from proboscis.decorators import DEFAULT_REGISTRY
from system_test import define_custom_groups
from system_test import discover_import_tests
from system_test import get_basepath
from system_test import register_system_test_cases
from system_test import tests_directory
from system_test.tests.base import ActionTest

from unified_test_reporter.providers.providers import TestCaseProvider
<<<<<<< HEAD
from unified_test_reporter.providers.providers import DocStringProvider
=======
>>>>>>> 066d4ecbbd33643da64c901fb3928f1b32af483d
from unified_test_reporter.settings import GROUP_FIELD
from unified_test_reporter.settings import logger


class ProbockisTestCaseProvider(TestCaseProvider):

    def get_docstring(self, parent_home, case_state, home):
        if issubclass(parent_home, ActionTest):
            docstring = parent_home.__doc__.split('\n')
            case_state.instance._load_config()
            configuration = case_state.instance.config_name
            docstring[0] = '{0} on {1}'.format(docstring[0], configuration)
            docstring = '\n'.join(docstring)
        else:
            docstring = home.func_doc or ''
        return docstring

    def get_plan(self, groups):
        discover_import_tests(get_basepath(), tests_directory)
        define_custom_groups()
        for one in groups:
            register_system_test_cases(one)
        return TestPlan.create_from_registry(DEFAULT_REGISTRY)

<<<<<<< HEAD
    def get_plan_by_group(self, group):
        discover_import_tests(get_basepath(), tests_directory)
        define_custom_groups()
        register_system_test_cases(group)
        return TestPlan.create_from_registry(DEFAULT_REGISTRY)

    def get_tests_for_groups(self, groups):
        tests = []
        docstring_provider = DocStringProvider()
        plan = self.get_plan(groups)
        #plan.filter(group_names=groups.values())
        for group in groups.keys():
            #plan.filter(group_names=[group])
            print "LEN=%s"%len(plan.tests)
            for case in plan.tests:
                case_name = self.get_test_case_name(case)
                docstring = self.get_docstring(parent_home=case.entry.parent.home,
                                               case_state=case.state,
                                               home=case.entry.home)
                title, steps, duration = docstring_provider.parse_docstring(docstring, case)
                test = {'title': title,
                        'custom_test_group':case_name,
                        'custom_test_case_description': docstring,
                        'custom_test_case_steps': steps,
                        'duration': duration}
                tests.append(test)
        return tests

    def get_tests_for_group(self, group):
        tests = []
        docstring_provider = DocStringProvider()
        plan = self.get_plan_by_group(group)
        group_val = group.values()[0]
        plan.filter(group_names=[group_val])
        for case in plan.tests:
            case_name = self.get_test_case_name(case)
            docstring = self.get_docstring(parent_home=case.entry.parent.home,
                                           case_state=case.state,
                                           home=case.entry.home)
            title, steps, duration = docstring_provider.parse_docstring(docstring, case)
            test = {'title': title,
                    'custom_test_group':case_name,
                    'custom_test_case_description': docstring,
                    'custom_test_case_steps': steps,
                    'duration': duration}
            tests.append(test)
        return tests

=======
>>>>>>> 066d4ecbbd33643da64c901fb3928f1b32af483d
    def get_test_case_name(self, case):
        """Returns test case name
        """
        if case.entry.parent:
            parent_home = case.entry.parent.home
            return parent_home.__name__ if issubclass(parent_home, ActionTest) \
                else case.entry.home.func_name
        return None

    def is_case_processable(self, case, tests):
        if not case.entry.info.enabled or not hasattr(case.entry, 'parent'):
            return False

        parent_home = case.entry.parent.home
        if issubclass(parent_home, ActionTest) and \
                any([test[GROUP_FIELD] == parent_home.__name__ for test in tests]):
            return False

        # Skip @before_class methods without doc strings:
        # they are just pre-checks, not separate tests cases
        if case.entry.info.before_class:
            if case.entry.home.func_doc is None:
                logger.debug('Skipping method "{0}", because it is not a '
                             'test case'.format(case.entry.home.func_name))
                return False
        return True