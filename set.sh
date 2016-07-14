#!/bin/bash

VENV_DIR=/tmp/venv
CODE_DIR=$(pwd)/../
export PYTHONPATH="$CODE_DIR:$PYTHONPATH"

virtualenv $VENV_DIR
echo
pushd . > /dev/null
cd $VENV_DIR > /dev/null
source bin/activate

packages="python-pip python-dev python3-dev libssl-dev libpq-dev libvirt-dev"
for item in ${packages[*]}
do
    found=`dpkg -l | grep $item`
    if [ -n "$found" ]
    then
<<<<<<< HEAD
        echo -e "$item\t\e[1;32mOk\e[0m"
    else
	echo -en "$item\t\033[s\e[1;33mInstalling...\e[0m\033[u"
	apt-get install $item > /dev/null
	if [ $? -eq 0 ]
	then
            echo -e "\033[u\e[1;32mInstalled    \e[0m"
	else
    	    echo -e "\e[1;31mInstallation failed\e[0m"
    	    exit 1
	fi
=======
    echo -e "$item\t\e[1;32mOk\e[0m"
    else
    echo -en "$item\t\033[s\e[1;33mInstalling...\e[0m\033[u"
    apt-get install $item > /dev/null
    if [ $? -eq 0 ]
    then
        echo -e "\033[u\e[1;32mInstalled    \e[0m"
    else
        echo -e "\e[1;31mInstallation failed\e[0m"
        exit 1
    fi
>>>>>>> b14b6099615ae74dac4bf01dce9acbb866e5bab9
    fi
done

pwd

CUR_DIR=$(pwd)
#FUELQA_DIR=/home/user/fuel-qa
if env | grep -q ^FUELQA_DIR
then
    echo -e "Warning: System variable FUELQA_DIR is not set!"
else
    if ! [ -d $FUELQA_DIR ];
    then
        echo -e "\e[1;31mWarning: Value of system variable FUELQA_DIR is wrong!\nNo directory $FUELQA_DIR"
    fi
fi

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
pip install -r reporter/../requirements.txt > /dev/null
python reporter/../setup.py develop

# -------------- EXAMPLES -----------------
#pass
#python unified_test_reporter/reports/generate_failure_group_statistics.py -o /tmp/report
#python unified_test_reporter/reports/generate_statistics.py --verbose --handle-blocked --out-file bugs_link_stat --job-name 9.0.swarm.runner --html
#python unified_test_reporter/reports/report.py -v -j 9.0.test_all -N 500
#python unified_test_reporter/reports/upload_cases_description.py -v -l -j 9.0.swarm.runner -N 160
#python unified_test_reporter/tests/clients_test.py -v TestReporter.test_proboskis_getting_docstring
rm reporter
deactivate
popd

