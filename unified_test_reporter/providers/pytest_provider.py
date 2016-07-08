# pylint: disable=no-name-in-module
# noinspection PyUnresolvedReferences
from pytest import Session
# pylint: enable=no-name-in-module
from _pytest.config import _prepareconfig
from _pytest.python import FixtureManager
from _pytest.mark import MarkMapping

from unified_test_reporter.providers.providers import TestCaseProvider


class PyTestTestCaseProvider(TestCaseProvider):

    def get_cases(self, group):
        config = _prepareconfig(args=str(""))
        session = Session(config)
        session._fixturemanager = FixtureManager(session)
        ret = [i for i
               in session.perform_collect() if
               group in list(MarkMapping(i.keywords)._mymarks)]
        return ret

    def group_in(self, group):
        config = _prepareconfig(args=str(""))
        session = Session(config)
        session._fixturemanager = FixtureManager(session)
        l = [list(MarkMapping(i.keywords)._mymarks) for i
             in session.perform_collect()]
        groups = set([item for sublist in l for item in sublist])
        return group in groups