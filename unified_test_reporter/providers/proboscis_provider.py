from proboscis import TestPlan
from proboscis.decorators import DEFAULT_REGISTRY
from system_test import define_custom_groups
from system_test import discover_import_tests
from system_test import get_basepath
from system_test import register_system_test_cases
from system_test import tests_directory
from system_test.tests.base import ActionTest

from unified_test_reporter.providers.providers import TestCaseProvider
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