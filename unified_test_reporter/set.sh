#!/bin/bash

VENV_DIR=/tmp/venv
CODE_DIR=$(pwd)/../
export PYTHONPATH="$CODE_DIR:$PYTHONPATH"

virtualenv $VENV_DIR
echo
pushd . > /dev/null
cd $VENV_DIR > /dev/null
source bin/activate

pwd

CUR_DIR=$(pwd)
FUELQA_DIR=/home/krozin/@Git/MIRANTIS/fuel-qa
export PYTHONPATH="${PYTHONPATH}:$CUR_DIR:$FUELQA_DIR"
export JENKINS_URL=https://product-ci.infra.mirantis.net
export TESTRAIL_URL=https://mirantis.testrail.com
export TESTRAIL_PROJECT="Mirantis OpenStack"
export TESTRAIL_USER=all@mirantis.com
export TESTRAIL_PASSWORD=mirantis1C@@L
export TESTS_RUNNER=9.0.swarm.runner
export TEST_RUNNER_JOB_NAME=9.0.swarm.runner
export TESTRAIL_TEST_SUITE='[9.0] Swarm'
export TESTRAIL_MILESTONE=9.0
export LAUNCHPAD_MILESTONE=9.0
export USE_UBUNTU='true'

ln -s $CODE_DIR/unified_test_reporter reporter
pip install -r reporter/requirements.txt > /dev/null
python reporter/../setup.py develop

# -------------- EXAMPLES -----------------
#pass
#python unified_test_reporter/reports/generate_failure_group_statistics.py -o /tmp/report
#python unified_test_reporter/reports/generate_statistics.py --verbose --handle-blocked --out-file bugs_link_stat --job-name 9.0.swarm.runner --html
#python unified_test_reporter/reports/report.py -v -j 9.0.test_all -N 500
<<<<<<< HEAD
#python unified_test_reporter/reports/upload_cases_description.py -v -l -j 9.0.swarm.runner -N 160
#python unified_test_reporter/tests/clients_test.py -v TestReporter.test_proboskis_getting_docstring
=======

#not tested yet
#python unified_test_reporter/reports/upload_cases_description.py -v -l -j 9.0.swarm.runner -N 160
>>>>>>> 066d4ecbbd33643da64c901fb3928f1b32af483d
rm reporter
deactivate
popd

