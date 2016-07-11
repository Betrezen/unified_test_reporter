#    Copyright 2013 - 2016 Mirantis, Inc.
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

from setuptools import find_packages
from setuptools import setup


setup(
    name='unified_test_reporter',
    version='1.0.0',
    description='Library for creating and publishing reports',
    author='Mirantis, Inc.',
    author_email='product@mirantis.com',
    url='http://mirantis.com',
    keywords='fuel universal unified_test_reporter',
    zip_safe=False,
    include_package_data=True,
    packages=find_packages(),
<<<<<<< HEAD
    entry_points={
        'unified_test_reporter.modules': [
            'jenkins_test_results = unified_test_reporter.providers.jenkins_client:Build',
            'proboscis_cases = unified_test_reporter.providers.proboscis:ProbockisTestCaseProvider',
            'pytest_cases = unified_test_reporter.providers.proboscis:PytestTestCaseProvider',
            'testrail_publisher = unified_test_reporter.providers.testrail_client:TestRailProject',
            'launchpad_bug = unified_test_reporter.providers.launchpad_client:LaunchpadBug',
        ]
    },
=======
>>>>>>> 066d4ecbbd33643da64c901fb3928f1b32af483d
)
