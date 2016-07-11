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

from launchpadlib.launchpad import Launchpad

from unified_test_reporter.providers.providers import BugProvider
from unified_test_reporter.settings import LaunchpadSettings


class LaunchpadBug(BugProvider):
    """LaunchpadBug."""  # TODO documentation

    def __init__(self, bug_id):
        self.launchpad = Launchpad.login_anonymously('just testing',
                                                     'production',
                                                     '.cache')
        self.bug = self.launchpad.bugs[int(bug_id)]

    def module_init(self):
        super(LaunchpadBug, self).module_init()

    @property
    def targets(self):
        return [
            {
                'project': task.bug_target_name.split('/')[0],
                'milestone': str(task.milestone).split('/')[-1],
                'status': task.status,
                'importance': task.importance,
                'title': task.title,
            } for task in self.bug_tasks]

    @property
    def title(self):
        """ Get bug title

        :param none
        :return: bug title - str
        """
        return self.targets[0].get('title', '')

    def get_duplicate_of(self):
        bug = self.bug
        duplicates = []
        while bug.duplicate_of and bug.id not in duplicates:
            duplicates.append(bug.id)
            bug = self.launchpad.load(str(bug.duplicate_of))
        return LaunchpadBug(bug.id)

    def inspect_bug(self):
        # Return target which matches defined in settings project/milestone and
        # has 'open' status. If there are no such targets, then just return first
        # one available target.
        for target in self.targets:
            if target['project'] == LaunchpadSettings.project and \
                            LaunchpadSettings.milestone in target['milestone'] and \
                            target['status'] not in LaunchpadSettings.closed_statuses:
                return target
        return self.targets[0]

    def __getattr__(self, item):
        return self.bug.__getattr__(item)
