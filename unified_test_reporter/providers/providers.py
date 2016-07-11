import re
import string

import pkg_resources
from cached_property import cached_property

from unified_test_reporter.settings import logger

"""
TESTS_RUNNER=10.0.swarm.runner
TESTRAIL_TEST_SUITE=[10.0] Swarm
TESTRAIL_MILESTONE=10.0
LAUNCHPAD_MILESTONE=10.0
TESTRAIL_USER=****
TESTRAIL_PASSWORD=****
TESTRAIL_PROJECT='Mirantis OpenStack'
TESTRAIL_URL=https://mirantis.testrail.com

python fuelweb_test/testrail/upload_cases_description.py -v -l -j 10.0.swarm.runner
get_test_group: https://product-ci.infra.mirantis.net/view/10.0_swarm/job/10.0.system_test.ubuntu.thread_1/76/injectedEnvVars/api/json
"""

GROUP_FIELD = 'custom_test_group'
STEP_NUM_PATTERN = re.compile(r'^(\d{1,3})[.].+')
DURATION_PATTERN = re.compile(r'Duration:?\s+(\d+(?:[sm]|\s?m))(?:in)?\b')


class TestReporterModule(object):

    def __init__(self, registrator, name, config):
        super(TestReporterModule, self).__init__()
        self.registrator = registrator
        self.name = name
        self.config = config
        self.module_init()
        self.enabled = True

    def module_init(self):
        pass

    @property
    def conf(self):
        return self.conf

    def enable(self):
        self.enabled = True

    def disable(self):
        self.enabled = False

    def __repr__(self):
        return '<{self.__class__.__name__} name=\'{self.name}\', enabled={self.enabled}>'.format(self=self)


class Registrator(list):
    modules = {}
    _loaded_modules = False

    @classmethod
    def register(cls, name):
        """ Decorator to register modules
        """
        def decorator(module_cls):
            cls.register_module(name, module_cls)
            return module_cls
        return decorator

    @classmethod
    def register_module(cls, name, module_cls):
        if issubclass(module_cls, TestReporterModule):
            cls.modules[name] = module_cls
            print ("register_module = {}".format(name))
        else:
            raise Exception('modules should be subclass of TestReporterModule')

    @classmethod
    def load_modules(cls):
        if cls._loaded_modules:
            return
        # Load modules
        for plugin in pkg_resources.iter_entry_points('unified_test_reporter.modules'):
            try:
                mcls = plugin.load()
                print ("load_modules = {}".format(plugin.name))
            except Exception as e:
                print ('Unable to load plugin "{}" - {}'.format(plugin.name, e))
                continue

            print ("pa:{}".format(mcls.__subclasses__()))
            if not issubclass(mcls, TestReporterModule):
                print ('plugin "{}" is not a subclass of TestReporterModule.'.format(plugin.name))
                continue
            cls.register_module(plugin.name, mcls)
        cls._loaded_modules = True

    def __init__(self, modules=None, config=None):
        list.__init__(self)
        self.config = config
        self.load_modules()

    def create_module(self, name):
        print self.modules
        print self.config.get(name, {})
        return self.modules.get(name)(self, name, self.config.get(name, {}))

    def get_module_by_name(self, name):
        for m in self:
            if m.name == name:
                return m

    def method_as_module(self, fn):
        module_cls = type('MethodModule', (TestReporterModule, ), {'process': staticmethod(fn)})
        return module_cls(self, fn.__name__, self.config.get('', {}))

    def on_capabilities(self, caps):
        map(lambda a: a.on_capabilities(caps), self)


class BugProvider(TestReporterModule):
    @cached_property
    def get_bugs(self):
        raise NotImplemented


class TestCaseProvider(TestReporterModule):
    @cached_property
    def get_groups(self):
        raise NotImplemented

    @cached_property
    def get_cases(self):
        raise NotImplemented

    @staticmethod
    def is_included(case_name, include):
        if include and case_name not in include:
            logger.debug("Skipping '{0}' test because it doesn't "
                         "contain '{1}' in method name".format(case_name,
                                                               include))
            return False
        else:
            return True

    @staticmethod
    def is_excluded(case_name, exclude):
        if exclude and case_name in exclude:
            logger.debug("Skipping '{0}' test because it contains"
                         " '{1}' in method name".format(case_name, exclude))
            return True
        else:
            return False


class DocStringProvider(TestReporterModule):

    def parse_docstring(self, s, case):
        split_s = s.strip().split('\n\n')
        title_r, steps_r, duration_r = self.unpack_docstring(split_s)
        title = self.parse_title(title_r, case) if title_r else ''
        steps = self.parse_steps(steps_r) if steps_r else ''
        duration = self.parse_duration(duration_r)
        return title, steps, duration

    def unpack_docstring(self, items):
        count = len(items)
        title = steps = duration = ''
        if count > 3:
            title, steps, duration, _ = self.unpack_list(*items)
        elif count == 3:
            title, steps, duration = items
        elif count == 2:
            title, steps = items
        elif count == 1:
            title = items
        return title, steps, duration

    def unpack_list(self, title, steps, duration, *other):
        return title, steps, duration, other

    def parse_title(self, s, case):
        title = ' '.join(map(string.strip, s.split('\n')))
        return title if title else case.entry.home.func_name

    def parse_steps(self, strings):
        steps = []
        index = -1
        for s_raw in strings.strip().split('\n'):
            s = s_raw.strip()
            _match = STEP_NUM_PATTERN.search(s)
            if _match:
                steps.append({'content': _match.group(), 'expected': 'pass'})
                index += 1
            else:
                if index > -1:
                    steps[index]['content'] = ' '.join([steps[index]['content'],
                                                        s])
        return steps

    def parse_duration(self, s):
        match = DURATION_PATTERN.search(s)
        return match.group(1).replace(' ', '') if match else '3m'


class TestPublisher(TestReporterModule):
    def add_descriptions(self):
        """ Publish test case decription
        example:
        {"descriptions": [{
          "test_name": "Check VirtLib",
          "test_id": "101",
          "steps":[
            {"step_id": "1",
             "content": "Step 1",
             "expected": "Expected Result 1",
             "actual": "Actual Result 1"},
            {"step_id": "2",
             "content": "Step 2",
             "expected": "Expected Result 2",
             "actual": "Actual Result 2",
             "status_id": "2"}]
         }]}
        :return: 1/0
        """
        raise NotImplemented

    def add_results(self):
        """ Publish test case results
        status_id:
        1	Passed
        2	Blocked
        3	Untested
        4	Retest
        5	Failed
        {"results": [
          {"test_name": "Check VirtLib",
           "test_id": 101,
           "status_id": 5,
           "comment": "This test failed",
           "elapsed": "15s",
           "defects": ["TR-7", "LP-1010"],
           "steps": [
            {"step_id": 1,
             "status_id": 1},
            {"step_id": 2,
             "expected": "2",
             "actual": "3",
             "status_id": 5}]
          },
          {"test_name": "Check IPMILib",
           "test_id": 102,
           "status_id": 1,
           "comment": "This test passed",
           "elapsed": "5m"
          }]}
        :return: 1/0
        """
        raise NotImplemented


class TestResultProvider(TestReporterModule):
    """TestResult."""  # TODO documentation

    def module_init(self, name, group, status, duration, url=None,
                 version=None, description=None, comments=None,
                 launchpad_bug=None, steps=None):
        self.name = name
        self.group = group
        self._status = status
        self.duration = duration
        self.url = url
        self._version = version
        self.description = description
        self.comments = comments
        self.launchpad_bug = launchpad_bug
        self.available_statuses = {
            'passed': ['passed', 'fixed'],
            'failed': ['failed', 'regression'],
            'skipped': ['skipped'],
            'blocked': ['blocked'],
            'custom_status2': ['in_progress']
        }
        self._steps = steps

    @cached_property
    def results(self):
        raise NotImplemented

    @property
    def version(self):
        # Version string length is limited by 250 symbols because field in
        # TestRail has type 'String'. This limitation can be removed by
        # changing field type to 'Text'
        return (self._version or '')[:250]

    @version.setter
    def version(self, value):
        self._version = value[:250]

    @property
    def status(self):
        for s in self.available_statuses.keys():
            if self._status in self.available_statuses[s]:
                return s
        logger.error('Unsupported result status: "{0}"!'.format(self._status))
        return self._status

    @status.setter
    def status(self, value):
        self._status = value

    @property
    def steps(self):
        return self._steps

    def __str__(self):
        result_dict = {
            'name': self.name,
            'group': self.group,
            'status': self.status,
            'duration': self.duration,
            'url': self.url,
            'version': self.version,
            'description': self.description,
            'comments': self.comments
        }
        return str(result_dict)


class NoseTestTestResultProvider(TestResultProvider):
    pass